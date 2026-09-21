import os
import torch
import onnx
import mlflow
import mlflow.pytorch
import mlflow.onnx
from mlflow.exceptions import MlflowException

from .models import LogicalModel, ModelVersion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_size(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    if not size_bytes:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def get_model_size_from_mlflow(client, model_version) -> int:
    """
    Attempt to sum artifact sizes for a model version run in MLflow.
    Returns None if artifacts cannot be listed.
    """
    try:
        artifacts = client.list_artifacts(model_version.run_id, path="model")
        total_size = sum(item.file_size for item in artifacts if item.file_size)
        return total_size or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_or_create_minio_experiment(experiment_name: str = "model-registry") -> str:
    """
    Get or create an MLflow experiment that is guaranteed to use the
    MinIO-backed artifact store (i.e. was created after the server was
    started with --default-artifact-root s3://...).

    Returns the experiment_id.
    """
    client = mlflow.MlflowClient()
    experiment = client.get_experiment_by_name(experiment_name)

    if experiment is None:
        # Create a fresh experiment — it will use the current default artifact root (MinIO)
        experiment_id = client.create_experiment(experiment_name)
    else:
        experiment_id = experiment.experiment_id

    return experiment_id


# ---------------------------------------------------------------------------
# Unified Service Class
# ---------------------------------------------------------------------------

class ModelServices:
    """
    Unified service layer for ML model registration, listing, and deletion.

    Supported file formats: .pt (PyTorch), .onnx (ONNX)
    Artifacts are stored directly in MLflow's configured artifact store (e.g. MinIO).
    """

    SUPPORTED_FORMATS = {"pt", "onnx"}

    @staticmethod
    def register_model(
        file_path: str,
        original_filename: str,
        model_name: str,
        model_type: str,
        accuracy: float,
        file_size: int,
        architecture: str = "",
        priority: int = None,
        is_deployable: bool = False,
        versioning: str = "Auto-increment",
        deployment_points: list = None,
        remarks: str = "",
    ) -> dict:
        """
        Full registration workflow:
          1. Validate / load the model file
          2. Get or create the LogicalModel entry; enforce model_type consistency
          3. Log the model run to MLflow (tags, metrics, artifact)
          4. Register the model in the MLflow Model Registry
          5. Create a ModelVersion DB record

        Returns a dict with: model_name, version, run_id, db_record_id, formatted_size
        """
        if deployment_points is None:
            deployment_points = []

        file_format = original_filename.lower().rsplit('.', 1)[-1]
        if file_format not in ModelServices.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format '.{file_format}'. "
                f"Supported formats: {', '.join(f'.{f}' for f in ModelServices.SUPPORTED_FORMATS)}"
            )

        # 1. Validate / load the model file
        try:
            if file_format == "pt":
                model_obj = torch.load(file_path, weights_only=False)
            elif file_format == "onnx":
                model_obj = onnx.load(file_path)
        except Exception as e:
            raise Exception(f"Model validation failed: {e}") from e

        # 2. Get or create LogicalModel; enforce model_type consistency
        logical_model = LogicalModel.objects.filter(name=model_name).first()
        if logical_model:
            if logical_model.model_type != model_type:
                raise ValueError(
                    f"Model '{model_name}' already exists with type "
                    f"'{logical_model.model_type}'. "
                    f"Cannot register new version as '{model_type}'."
                )
        else:
            logical_model = LogicalModel.objects.create(
                name=model_name,
                model_type=model_type,
                mlflow_name=model_name,
            )

        # 3. Log to MLflow — always use a MinIO-backed experiment
        try:
            experiment_id = get_or_create_minio_experiment("model-registry")
            tags = {
                "model_type": model_type,
                "framework": file_format,
                "is_deployable": str(is_deployable),
                "versioning": versioning,
            }
            if architecture:
                tags["architecture"] = architecture

            metrics = {"accuracy": accuracy}
            if priority is not None:
                metrics["priority"] = float(priority)

            with mlflow.start_run(experiment_id=experiment_id) as run:
                mlflow.set_tags(tags)
                mlflow.log_metrics(metrics)

                if file_format == "pt":
                    mlflow.pytorch.log_model(
                        model_obj, artifact_path="model", serialization_format="pickle"
                    )
                elif file_format == "onnx":
                    mlflow.onnx.log_model(model_obj, artifact_path="model")

                run_id = run.info.run_id

            model_uri = f"runs:/{run_id}/model"
            result = mlflow.register_model(model_uri=model_uri, name=model_name)

        except MlflowException as e:
            raise Exception(f"MLflow registration failed: {e}") from e
        except Exception as e:
            raise Exception(f"MLflow registration failed: {e}") from e

        # 4. Create ModelVersion DB record
        db_version = ModelVersion.objects.create(
            logical_model=logical_model,
            version_number=result.version,
            architecture=architecture,
            accuracy=accuracy,
            priority=priority,
            is_deployable=is_deployable,
            remarks=remarks,
            deployment_points=deployment_points,
            original_filename=original_filename,
            file_format=file_format,
            file_size=file_size,
            run_id=run_id,
            status="REGISTERED",
        )

        return {
            "model_name": model_name,
            "version": result.version,
            "run_id": run_id,
            "db_record_id": db_version.id,
            "formatted_size": format_size(file_size),
        }

    @staticmethod
    def list_models() -> list:
        """
        Return all registered models with full enriched metadata.

        Cross-references MLflow registry with local DB and auto-syncs any
        versions that were deleted directly in MLflow.
        """
        client = mlflow.MlflowClient()
        try:
            registered_models = client.search_registered_models()
        except MlflowException as e:
            raise Exception(f"Could not connect to MLflow: {e}") from e

        # Determine which (name, version) pairs are still active in MLflow
        active_name_vers = set()
        for model in registered_models:
            for v in client.search_model_versions(f"name='{model.name}'"):
                active_name_vers.add((model.name, int(v.version)))

        # Sync: remove DB records for versions deleted directly in MLflow
        for mv in ModelVersion.objects.filter(status="REGISTERED").select_related('logical_model'):
            if (mv.logical_model.mlflow_name, int(mv.version_number)) not in active_name_vers:
                mv.delete()

        # Clean up logical models with no remaining versions
        for lm in LogicalModel.objects.all():
            if lm.versions.count() == 0:
                lm.delete()

        # Build a lookup dict: "mlflow_name_version" → ModelVersion
        local_dict = {
            f"{mv.logical_model.mlflow_name}_{mv.version_number}": mv
            for mv in ModelVersion.objects.all().select_related('logical_model')
        }

        results = []
        for rm in registered_models:
            versions = client.search_model_versions(f"name='{rm.name}'")
            versions_data = []
            for mv in versions:
                size_bytes = get_model_size_from_mlflow(client, mv)
                db_record = local_dict.get(f"{rm.name}_{int(mv.version)}")

                # Fall back to DB-stored size if MLflow artifact listing fails
                if size_bytes is None and db_record and db_record.file_size:
                    size_bytes = db_record.file_size

                versions_data.append({
                    "version": int(mv.version),
                    "status": mv.status,
                    "run_id": mv.run_id,
                    "model_uri": mv.source,
                    "creation_timestamp": mv.creation_timestamp,
                    "size_bytes": size_bytes,
                    "formatted_size": format_size(size_bytes),
                    "original_filename": db_record.original_filename if db_record else None,
                    "framework": db_record.file_format if db_record else "Unknown",
                    "model_type": db_record.logical_model.model_type if db_record else "Unknown",
                    "architecture": db_record.architecture if db_record else "",
                    "priority": db_record.priority if db_record else None,
                    "is_deployable": db_record.is_deployable if db_record else False,
                    "deployment_points": db_record.deployment_points if db_record else [],
                    "remarks": db_record.remarks if db_record else "",
                    "accuracy": db_record.accuracy if db_record else 0.0,
                    "db_id": db_record.id if db_record else None,
                })

            versions_data.sort(key=lambda x: x["version"], reverse=True)
            if versions_data:
                results.append({
                    "name": rm.name,
                    "creation_timestamp": rm.creation_timestamp,
                    "all_versions": versions_data,
                })

        return results

    @staticmethod
    def delete_model_version(mlflow_name: str, version: int, db_id: int = None) -> bool:
        """
        Delete a specific model version from:
          1. The MLflow Model Registry
          2. The underlying MLflow run
          3. The local database (ModelVersion + LogicalModel if last version)

        Uses db_id for precise lookup when provided.
        """
        client = mlflow.MlflowClient()

        if db_id:
            qs = ModelVersion.objects.filter(id=db_id)
        else:
            qs = ModelVersion.objects.filter(
                logical_model__mlflow_name=mlflow_name,
                version_number=version,
            )

        mv = qs.select_related('logical_model').first()
        if not mv:
            raise Exception(
                f"ModelVersion not found in local database for {mlflow_name} v{version}"
            )

        run_id = mv.run_id

        try:
            # 1. Delete from MLflow Registry
            client.delete_model_version(name=mlflow_name, version=str(version))

            # Delete the registered model entry if no more versions remain
            remaining = client.search_model_versions(f"name='{mlflow_name}'")
            if not remaining:
                try:
                    client.delete_registered_model(name=mlflow_name)
                except Exception:
                    pass

            # 2. Delete the underlying MLflow run
            if run_id:
                client.delete_run(run_id)

            # 3. Delete local DB records
            lm = mv.logical_model
            mv.delete()
            if lm.versions.count() == 0:
                lm.delete()

            return True

        except Exception as e:
            raise Exception(
                f"Failed to delete model version {mlflow_name} v{version}: {e}"
            ) from e
