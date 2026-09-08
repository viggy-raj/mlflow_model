# Changelog

## [1.1.0] - Native MLflow & Real Apache Ozone Storage
### Added
- Real Apache Ozone integration using `boto3` and the MLflow S3 plugin.
- MLflow native model logging. `ModelTrainView` now uses `mlflow.pyfunc.log_model()` with an explicit `PythonModel` wrapper.
- Native model execution in `RolloutManager.predict()`. The engine now dynamically pulls the model artifact directly from the MLflow registry using `mlflow.pyfunc.load_model()` instead of instantiating local static classes.
- Explicit Node 16 engine requirements in frontend `package.json` files.
- `backend/.env.example` containing required S3 endpoint variables.
- Integration test (`integration_test_ozone.py`) to verify artifacts are physically written to the Ozone bucket.

### Removed
- `OzoneStorageService` (the fake console-only placeholder) has been completely deleted.
- The `StorageService` interface was removed to prevent duplicate/competing artifact storage paths. MLflow is now the single source of truth for artifact storage.
- Manual serialization methods from dummy models.
