import os
from minio import Minio

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")

print(f"Connecting to MinIO at {MINIO_ENDPOINT}...")
print(f"Checking bucket: {BUCKET_NAME}\n")

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=True,
    cert_check=False
)

try:
    objects = client.list_objects(BUCKET_NAME, recursive=True)
    count = 0
    print("-" * 60)
    for obj in objects:
        count += 1
        print(f"📦 {obj.object_name} (Size: {obj.size} bytes)")
    print("-" * 60)
    print(f"\nTotal files found: {count}")
except Exception as e:
    print(f"Error connecting to MinIO: {e}")
