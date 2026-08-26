import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from flask import current_app

ALLOWED_ROOT_FILES={"run.py","requirements.txt","gunicorn.conf.py","VERSION"}
ALLOWED_PREFIXES=("app/","migrations/","tests/")
PROTECTED_PREFIXES=(".env",".git/",".venv/","instance/","uploads/","backups/","logs/")
MAX_FILES=5000
MAX_UNCOMPRESSED=150*1024*1024

class UpdateError(RuntimeError): pass

def app_root(): return Path(current_app.root_path).parent.resolve()
def current_version():
    p=app_root()/"VERSION"
    return p.read_text().strip() if p.exists() else "1.0.0"
def _version_tuple(value):
    parts=[]
    for bit in str(value).split("."):
        try: parts.append(int("".join(c for c in bit if c.isdigit()) or 0))
        except ValueError: parts.append(0)
    return tuple((parts+[0,0,0])[:3])
def _safe_path(name):
    name=name.replace("\\","/").lstrip("/")
    if not name or name.endswith("/"): return None
    p=Path(name)
    if ".." in p.parts: raise UpdateError(f"Unsafe path: {name}")
    if any(name==x or name.startswith(x) for x in PROTECTED_PREFIXES): raise UpdateError(f"Protected path in package: {name}")
    if name not in ALLOWED_ROOT_FILES and not name.startswith(ALLOWED_PREFIXES): raise UpdateError(f"Path not allowed in update: {name}")
    return name

def _canonical_manifest(manifest):
    clean=dict(manifest); clean.pop("signature",None)
    return json.dumps(clean,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _verify_signature(manifest):
    key=os.environ.get("RSMS_UPDATE_KEY","")
    signature=manifest.get("signature","")
    if current_app.config.get("ENV")=="production" and not key: raise UpdateError("RSMS_UPDATE_KEY must be configured in production before updates can be installed.")
    if key:
        expected=hmac.new(key.encode(),_canonical_manifest(manifest),hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature,expected): raise UpdateError("Update package signature is invalid.")

def inspect_package(zip_path):
    zip_path=Path(zip_path)
    if not zipfile.is_zipfile(zip_path): raise UpdateError("Upload is not a valid ZIP update package.")
    package_sha=hashlib.sha256(zip_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(zip_path) as z:
        infos=z.infolist()
        if len(infos)>MAX_FILES: raise UpdateError("Update contains too many files.")
        if sum(i.file_size for i in infos)>MAX_UNCOMPRESSED: raise UpdateError("Update package is too large when extracted.")
        if "update.json" not in z.namelist(): raise UpdateError("update.json is missing from the update package.")
        try: manifest=json.loads(z.read("update.json").decode("utf-8"))
        except Exception as exc: raise UpdateError("update.json is invalid.") from exc
        version=str(manifest.get("version","")).strip(); minimum=str(manifest.get("minimum_version","")).strip(); files=manifest.get("files")
        if not version or not isinstance(files,dict) or not files: raise UpdateError("Manifest requires version and files.")
        if minimum and _version_tuple(current_version())<_version_tuple(minimum): raise UpdateError(f"Update requires RSMS {minimum} or newer.")
        if _version_tuple(version)<=_version_tuple(current_version()) and not manifest.get("allow_same_version"): raise UpdateError(f"Update {version} is not newer than installed version {current_version()}.")
        _verify_signature(manifest)
        archive_names=set(z.namelist())
        for raw,expected_hash in files.items():
            name=_safe_path(raw)
            if not name or name not in archive_names: raise UpdateError(f"Manifest file missing from ZIP: {raw}")
            actual=hashlib.sha256(z.read(name)).hexdigest()
            if actual.lower()!=str(expected_hash).lower(): raise UpdateError(f"Checksum mismatch for {name}")
        for raw in manifest.get("delete",[]): _safe_path(raw)
    return manifest,package_sha

def _extract_candidate(zip_path,manifest,candidate):
    root=app_root()
    ignore=shutil.ignore_patterns(".git",".venv","instance","uploads","backups","logs","__pycache__","*.pyc")
    shutil.copytree(root,candidate,dirs_exist_ok=True,ignore=ignore)
    with zipfile.ZipFile(zip_path) as z:
        for raw in manifest["files"]:
            name=_safe_path(raw); dest=(candidate/name).resolve()
            if not str(dest).startswith(str(candidate.resolve())+os.sep): raise UpdateError("Unsafe extraction target.")
            dest.parent.mkdir(parents=True,exist_ok=True)
            with z.open(name) as src,open(dest,"wb") as out: shutil.copyfileobj(src,out)
        for raw in manifest.get("delete",[]):
            target=candidate/_safe_path(raw)
            if target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()

def _run(command,cwd,timeout=300,env=None):
    result=subprocess.run(command,cwd=str(cwd),env=env or os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
    if result.returncode!=0: raise UpdateError(f"Command failed: {' '.join(command)}\n{result.stdout[-5000:]}")
    return result.stdout

def _backup_database(backup_dir):
    uri=str(current_app.config.get("SQLALCHEMY_DATABASE_URI") or "")
    backup_dir.mkdir(parents=True,exist_ok=True)
    if uri.startswith("sqlite"):
        from app.extensions import db
        path=Path(db.engine.url.database or "")
        if path.exists():
            dest=backup_dir/"database.sqlite"; shutil.copy2(path,dest); return str(dest)
        return None
    if uri.startswith("postgresql"):
        pg_uri=uri.replace("postgresql+psycopg://","postgresql://",1)
        dest=backup_dir/"database.dump"
        try: _run(["pg_dump","--dbname",pg_uri,"--format=custom","--file",str(dest)],app_root(),timeout=300)
        except FileNotFoundError as exc: raise UpdateError("pg_dump is required for production database backup.") from exc
        return str(dest)
    raise UpdateError("Unsupported database type for automatic update backup.")

def _backup_files(manifest,backup_dir):
    root=app_root(); files_dir=backup_dir/"files"; files_dir.mkdir(parents=True,exist_ok=True)
    for raw in set(manifest["files"])|set(manifest.get("delete",[])):
        name=_safe_path(raw); src=root/name
        if src.exists():
            dst=files_dir/name; dst.parent.mkdir(parents=True,exist_ok=True)
            if src.is_dir(): shutil.copytree(src,dst,dirs_exist_ok=True)
            else: shutil.copy2(src,dst)
    return files_dir

def _activate(zip_path,manifest):
    root=app_root()
    with zipfile.ZipFile(zip_path) as z:
        for raw in manifest["files"]:
            name=_safe_path(raw); target=root/name; target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+".update-tmp")
            with z.open(name) as src,open(temp,"wb") as out: shutil.copyfileobj(src,out)
            os.replace(temp,target)
        for raw in manifest.get("delete",[]):
            target=root/_safe_path(raw)
            if target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()

def _restore_files(manifest,backup_dir):
    root=app_root(); files_dir=backup_dir/"files"
    for raw in manifest["files"]:
        name=_safe_path(raw); current=root/name; backup=files_dir/name
        if backup.exists():
            current.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(backup,current)
        elif current.exists(): current.unlink()
    for raw in manifest.get("delete",[]):
        name=_safe_path(raw); backup=files_dir/name; current=root/name
        if backup.exists(): current.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(backup,current)

def install_package(zip_path,manifest):
    root=app_root(); stamp=datetime.now().strftime("%Y%m%d-%H%M%S"); backup_dir=root/"backups"/"system-updates"/f"{stamp}-{current_version()}"
    with tempfile.TemporaryDirectory(prefix="rsms-update-") as tmp:
        candidate=Path(tmp)/"candidate"; _extract_candidate(zip_path,manifest,candidate)
        env=os.environ.copy(); env["FLASK_ENV"]="testing"; env["PYTHONPATH"]=str(candidate)
        if (candidate/"tests").exists(): _run([sys.executable,"-m","pytest","-q","-W","error::sqlalchemy.exc.LegacyAPIWarning"],candidate,timeout=600,env=env)
        _backup_database(backup_dir); _backup_files(manifest,backup_dir)
        try:
            _activate(zip_path,manifest)
            if "requirements.txt" in manifest["files"]: _run([sys.executable,"-m","pip","install","-r","requirements.txt"],root,timeout=600)
            _run([sys.executable,"-m","flask","--app","run.py","db","upgrade"],root,timeout=300)
            health_env=os.environ.copy(); health_env["PYTHONPATH"]=str(root)
            _run([sys.executable,"-c","from app import create_app; create_app('testing'); print('RSMS health OK')"],root,timeout=120,env=health_env)
            (root/"VERSION").write_text(str(manifest["version"]).strip()+"\n")
        except Exception:
            _restore_files(manifest,backup_dir)
            raise
    return str(backup_dir)
