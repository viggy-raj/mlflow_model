# MLflow Ozone Platform

A local MLflow-based model management platform utilizing a Microfrontend Architecture (React/Webpack 5 Module Federation) and a Django Backend-for-Frontend (BFF). Model artifacts are stored exclusively in Apache Ozone via its S3 Gateway.

## Architecture

This project is built from scratch and relies on the following decoupled components:

1. **React Shell (Port 3000)**: The root microfrontend host application.
2. **Model Management MFE (Port 3001)**: A remote microfrontend federated into the Shell, responsible for the Model UI.
3. **Django/DRF BFF (Port 8000)**: The API layer providing RESTful services under `/api/v1/`.
4. **MLflow Tracking Server (Port 5000)**: Manages experiment, run, and model metadata (using local SQLite).
5. **Apache Ozone S3 Gateway (Port 9878)**: The real backend object storage where serialized ML models are physically stored.

*Note: There is NO cloud deployment, NO Azure, NO Kubernetes, and NO Quiz functionality in this local development project.*

## Prerequisites

- **Node.js**: `v16.x` strictly required.
- **Python**: `3.10+`
- **Apache Ozone**: A local instance of Apache Ozone exposing the S3-compatible Gateway (e.g., via Docker Compose).

## Environment Configuration

Copy `backend/.env.example` to `backend/.env` and update your Ozone credentials:
```env
# Apache Ozone S3 Gateway Configuration
MLFLOW_S3_ENDPOINT_URL=http://localhost:9878
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
OZONE_BUCKET=ml-models
MLFLOW_S3_IGNORE_TLS=true
```

## MLflow & Ozone Setup

1. Ensure your Apache Ozone S3 Gateway is running and your bucket (e.g., `ml-models`) exists.
2. Start the MLflow Tracking Server, configuring it to use SQLite for metadata and the Ozone S3 bucket for artifacts:

```bash
export MLFLOW_S3_ENDPOINT_URL=http://localhost:9878
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export MLFLOW_S3_IGNORE_TLS=true

mlflow server \
    --backend-store-uri sqlite:///mlflow.db \
    --default-artifact-root s3://ml-models/ \
    --host 0.0.0.0 --port 5000
```

## Backend Startup

1. Navigate to `backend/`.
2. Create and activate a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run migrations: `python manage.py migrate`.
5. Start the server: `python manage.py runserver`.

## Frontend Startup

Ensure you are using Node 16.

1. Terminal 1 (Model Management MFE):
   ```bash
   cd frontend/mfe-model-management
   npm install
   npm start
   ```

2. Terminal 2 (Shell):
   ```bash
   cd frontend/shell
   npm install
   npm start
   ```
Navigate to `http://localhost:3000` to view the application.

## Workflows

### Model Training
1. In the UI, click **Train Model** (select either `dummy_model` or `dummy_model_bad`).
2. The UI sends a POST request to the Django BFF (`/api/v1/models/train/`).
3. The Django backend wraps the dummy model in an `mlflow.pyfunc.PythonModel`.
4. `mlflow.pyfunc.log_model()` natively serializes the model and uses `boto3` to push the artifact directly to the Apache Ozone S3 Gateway.
5. The model metadata and registered versions are stored in the MLflow SQLite database.

### Prediction & Rollout
1. A gradual rollout shifts traffic between a V1 model and a V2 model.
2. The `RolloutManager` dynamically pulls the executable artifact natively from MLflow using `mlflow.pyfunc.load_model(model_uri)`.
3. If the V2 model produces invalid results (error rate > 20%), an automatic rollback occurs.

## Artifact Verification in Ozone

You can verify that the model artifact was physically stored in Apache Ozone by running the integration test:

```bash
cd backend
export RUN_OZONE_INTEGRATION_TESTS=1
pytest tests/integration_test_ozone.py -v -s
```

Or manually using the AWS CLI configured for your local Ozone Gateway:
```bash
aws s3 ls s3://ml-models/ --endpoint-url http://localhost:9878
```

## Tests
Run the backend unit tests to verify API endpoints, routing, and rollback logic (MLflow is mocked locally during unit tests):
```bash
pytest backend/tests/
```
