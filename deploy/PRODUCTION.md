# RSMS production deployment

This runbook assumes Ubuntu/Debian, PostgreSQL, Redis, Nginx and systemd. Do not use the Flask development server in production.

## 1. Server packages

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv postgresql redis-server nginx certbot python3-certbot-nginx
sudo systemctl enable --now postgresql redis-server nginx
```

## 2. Application user and checkout

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin rsms || true
sudo mkdir -p /opt/rsms /etc/rsms /var/backups/rsms
sudo chown rsms:www-data /opt/rsms
sudo chmod 700 /etc/rsms /var/backups/rsms
# Clone/copy the tested production-hardening release into /opt/rsms, then:
cd /opt/rsms
sudo -u rsms python3.12 -m venv .venv
sudo -u rsms .venv/bin/pip install --upgrade pip
sudo -u rsms .venv/bin/pip install -r requirements.txt
```

## 3. PostgreSQL

Create a dedicated database/user and a strong password. Example from `sudo -u postgres psql`:

```sql
CREATE USER rsms WITH PASSWORD 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD';
CREATE DATABASE rsms OWNER rsms;
REVOKE ALL ON DATABASE rsms FROM PUBLIC;
```

Do not expose PostgreSQL or Redis to the public internet. Bind/firewall them to localhost/private networking.

## 4. Environment

Copy `deploy/rsms.env.example` to `/etc/rsms/rsms.env`, replace every placeholder, and protect it:

```bash
sudo cp deploy/rsms.env.example /etc/rsms/rsms.env
sudo chmod 600 /etc/rsms/rsms.env
sudo chown root:root /etc/rsms/rsms.env
openssl rand -hex 32
```

Set `SECRET_KEY` to the generated value. Keep `FLASK_ENV=production`, `SESSION_COOKIE_SECURE=true`, and `TRUST_PROXY=true` when Nginx is the trusted local reverse proxy.

## 5. Database migration

```bash
cd /opt/rsms
set -a; source /etc/rsms/rsms.env; set +a
.venv/bin/flask --app run.py db upgrade
```

For migration from an existing SQLite development database, do not copy the SQLite file into production. Export/import the business data deliberately into PostgreSQL and verify row counts and key workflows before cutover.

## 6. Gunicorn service

Review `deploy/rsms.service.example`, then:

```bash
sudo cp deploy/rsms.service.example /etc/systemd/system/rsms.service
sudo systemctl daemon-reload
sudo systemctl enable --now rsms
sudo systemctl status rsms
curl -I http://127.0.0.1:8000/
```

## 7. Nginx and HTTPS

Copy `deploy/nginx-rsms.conf.example`, replace `rsms.example.com` with the real hostname, and initially obtain/manage the TLS certificate with Certbot. Validate before reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d YOUR_RSMS_HOSTNAME
```

Only ports 80/443 should be internet-facing for the web application. Gunicorn remains on `127.0.0.1:8000`.

## 8. Backups

Install the backup scripts:

```bash
sudo install -m 700 deploy/backup-rsms.sh /usr/local/sbin/backup-rsms
sudo install -m 700 deploy/restore-rsms.sh /usr/local/sbin/restore-rsms
sudo /usr/local/sbin/backup-rsms
```

Schedule at least daily backups (systemd timer or cron), copy backups off the application server, encrypt/protect that destination, and monitor backup failures. Retention defaults to 14 days.

A backup is not considered verified until a recent dump is restored into a separate test database and RSMS can read that restored data. Never test restore against the live database.

## 9. Release procedure

Before each deployment: create a database backup, record the current Git commit, pull/deploy only the tested release, install dependencies, run `flask db upgrade`, restart RSMS, and perform smoke tests. Keep the previous application commit available for rollback. Database migrations may require a forward-fix; do not blindly downgrade a production database.

```bash
sudo /usr/local/sbin/backup-rsms
cd /opt/rsms
git rev-parse HEAD
git pull --ff-only origin production-hardening
.venv/bin/pip install -r requirements.txt
set -a; source /etc/rsms/rsms.env; set +a
.venv/bin/flask --app run.py db upgrade
sudo systemctl restart rsms
sudo systemctl status rsms
```

## 10. Production smoke checklist

Verify login/logout, dashboard, lead webhook pending + verified update, lead confirmation, customer linkage, booking confirmation, repair creation, technician access, QC before/after, inventory reserve/use/return, payment, invoice print, customer history, permissions for non-admin roles, pagination, system settings, and backup creation. Check `journalctl -u rsms` and Nginx logs for 4xx/5xx errors.

## 11. Security checklist

Use unique admin accounts and strong passwords; remove/disable unused users; never commit secrets or production `.env`; regenerate any webhook token that has been exposed; keep OS/PostgreSQL/Redis/Python packages patched; restrict SSH; use a firewall; keep PostgreSQL/Redis/Gunicorn private; maintain HTTPS; test role permissions with real non-admin accounts; and restore-test backups periodically.
