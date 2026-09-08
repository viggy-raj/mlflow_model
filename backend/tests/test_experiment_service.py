import pytest
from unittest.mock import patch, MagicMock
from model_management.services.experiment_service import ExperimentService

@patch('model_management.services.experiment_service.mlflow')
def test_get_or_create_experiment(mock_mlflow):
    mock_mlflow.get_experiment_by_name.return_value = None
    mock_mlflow.create_experiment.return_value = "123"
    
    service = ExperimentService()
    exp_id = service.get_or_create_experiment("test_exp")
    
    assert exp_id == "123"
    mock_mlflow.create_experiment.assert_called_once_with("test_exp")
