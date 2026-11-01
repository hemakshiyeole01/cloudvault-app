import os
import socket
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, redirect, render_template, request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET")

# No access keys here. On EC2 this uses the attached IAM role automatically.
s3 = boto3.client("s3", region_name=AWS_REGION)


def list_files():
    """Return (files, error_message) for the bucket."""
    if not S3_BUCKET:
        return [], "S3 bucket is not configured."
    try:
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=100)
        files = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            files.append({
                "key": key,
                "name": key.split("_", 1)[-1],  # strip the uuid prefix
                "size_kb": round(obj["Size"] / 1024, 1),
                "modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M"),
            })
        files.sort(key=lambda f: f["modified"], reverse=True)
        return files, None
    except (ClientError, BotoCoreError):
        app.logger.exception("S3 list failed")
        return [], "Could not load files from S3."


def render_home(message=None, status=200):
    files, list_error = list_files()
    return render_template(
        "index.html",
        hostname=socket.gethostname(),
        files=files,
        message=message or list_error,
    ), status


@app.route("/")
def home():
    return render_home()


@app.route("/health")
def health():
    return {"status": "healthy"}, 200


@app.route("/upload", methods=["POST"])
def upload_file():
    if not S3_BUCKET:
        return render_home("S3 bucket is not configured.", 500)
    if "file" not in request.files:
        return render_home("No file selected.", 400)

    file = request.files["file"]
    filename = secure_filename(file.filename or "")
    if not filename:
        return render_home("Invalid or empty filename.", 400)

    key = f"{uuid.uuid4().hex}_{filename}"
    try:
        s3.upload_fileobj(file, S3_BUCKET, key)
        return render_home(f"'{filename}' uploaded successfully to S3!")
    except (ClientError, BotoCoreError):
        app.logger.exception("S3 upload failed")
        return render_home("Upload failed. Check the application logs.", 500)


@app.route("/download/<path:key>")
def download_file(key):
    if not S3_BUCKET:
        return render_home("S3 bucket is not configured.", 500)
    original_name = key.split("_", 1)[-1]
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{original_name}"',
            },
            ExpiresIn=300,  # link valid for 5 minutes
        )
        return redirect(url)
    except (ClientError, BotoCoreError):
        app.logger.exception("Presign failed")
        return render_home("Could not create download link.", 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)