import mlflow
from typing import Any, Dict, Optional
from django.conf import settings

class ExperimentService:
    """Facade for MLflow operations."""

    def __init__(self):
        mlflow.set_tracking_uri(getattr(settings, 'MLFLOW_TRACKING_URI', 'http://localhost:5000'))

    def get_or_create_experiment(self, name: str) -> str:
        experiment = mlflow.get_experiment_by_name(name)
        if experiment is None:
            return mlflow.create_experiment(name)
        return experiment.experiment_id

    def list_experiments(self) -> list:
        return mlflow.search_experiments()

    def start_run(self, experiment_id: str, run_name: Optional[str] = None) -> mlflow.ActiveRun:
        return mlflow.start_run(experiment_id=experiment_id, run_name=run_name)

    def log_params(self, params: Dict[str, Any]):
        mlflow.log_params(params)

    def log_metrics(self, metrics: Dict[str, Any]):
        mlflow.log_metrics(metrics)



    def list_registered_models(self) -> list:
        client = mlflow.tracking.MlflowClient()
        return client.search_registered_models()
