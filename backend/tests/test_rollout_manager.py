import pytest
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
    assert state.v1_weight == 100
    assert state.v2_weight == 0
    
    status = rollout_manager.get_status()
    assert status['status'] == 'ROLLING_OUT'
    assert status['v1_weight'] == 100

@pytest.mark.django_db
def test_rollout_advance_complete(rollout_manager, settings):
    settings.ROLLOUT_STEP_SIZE = 50
    state = rollout_manager.start_rollout("dummy_model", "dummy_model")
    
    rollout_manager.advance_step()
    assert rollout_manager.state.v2_weight == 50
    assert rollout_manager.state.status == 'ROLLING_OUT'
    
    rollout_manager.advance_step()
    assert rollout_manager.state.v2_weight == 100
    assert rollout_manager.state.status == 'COMPLETE'

@pytest.mark.django_db
def test_rollout_rollback_due_to_errors(rollout_manager, settings):
    settings.ROLLOUT_ERROR_THRESHOLD = 0.20
    state = rollout_manager.start_rollout("dummy_model", "dummy_model_bad")
    
    # Simulate errors
    rollout_manager.state.request_count = 10
    rollout_manager.state.error_count = 3  # 30% error rate
    rollout_manager.state.save()
    
    # Next advance should trigger rollback
    rollout_manager.advance_step()
    
    assert rollout_manager.state.status == 'ROLLED_BACK'
    assert rollout_manager.state.v1_weight == 100
    assert rollout_manager.state.v2_weight == 0
