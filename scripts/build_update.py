#!/usr/bin/env python3
import argparse, hashlib, hmac, json, os, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ALLOWED_ROOT={"run.py","requirements.txt","gunicorn.conf.py","VERSION"}
ALLOWED_PREFIXES=("app/","migrations/","tests/")

def canonical(m):
    x=dict(m); x.pop("signature",None)
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def main():
    p=argparse.ArgumentParser(description="Build a signed RSMS update package")
    p.add_argument("--version",required=True); p.add_argument("--minimum-version",default="1.0.0"); p.add_argument("--output"); p.add_argument("--changelog",default="RSMS update"); p.add_argument("--delete",action="append",default=[]); args=p.parse_args()
    files={}
    for path in ROOT.rglob("*"):
        if not path.is_file(): continue
        rel=path.relative_to(ROOT).as_posix()
        if rel.startswith((".git/",".venv/","instance/","uploads/","backups/","logs/","__pycache__/")) or "/__pycache__/" in rel or rel.endswith((".pyc",".DS_Store")): continue
        if rel in ALLOWED_ROOT or rel.startswith(ALLOWED_PREFIXES): files[rel]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={"version":args.version,"minimum_version":args.minimum_version,"changelog":args.changelog,"files":files,"delete":args.delete}
    key=os.environ.get("RSMS_UPDATE_KEY","")
    if not key: raise SystemExit("RSMS_UPDATE_KEY is required to build a signed production update package")
    manifest["signature"]=hmac.new(key.encode(),canonical(manifest),hashlib.sha256).hexdigest()
    output=Path(args.output or f"rsms-update-{args.version}.zip")
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("update.json",json.dumps(manifest,indent=2,ensure_ascii=False))
        for rel in files: z.write(ROOT/rel,rel)
    print(f"Built {output} with {len(files)} files")
    print("SHA256:",hashlib.sha256(output.read_bytes()).hexdigest())
if __name__=="__main__": main()
