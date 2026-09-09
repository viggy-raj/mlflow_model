import pytest
from unittest.mock import patch, MagicMock

from model_management.services.rollout_manager import RolloutManager
from model_management.services.lifecycle_manager import LifecycleManager
from model_management.models import RolloutState
from model_management.services.model_version_service import ModelVersionInfo

@pytest.fixture
def rollout_manager():
    rm = RolloutManager.get_instance()
    rm.state = None
    if rm.timer:
        rm.timer.cancel()
    RolloutState.objects.all().delete()
    return rm

@pytest.mark.django_db
@patch('model_management.services.model_version_service.ModelVersionService.get_active_version')
@patch('model_management.services.model_version_service.ModelVersionService.get_latest_approved_version')
@patch('model_management.services.model_version_service.ModelVersionService.set_active')
def test_scenario_v5_v6_rollback(mock_set_active, mock_get_latest_approved, mock_get_active, rollout_manager, settings):
    settings.ROLLOUT_STEP_SIZE = 10
    settings.ROLLOUT_INTERVAL_SECONDS = 5
    settings.ROLLOUT_ERROR_THRESHOLD = 0.20

    # DummyModel v5 = valid ACTIVE
    mock_get_active.return_value = ModelVersionInfo(registered_name="DummyModel", version="5", run_id="run5")
    # DummyModel v6 = bad CANDIDATE is approved
    mock_get_latest_approved.return_value = ModelVersionInfo(registered_name="DummyModel", version="6", run_id="run6")

    # Approve v6 triggers check
    lm = LifecycleManager.get_instance()
    did_start = lm.check_for_pending_promotion("DummyModel")

    assert did_start is True, "Rollout should have started because v6 > v5"

    # v5 remains active, v6 enters canary
    status = rollout_manager.get_status()
    assert status['status'] == 'ROLLING_OUT'
    assert status['active_mlflow_version'] == "5"
    assert status['canary_mlflow_version'] == "6"
    assert status['active_weight'] == 90
    assert status['canary_weight'] == 10

    with patch("mlflow.pyfunc.load_model") as mock_load:
        mock_model = MagicMock()
        mock_model.predict.return_value = -1.5 # Invalid
        mock_load.return_value = mock_model
        
        rollout_manager.state.canary_weight = 100
        rollout_manager.state.save()
        rollout_manager.predict([0.5, 0.2])

    status = rollout_manager.get_status()
    assert status['status'] == 'ROLLED_BACK'
    assert status['active_weight'] == 100
    assert status['canary_weight'] == 0
    assert status['triggering_failure'] is not None
    assert status['triggering_failure']['prediction_result'] == -1.5

    # Ensure we attempted to re-assert active on v5 during rollback
    mock_set_active.assert_called_with("DummyModel", "5")
