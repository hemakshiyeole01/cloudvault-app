#!/bin/bash
# EC2 user-data for CloudVault (Amazon Linux 2023)
# EDIT THESE THREE before use:
REPO_URL="https://github.com/YOUR-USERNAME/YOUR-REPO.git"
S3_BUCKET="cloudvault-uploads-cc-pro"
APP_PORT=80   # must match the cloudvault-tg target group port

dnf update -y
dnf install -y python3-pip git

cd /opt
git clone "$REPO_URL" cloudvault-app
cd cloudvault-app

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cat > /etc/systemd/system/cloudvault.service << UNIT
[Unit]
Description=CloudVault Flask App
After=network.target

[Service]
WorkingDirectory=/opt/cloudvault-app
Environment=S3_BUCKET=${S3_BUCKET}
Environment=AWS_REGION=us-east-1
ExecStart=/opt/cloudvault-app/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:${APP_PORT} app:app
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now cloudvault
