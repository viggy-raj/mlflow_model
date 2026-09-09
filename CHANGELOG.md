# Changelog

## [Unreleased] - Automated Dynamic Model Replacement Lifecycle
### Added
- `ModelVersionService` (`model_management/services/model_version_service.py`): New thin
  facade over `MlflowClient` that manages the `"approved"` and `"active"` MLflow model
  aliases (with tag-based fallback for older MLflow servers).  Provides
  `get_latest_approved_version()`, `get_active_version()`, `set_approved()`, `set_active()`,
  and `get_all_registered_names()`.
- `LifecycleManager` (`model_management/services/lifecycle_manager.py`): New singleton
  service encapsulating the auto-promotion decision logic.  Compares the latest approved
  version against the currently active version for any registered MLflow model and
  automatically calls `RolloutManager.start_rollout()` when a newer approved version is
  detected.
- `POST /api/v1/models/approve/` endpoint: Stamps the `"approved"` alias on a specific
  MLflow model version and immediately calls `LifecycleManager.check_for_pending_promotion()`
  to detect and trigger a canary rollout if warranted.
- `ModelApproveSerializer` in `api/serializers/model_serializers.py`.
- On-startup lifecycle check in `ModelManagementConfig.ready()`: after resuming any active
  rollout from the DB, calls `LifecycleManager.check_for_pending_promotion_all()` to handle
  approvals that occurred while the server was offline.
- Four new nullable fields on `RolloutState` (`v1_mlflow_name`, `v1_mlflow_version`,
  `v2_mlflow_name`, `v2_mlflow_version`) that carry the MLflow registered model name and
  version for generic artifact URI construction.
- Database migration `0002_rolloutstate_mlflow_fields`.
- **Generic MLflow artifact routing** in `RolloutManager.predict()`: when the lifecycle
  fields are populated, builds the model URI as `models:/{name}/{version}` — fully dynamic,
  no model name or version hardcoded.  Legacy manual-rollout path is preserved when those
  fields are `None`.
- **Automatic V2→active promotion**: `RolloutManager.advance_step()` calls
  `ModelVersionService.set_active()` on the V2 model when the rollout reaches `COMPLETE`.
- **9 new unit-test files / test cases**: `test_model_version_service.py` (9 tests),
  `test_lifecycle_manager.py` (7 tests), `test_approve_endpoint.py` (3 tests),
  and 2 additional tests in `test_rollout_manager.py`.

### Changed
- `RolloutManager.start_rollout()` now accepts optional `v1_mlflow_name`,
  `v1_mlflow_version`, `v2_mlflow_name`, `v2_mlflow_version` keyword arguments.
- `RolloutManager.get_status()` includes the new mlflow name/version fields in its response.
- `apps.py` `ready()` hook now also calls `LifecycleManager`.
- `README.md` updated with "Automated Model Promotion Lifecycle" section.

---

## [Unreleased] - Native MLflow & Real Apache Ozone Storage

### Added
- Integrated native MLflow tracking with Apache Ozone S3 Gateway for model artifact storage.
- Added explicit `artifact_location` mapping to `s3://ml-models/mlflow-artifacts` inside `ExperimentService.get_or_create_experiment()`.
- MLflow now exclusively manages model artifact storage using `boto3`.
- `backend/.env.example` containing required S3 endpoint variables.
- Real Apache Ozone integration using `boto3` and the MLflow S3 plugin.
- Native model execution in `RolloutManager.predict()`. The engine now dynamically pulls the model artifact directly from the MLflow registry using `mlflow.pyfunc.load_model()` instead of instantiating local static classes.
- Explicit Node 16 engine requirements in frontend `package.json` files.
- `backend/.env.example` containing required S3 endpoint variables.
- Integration test (`integration_test_ozone.py`) to verify artifacts are physically written to the Ozone bucket.

### Removed
- `OzoneStorageService` (the fake console-only placeholder) has been completely deleted.
- The `StorageService` interface was removed to prevent duplicate/competing artifact storage paths. MLflow is now the single source of truth for artifact storage.
- Manual serialization methods from dummy models.
