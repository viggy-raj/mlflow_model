#!/bin/bash
# start_mlflow.sh
# Reads MinIO credentials from the .env file and starts MLflow
# with MinIO as the artifact store.

set -a  # Automatically export all variables read by source
source "$(dirname "$0")/backend/.env"
set +a

# Map MinIO credentials to what boto3 (used by MLflow) expects
export AWS_ACCESS_KEY_ID="$MINIO_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$MINIO_SECRET_KEY"
export MLFLOW_S3_ENDPOINT_URL="https://$MINIO_ENDPOINT"
export MLFLOW_S3_IGNORE_TLS="true"

echo "Starting MLflow server..."
echo "  MinIO Endpoint : $MINIO_ENDPOINT"
echo "  Bucket         : $BUCKET_NAME"
echo "  Tracking URI   : http://127.0.0.1:5000"
echo ""

mlflow server \
    --backend-store-uri sqlite:///mlflow.db \
    --default-artifact-root "s3://$BUCKET_NAME" \
    --serve-artifacts \
    --host 127.0.0.1 \
    --port 5000
