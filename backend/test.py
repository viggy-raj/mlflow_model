import os
from minio import Minio
from dotenv import load_dotenv
load_dotenv()

client = Minio(
    os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=True,
    cert_check=False,
)

try:
    exists = client.bucket_exists("mlflow-dev")

    if exists:
        print("✅ Connected successfully. Bucket exists.")
    else:
        print("❌ Connected to MinIO, but bucket does not exist.")

except Exception as e:
    print("❌ Connection failed:")
    print(e)
