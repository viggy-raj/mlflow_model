"""
Test script to verify MLflow and MinIO connectivity and integration.

Usage:
    Set environment variables first, then run:
        python test_mlflow_minio.py

Environment Variables Required:
    MINIO_ENDPOINT      — e.g. 192.168.x.x:9000
    MINIO_ACCESS_KEY    — your MinIO access key
    MINIO_SECRET_KEY    — your MinIO secret key
    BUCKET_NAME         — your MinIO bucket name
    MLFLOW_TRACKING_URI — e.g. http://0.0.0.0:5000
"""

import os
from dotenv import load_dotenv

# Load environment variables from the .env file in the backend directory
load_dotenv(dotenv_path="../.env")

import io
import sys
import joblib
import mlflow
import mlflow.sklearn
from minio import Minio
from minio.error import S3Error
from sklearn.ensemble import RandomForestClassifier

# ── Configuration ─────────────────────────────────────────────────────────────
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME      = os.getenv("BUCKET_NAME",)
MLFLOW_URI       = os.getenv("MLFLOW_TRACKING_URI")

TEST_OBJECT_NAME = "test/connectivity-test.pkl"
TEST_MODEL_NAME  = "connectivity-test-model"

PASS = "✅ PASS"
FAIL = "❌ FAIL"

# ── Helpers ───────────────────────────────────────────────────────────────────

def section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def result(label, success, detail=""):
    status = PASS if success else FAIL
    print(f"  {status}  {label}")
    if detail:
        print(f"         {detail}")

# ── Test 1: MinIO Connectivity ────────────────────────────────────────────────

def test_minio():
    section("TEST 1 — MinIO Connectivity")
    print(f"  Endpoint : {MINIO_ENDPOINT}")
    print(f"  Bucket   : {BUCKET_NAME}\n")

    try:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=True,        # MinIO server uses HTTPS
            cert_check=False,
        )
        result("MinIO client created", True)
    except Exception as e:
        result("MinIO client created", False, str(e))
        return False

    # Check bucket exists
    try:
        exists = client.bucket_exists(BUCKET_NAME)
        result(f"Bucket '{BUCKET_NAME}' exists", exists,
               "" if exists else f"Create bucket '{BUCKET_NAME}' in your MinIO console first.")
        if not exists:
            return False
    except S3Error as e:
        result("Bucket check", False, str(e))
        return False

    # Upload a small test model
    try:
        model = RandomForestClassifier(n_estimators=5)
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        buffer.seek(0)
        size = buffer.getbuffer().nbytes

        client.put_object(
            bucket_name=BUCKET_NAME,
            object_name=TEST_OBJECT_NAME,
            data=buffer,
            length=size,
            content_type="application/octet-stream",
        )
        result("Upload test .pkl to MinIO", True, f"Object: {TEST_OBJECT_NAME} ({size} bytes)")
    except S3Error as e:
        result("Upload test .pkl to MinIO", False, str(e))
        return False

    # List objects
    try:
        objects = list(client.list_objects(BUCKET_NAME, prefix="test/", recursive=True))
        result("List objects in bucket", True, f"Found {len(objects)} object(s) under 'test/' prefix")
    except S3Error as e:
        result("List objects in bucket", False, str(e))

    return True


# ── Test 2: MLflow Connectivity ───────────────────────────────────────────────

def test_mlflow():
    section("TEST 2 — MLflow Connectivity")
    print(f"  Tracking URI : {MLFLOW_URI}\n")

    mlflow.set_tracking_uri(MLFLOW_URI)

    # Set environment variables that boto3 (used by MLflow) requires for S3/MinIO
    os.environ["AWS_ACCESS_KEY_ID"] = MINIO_ACCESS_KEY
    os.environ["AWS_SECRET_ACCESS_KEY"] = MINIO_SECRET_KEY
    
    # MLflow expects the endpoint URL with the https:// prefix
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = f"https://{MINIO_ENDPOINT}"
    os.environ["MLFLOW_S3_IGNORE_TLS"] = "true"  # Ignore self-signed cert issues

    # Check server reachable
    try:
        client = mlflow.MlflowClient()
        client.search_registered_models()
        result("MLflow server reachable", True, MLFLOW_URI)
    except Exception as e:
        result("MLflow server reachable", False, str(e))
        return False

    # Log a model run
    run_id = None
    model_uri = None
    try:
        model = RandomForestClassifier(n_estimators=5)
        with mlflow.start_run() as run:
            mlflow.sklearn.log_model(model, name="model")
            run_id = run.info.run_id
        model_uri = f"runs:/{run_id}/model"
        result("Log model to MLflow run", True, f"run_id: {run_id}")
    except Exception as e:
        result("Log model to MLflow run", False, str(e))
        return False

    # Check artifact URI (should point to MinIO if configured)
    try:
        run_info = mlflow.get_run(run_id)
        artifact_uri = run_info.info.artifact_uri
        points_to_minio = artifact_uri.startswith("s3://") or artifact_uri.startswith("mlflow-artifacts:")
        result(
            "Artifact URI points to MinIO/S3",
            points_to_minio,
            f"Artifact URI: {artifact_uri}" + ("" if points_to_minio else
            "\n         ⚠️  Still pointing to local mlartifacts/. "
            "Start MLflow with --default-artifact-root s3://<bucket>")
        )
    except Exception as e:
        result("Check artifact URI", False, str(e))

    # Register the model
    try:
        reg = mlflow.register_model(model_uri=model_uri, name=TEST_MODEL_NAME)
        result("Register model in MLflow registry", True,
               f"Model: '{reg.name}', Version: {reg.version}")
    except Exception as e:
        result("Register model in MLflow registry", False, str(e))
        return False

    return True


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("  MLflow + MinIO Integration Test")
    print("═" * 60)

    minio_ok  = test_minio()
    mlflow_ok = test_mlflow()

    section("SUMMARY")
    result("MinIO", minio_ok)
    result("MLflow", mlflow_ok)

    if minio_ok and mlflow_ok:
        print("\n  🎉 All tests passed! Your setup is ready.\n")
    else:
        print("\n  ⚠️  Some tests failed. Fix the issues above and re-run.\n")
        sys.exit(1)
