import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings
from model_management.services.rollout_manager import RolloutManager
from model_management.models import RolloutState

@pytest.fixture
def rollout_manager(db):
    rm = RolloutManager.get_instance()
    # Reset for tests
    rm.state = None
    if rm.timer:
        rm.timer.cancel()
        rm.timer = None
    yield rm
    if rm.timer:
        rm.timer.cancel()

@pytest.mark.django_db
def test_rollout_manager_start(rollout_manager):
    state = rollout_manager.start_rollout("dummy_model", "dummy_model")
    assert state.status == 'ROLLING_OUT'
    assert state.active_weight == 90
    assert state.canary_weight == 10
    
    status = rollout_manager.get_status()
    assert status['status'] == 'ROLLING_OUT'
    assert status['active_weight'] == 90
    assert status['canary_weight'] == 10

@pytest.mark.django_db
def test_rollout_advance_complete(rollout_manager, settings):
    settings.ROLLOUT_STEP_SIZE = 50
    state = rollout_manager.start_rollout("dummy_model", "dummy_model")
    
    rollout_manager.advance_step()
    assert rollout_manager.state.canary_weight == 100
    assert rollout_manager.state.status == 'COMPLETE'
    
    rollout_manager.advance_step()
    assert rollout_manager.state.canary_weight == 100
    assert rollout_manager.state.status == 'COMPLETE'

@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_rollout_rollback_due_to_errors(mock_load, rollout_manager, settings):
    settings.ROLLOUT_ERROR_THRESHOLD = 0.20
    state = rollout_manager.start_rollout("dummy_model", "dummy_model_bad")
    state.canary_weight = 100
    state.save()
    
    mock_model = MagicMock()
    mock_model.predict.return_value = -1.5 # Invalid
    mock_load.return_value = mock_model
    
    # Simulate errors
    rollout_manager.state.canary_request_count = 10
    rollout_manager.state.canary_error_count = 3  # 30% error rate
    rollout_manager.state.save()
    
    # Next predict should trigger rollback
    rollout_manager.predict([0.5])
    
    assert rollout_manager.state.status == 'ROLLED_BACK'
    assert rollout_manager.state.active_weight == 100
    assert rollout_manager.state.canary_weight == 0
    assert "Rollback Trigger: FIRST INVALID CANARY PREDICTION" in rollout_manager.state.rollback_reason

@pytest.mark.django_db
def test_rollout_manager_predict_logging(rollout_manager):
    state = rollout_manager.start_rollout("dummy_model", "dummy_model")
    
    # Predict during rollout
    result = rollout_manager.predict([1.0, 2.0, 3.0])
    
    # Verify PredictionLog is created
    from model_management.models import PredictionLog
    log = PredictionLog.objects.get(rollout=state)
    assert log.input_data == [1.0, 2.0, 3.0]
    assert log.prediction_result == result["result"]
    assert log.is_valid == result["valid"]
    
    # Verify per-model counts
    state.refresh_from_db()
    assert state.request_count == 1
    # either v1 or v2 handled it
    assert state.active_request_count + state.canary_request_count == 1


@pytest.mark.django_db
def test_rollout_complete_calls_set_active(rollout_manager, settings):
    """
    When a lifecycle rollout (with canary_model_name populated) completes,
    _promote_canary_to_active() must call ModelVersionService.set_active().
    """
    from unittest.mock import patch

    settings.ROLLOUT_STEP_SIZE = 100  # complete in a single step
    rollout_manager.start_rollout(
            active_model_name="MyModel",
        active_mlflow_version="2",
        canary_model_name="MyModel",
        canary_mlflow_version="3",
    )

    with patch(
        "model_management.services.rollout_manager.ModelVersionService"
    ) as mock_mvs:
        rollout_manager.advance_step()

    assert rollout_manager.state.status == 'COMPLETE'
    mock_mvs.set_active.assert_called_once_with("MyModel", "3")


@pytest.mark.django_db
def test_rollout_complete_without_mlflow_fields_does_not_call_set_active(rollout_manager, settings):
    """
    A manual rollout (no canary_model_name) must NOT call set_active —
    backward compat must be fully preserved.
    """
    from unittest.mock import patch

    settings.ROLLOUT_STEP_SIZE = 100
    rollout_manager.start_rollout("dummy_model", "dummy_model")  # no mlflow fields

    with patch(
        "model_management.services.rollout_manager.ModelVersionService"
    ) as mock_mvs:
        rollout_manager.advance_step()

    assert rollout_manager.state.status == 'COMPLETE'
    mock_mvs.set_active.assert_not_called()
