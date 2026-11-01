import os
import socket
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET")  # set via environment, don't hardcode

# No access keys here. On EC2 this uses the attached IAM role automatically.
s3 = boto3.client("s3", region_name=AWS_REGION)


@app.route("/")
def home():
    return render_template("index.html", hostname=socket.gethostname())


@app.route("/health")
def health():
    return {"status": "healthy"}, 200


@app.route("/upload", methods=["POST"])
def upload_file():
    if not S3_BUCKET:
        return "S3 bucket is not configured.", 500
    if "file" not in request.files:
        return "No file selected.", 400

    file = request.files["file"]
    filename = secure_filename(file.filename or "")
    if not filename:
        return "Invalid or empty filename.", 400

    key = f"{uuid.uuid4().hex}_{filename}"
    try:
        s3.upload_fileobj(file, S3_BUCKET, key)
        return f"File '{filename}' uploaded successfully to S3!", 200
    except (ClientError, BotoCoreError):
        app.logger.exception("S3 upload failed")
        return "Upload failed. Check the application logs.", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
