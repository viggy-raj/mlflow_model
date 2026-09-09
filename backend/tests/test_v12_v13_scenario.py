import pytest
from unittest.mock import patch, MagicMock
from model_management.services.lifecycle_manager import LifecycleManager
from model_management.services.model_version_service import ModelVersionInfo
from model_management.services.rollout_manager import RolloutManager
from model_management.models import RolloutState

@pytest.fixture
def rm():
    manager = RolloutManager.get_instance()
    manager.state = None
    if manager.timer:
        manager.timer.cancel()
    RolloutState.objects.all().delete()
    return manager

@pytest.mark.django_db
@patch("model_management.services.model_version_service.ModelVersionService.get_active_version")
@patch("model_management.services.model_version_service.ModelVersionService.get_latest_approved_version")
@patch("model_management.services.model_version_service.ModelVersionService.set_active")
def test_v12_v13_bad_model_scenario(mock_set_active, mock_approved, mock_active, settings, rm):
    settings.ROLLOUT_STEP_SIZE = 10
    settings.ROLLOUT_INTERVAL_SECONDS = 5
    settings.ROLLOUT_ERROR_THRESHOLD = 0.20

    # Simulate: v12 is ACTIVE
    mock_active.return_value = ModelVersionInfo("DummyModel", "12", "run12")
    
    # Simulate: v13 is APPROVED
    mock_approved.return_value = ModelVersionInfo("DummyModel", "13", "run13")

    # Approve v13
    lm = LifecycleManager.get_instance()
    started = lm.check_for_pending_promotion("DummyModel")
    
    assert started is True
    
    # Immediately check status
    status = rm.get_status()
    
    assert status["status"] == "ROLLING_OUT"
    assert status["active_mlflow_version"] == "12"
    assert status["canary_mlflow_version"] == "13"
    assert status["canary_weight"] == 10
    assert status["active_weight"] == 90
    
    # Force canary traffic to test failure logging
    rm.state.canary_weight = 100
    rm.state.save()

    # Generate bad canary prediction
    with patch("mlflow.pyfunc.load_model") as mock_load:
        mock_model = MagicMock()
        mock_model.predict.return_value = -1.5 # Invalid
        mock_load.return_value = mock_model
        
        result = rm.predict([0.5, 0.2])
        
    assert result["is_canary"] is True
    assert result["valid"] is False
    
    rm.state.refresh_from_db()
    
    # 1 canary request, 1 error = 100% error rate
    assert rm.state.canary_request_count == 1
    assert rm.state.canary_error_count == 1
    
    # Rollback should be immediate without advance_step
    status = rm.get_status()
    assert status["status"] == "ROLLED_BACK"
    assert status["active_mlflow_version"] == "12"
    assert status["active_weight"] == 100
    assert status["canary_mlflow_version"] == "13"
    assert status["canary_weight"] == 0
    assert status["triggering_failure"] is not None
    assert status["triggering_failure"]["is_valid"] is False
    assert status["triggering_failure"]["prediction_result"] == -1.5
    
    # Assert v12 was re-asserted as ACTIVE
    mock_set_active.assert_called_with("DummyModel", "12")


@pytest.mark.django_db
@patch("model_management.services.model_version_service.ModelVersionService.get_active_version")
@patch("model_management.services.model_version_service.ModelVersionService.get_latest_approved_version")
@patch("model_management.services.model_version_service.ModelVersionService.set_active")
def test_v12_v14_successful_scenario(mock_set_active, mock_approved, mock_active, settings, rm):
    settings.ROLLOUT_STEP_SIZE = 50
    settings.ROLLOUT_INTERVAL_SECONDS = 5
    settings.ROLLOUT_ERROR_THRESHOLD = 0.20

    # Simulate: v12 is ACTIVE
    mock_active.return_value = ModelVersionInfo("DummyModel", "12", "run12")
    
    # Simulate: v14 is APPROVED
    mock_approved.return_value = ModelVersionInfo("DummyModel", "14", "run14")

    # Approve v14
    lm = LifecycleManager.get_instance()
    lm.check_for_pending_promotion("DummyModel")
    
    status = rm.get_status()
    assert status["status"] == "ROLLING_OUT"
    assert status["active_mlflow_version"] == "12"
    assert status["canary_mlflow_version"] == "14"
    assert status["canary_weight"] == 50
    
    # Advance to 100
    rm.advance_step()
    
    status = rm.get_status()
    assert status["status"] == "COMPLETE"
    assert status["canary_mlflow_version"] == "14"
    assert status["canary_weight"] == 100
    assert status["active_weight"] == 0
    
    # Assert v14 was promoted to ACTIVE
    mock_set_active.assert_called_with("DummyModel", "14")
