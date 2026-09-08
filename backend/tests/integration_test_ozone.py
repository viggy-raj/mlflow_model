import os
import boto3
import pytest
from dotenv import load_dotenv

load_dotenv()

# Skip this test if we are not specifically running integration tests
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_OZONE_INTEGRATION_TESTS") != "1",
    reason="Ozone integration tests are disabled by default. Set RUN_OZONE_INTEGRATION_TESTS=1 to run."
)

def test_ozone_s3_connection_and_artifact_presence():
    """
    Integration test to verify that Apache Ozone S3 Gateway is accessible
    and contains MLflow artifacts.
    """
    endpoint_url = os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9878")
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket_name = os.environ.get("OZONE_BUCKET", "ml-models")

    assert aws_access_key_id, "AWS_ACCESS_KEY_ID must be set"
    assert aws_secret_access_key, "AWS_SECRET_ACCESS_KEY must be set"

    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        verify=False  # Typically MLFLOW_S3_IGNORE_TLS is true for local testing
    )

    # 1. Verify we can list buckets
    try:
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        assert bucket_name in buckets, f"Bucket '{bucket_name}' not found in Ozone."
    except Exception as e:
        pytest.fail(f"Failed to connect to Ozone S3 Gateway or list buckets: {e}")

    # 2. Verify we have objects in the bucket (e.g., our uploaded MLflow models)
    try:
        objects_response = s3_client.list_objects_v2(Bucket=bucket_name)
        assert 'Contents' in objects_response, "Bucket is empty. No artifacts found!"
        
        objects = [obj['Key'] for obj in objects_response['Contents']]
        print(f"Found {len(objects)} objects in bucket '{bucket_name}'.")
        
        # MLflow typically stores under <experiment_id>/<run_id>/artifacts/...
        # We just verify at least one artifact exists.
        assert len(objects) > 0, "No model artifacts found in the Ozone bucket."
    except Exception as e:
        pytest.fail(f"Failed to list objects in Ozone bucket: {e}")
