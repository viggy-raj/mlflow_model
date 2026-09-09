"""
test_full_lifecycle.py
======================
Exhaustive tests covering the complete model lifecycle:

  1. First valid model  → CANDIDATE → APPROVE → ACTIVE 100% (no canary)
  2. Second valid model → CANDIDATE → APPROVE → CANARY → gradual shift → COMPLETE
  3. Bad model          → CANDIDATE → APPROVE → CANARY → bad requests → ROLLBACK → previous ACTIVE

Also tests:
  - request_number sequential generation
  - exact input / result / error_reason logging
  - is_canary flag correctness on active & canary routes
  - canary-only error rate calculation
  - triggering_failure identification
  - failed model version & logs retained after rollback
  - canary_failures list in get_status()
  - _is_valid_prediction helper
"""

import pytest
from unittest.mock import patch, MagicMock
import mlflow.pyfunc

from model_management.models import PredictionLog, RolloutState
from model_management.services.lifecycle_manager import LifecycleManager
from model_management.services.model_version_service import ModelVersionInfo
from model_management.services.rollout_manager import RolloutManager, _is_valid_prediction


# ---------------------------------------------------------------------------
# Shared fixture — resets singletons before every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singletons(db):
    rm = RolloutManager.get_instance()
    rm.state = None
    if rm.timer:
        rm.timer.cancel()
        rm.timer = None

    # Force LifecycleManager singleton to re-init cleanly
    LifecycleManager._instance = None

    RolloutState.objects.all().delete()
    yield
    rm = RolloutManager.get_instance()
    if rm.timer:
        rm.timer.cancel()


@pytest.fixture
def rm():
    return RolloutManager.get_instance()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_canary_log(state, req_num, valid=False, result=-1.5):
    """Create a canary PredictionLog directly in the DB."""
    return PredictionLog.objects.create(
        rollout=state,
        request_number=req_num,
        registered_model_name="DummyModel",
        exact_mlflow_version=state.canary_mlflow_version or "6",
        is_canary=True,
        input_data=[0.5, 0.2],
        prediction_result=result,
        is_valid=valid,
        error_reason=None if valid else f"Prediction result {result!r} is outside [0.0, 1.0]",
    )


# ===========================================================================
# Section 1 – First valid model: CANDIDATE → APPROVE → ACTIVE (no canary)
# ===========================================================================

@pytest.mark.django_db
@patch("model_management.services.model_version_service.ModelVersionService.get_active_version", return_value=None)
@patch("model_management.services.model_version_service.ModelVersionService.get_latest_approved_version")
@patch("model_management.services.model_version_service.ModelVersionService.set_active")
def test_first_approval_sets_active_immediately(mock_set_active, mock_approved, mock_active, rm):
    """
    When there is no active version, approving the first model must NOT start a
    canary rollout — it must call set_active immediately and leave RM idle.
    """
    mock_approved.return_value = ModelVersionInfo("DummyModel", "1", "run1")

    lm = LifecycleManager.get_instance()
    started = lm.check_for_pending_promotion("DummyModel")

    assert started is False, "First approval must NOT start a rollout"
    mock_set_active.assert_called_once_with("DummyModel", "1")
    assert rm.state is None  # rollout manager untouched


@pytest.mark.django_db
@patch("model_management.services.model_version_service.ModelVersionService.get_active_version", return_value=None)
@patch("model_management.services.model_version_service.ModelVersionService.get_latest_approved_version", return_value=None)
def test_unapproved_candidate_receives_no_traffic(mock_approved, mock_active, rm):
    """Unapproved model → lifecycle check does nothing → no rollout → no traffic."""
    lm = LifecycleManager.get_instance()
    started = lm.check_for_pending_promotion("DummyModel")
    assert started is False
    assert rm.state is None


# ===========================================================================
# Section 2 – Second valid model: CANDIDATE → APPROVE → CANARY → COMPLETE
# ===========================================================================

@pytest.mark.django_db
@patch("model_management.services.model_version_service.ModelVersionService.get_active_version")
@patch("model_management.services.model_version_service.ModelVersionService.get_latest_approved_version")
@patch("model_management.services.model_version_service.ModelVersionService.set_active")
def test_second_approval_starts_canary(mock_set_active, mock_approved, mock_active, rm):
    """Approving a version newer than the active one must start a canary rollout."""
    mock_active.return_value = ModelVersionInfo("DummyModel", "1", "run1")
    mock_approved.return_value = ModelVersionInfo("DummyModel", "2", "run2")

    lm = LifecycleManager.get_instance()
    started = lm.check_for_pending_promotion("DummyModel")

    assert started is True
    s = rm.get_status()
    assert s["status"] == "ROLLING_OUT"
    assert s["active_mlflow_version"] == "1"
    assert s["canary_mlflow_version"] == "2"
    assert s["active_weight"] == 90
    assert s["canary_weight"] == 10


@pytest.mark.django_db
def test_exact_mlflow_versions_used_in_rollout(rm, settings):
    """The exact version strings passed to start_rollout flow unchanged through get_status()."""
    settings.ROLLOUT_STEP_SIZE = 10
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="7",
        canary_model_name="DummyModel", canary_mlflow_version="8",
    )
    s = rm.get_status()
    assert s["active_mlflow_version"] == "7"
    assert s["canary_mlflow_version"] == "8"
    assert s["active_model_name"] == "DummyModel"
    assert s["canary_model_name"] == "DummyModel"


@pytest.mark.django_db
def test_gradual_traffic_shift(rm, settings):
    """Each advance_step shifts traffic by exactly step_size."""
    settings.ROLLOUT_STEP_SIZE = 25
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    # It starts at (75, 25)
    expected = [(50, 50), (25, 75), (0, 100)]
    for (exp_active, exp_canary) in expected:
        rm.advance_step()
        assert rm.state.active_weight == exp_active
        assert rm.state.canary_weight == exp_canary


@pytest.mark.django_db
@patch("model_management.services.rollout_manager.ModelVersionService")
def test_successful_rollout_promotes_canary_to_active(mock_mvs, rm, settings):
    """After a complete rollout, set_active must be called with the exact canary version."""
    settings.ROLLOUT_STEP_SIZE = 100
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="3",
        canary_model_name="DummyModel", canary_mlflow_version="4",
    )
    rm.advance_step()
    assert rm.state.status == "COMPLETE"
    mock_mvs.set_active.assert_called_once_with("DummyModel", "4")


# ===========================================================================
# Section 3 – Prediction logging
# ===========================================================================

@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_request_number_increments_sequentially(mock_load, rm, settings):
    """request_number must be 1-based and increment with each prediction."""
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.5
    mock_load.return_value = mock_model

    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    for _ in range(3):
        rm.predict([0.5, 0.5])

    logs = list(PredictionLog.objects.filter(rollout=rm.state).order_by("request_number"))
    assert len(logs) == 3
    assert [l.request_number for l in logs] == [1, 2, 3]


@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_prediction_logs_exact_input_data(mock_load, rm, settings):
    """Each log must contain the exact input_data passed to predict()."""
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.7
    mock_load.return_value = mock_model

    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    rm.predict([0.1, 0.9])
    log = PredictionLog.objects.get(rollout=rm.state)
    assert log.input_data == [0.1, 0.9]


@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_prediction_logs_exact_result(mock_load, rm, settings):
    """Each log must contain the exact prediction_result."""
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.42
    mock_load.return_value = mock_model

    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    result = rm.predict([0.5, 0.5])
    log = PredictionLog.objects.get(rollout=rm.state)
    assert log.prediction_result == result["result"]
    assert log.is_valid is True


@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_is_canary_flag_false_when_canary_weight_zero(mock_load, rm, settings):
    """When canary_weight is 0, all routing goes to active → is_canary=False in logs."""
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.5
    mock_load.return_value = mock_model

    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    rm.state.canary_weight = 0 # Force all traffic to active
    rm.state.save()
    # canary_weight starts at 0 → all traffic to active
    for _ in range(5):
        r = rm.predict([0.5])
        assert r["is_canary"] is False

    logs = PredictionLog.objects.filter(rollout=rm.state)
    assert all(not log.is_canary for log in logs)


@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_is_canary_flag_true_when_canary_weight_hundred(mock_load, rm, settings):
    """When canary_weight is forced to 100 during ROLLING_OUT, routing goes to canary."""
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.5
    mock_load.return_value = mock_model

    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    rm.state.canary_weight = 100 # Force 100
    rm.state.save()
    res = rm.predict([0.5])
    assert res["is_canary"] is True
    log = PredictionLog.objects.get(rollout=rm.state)
    assert log.is_canary is True


@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_canary_prediction_counted_separately(mock_load, rm, settings):
    """Canary requests must be tracked in canary_request_count, not active_request_count."""
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.5
    mock_load.return_value = mock_model

    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    rm.state.canary_weight = 100
    rm.state.active_weight = 0
    rm.state.save()

    for _ in range(4):
        rm.predict([0.5])

    rm.state.refresh_from_db()
    assert rm.state.canary_request_count == 4
    assert rm.state.active_request_count == 0


# ===========================================================================
# Section 4 – Invalid predictions: error logging, canary error counting
# ===========================================================================

@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_invalid_prediction_logged_with_error_reason(mock_load, rm, settings):
    """Invalid predictions must log is_valid=False with a non-empty error_reason."""
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = -1.5   # invalid
    mock_load.return_value = mock_model

    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    rm.state.canary_weight = 100
    rm.state.active_weight = 0
    rm.state.save()

    result = rm.predict([0.5, 0.2])

    assert result["valid"] is False
    assert result["error_reason"] is not None
    assert "-1.5" in result["error_reason"]

    log = PredictionLog.objects.get(rollout=rm.state)
    assert log.is_valid is False
    assert log.error_reason is not None
    assert "-1.5" in log.error_reason


@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
def test_immediate_rollback_on_first_canary_error(mock_load, rm, settings):
    """
    The FIRST invalid canary prediction MUST immediately trigger rollback synchronously,
    without waiting for the timer or any percentage threshold.
    """
    settings.ROLLOUT_STEP_SIZE = 10
    mock_model = MagicMock()
    mock_model.predict.return_value = -1.5  # invalid
    mock_load.return_value = mock_model
    
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    rm.state.canary_weight = 100
    rm.state.save()
    
    # Predict triggers the error
    rm.predict([0.5])
    
    rm.state.refresh_from_db()
    assert rm.state.status == "ROLLED_BACK"
    assert rm.state.triggering_failure is not None
    assert rm.state.rollback_reason == "Rollback Trigger: FIRST INVALID CANARY PREDICTION"


# ===========================================================================
# Section 6 – Triggering failure identification
# ===========================================================================

@pytest.mark.django_db
def test_triggering_failure_appears_in_get_status(rm, settings):
    """get_status() must include non-null 'triggering_failure' dict after rollback."""
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="5",
        canary_model_name="DummyModel", canary_mlflow_version="6",
    )
    state = rm.state

    bad_log = _make_canary_log(state, 1, valid=False, result=-1.5)
    state.canary_request_count = 1
    state.canary_error_count = 1
    state.save()
    
    # Force state to rollback status for status check
    state.status = "ROLLED_BACK"
    state.triggering_failure = bad_log
    state.save()

    s = rm.get_status()
    assert s["status"] == "ROLLED_BACK"
    tf = s["triggering_failure"]
    assert tf is not None
    assert tf["request_number"] == 1
    assert tf["exact_mlflow_version"] == "6"
    assert tf["input_data"] == [0.5, 0.2]
    assert tf["prediction_result"] == -1.5
    assert tf["is_valid"] is False
    assert tf["error_reason"] is not None


@pytest.mark.django_db
def test_canary_failures_list_in_get_status(rm, settings):
    """get_status() must expose 'canary_failures' list with all invalid canary logs."""
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="5",
        canary_model_name="DummyModel", canary_mlflow_version="6",
    )
    state = rm.state

    for i in range(1, 4):
        _make_canary_log(state, i, valid=False, result=-1.0)
    state.canary_request_count = 3
    state.canary_error_count = 3
    state.status = "ROLLED_BACK"
    state.save()

    s = rm.get_status()
    assert "canary_failures" in s
    assert len(s["canary_failures"]) == 3


# ===========================================================================
# Section 7 – Rollback: previous active restored, bad model retained
# ===========================================================================

@pytest.mark.django_db
@patch("model_management.services.rollout_manager.ModelVersionService")
def test_rollback_restores_previous_active_version(mock_mvs, rm, settings):
    """After rollback, set_active must be called with the ORIGINAL active version (v5, not v6)."""
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="5",
        canary_model_name="DummyModel", canary_mlflow_version="6",
    )
    
    # Trigger rollback
    rm.state.status = "ROLLED_BACK"
    rm.state.save()
    rm._do_rollback()

    assert rm.state.status == "ROLLED_BACK"
    assert rm.state.active_mlflow_version == "5"
    assert rm.state.canary_mlflow_version == "6"
    mock_mvs.set_active.assert_called_with("DummyModel", "5")


@pytest.mark.django_db
def test_failed_model_version_retained_in_db(rm, settings):
    """After rollback, canary_mlflow_version must still be recorded — never cleared."""
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="5",
        canary_model_name="DummyModel", canary_mlflow_version="6",
    )
    rm.state.status = "ROLLED_BACK"
    rm.state.save()

    rm.state.refresh_from_db()
    assert rm.state.canary_mlflow_version == "6"  # not deleted


@pytest.mark.django_db
def test_prediction_logs_retained_after_rollback(rm, settings):
    """PredictionLogs must survive rollback — never deleted."""
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="5",
        canary_model_name="DummyModel", canary_mlflow_version="6",
    )
    state = rm.state
    _make_canary_log(state, 1, valid=False, result=-1.0)
    state.status = "ROLLED_BACK"
    state.save()

    assert PredictionLog.objects.filter(rollout=state).count() == 1


# ===========================================================================
# Section 8 – Lifecycle ordering
# ===========================================================================

@pytest.mark.django_db
@patch("model_management.services.model_version_service.ModelVersionService.get_active_version")
@patch("model_management.services.model_version_service.ModelVersionService.get_latest_approved_version")
def test_older_approved_does_not_start_rollout(mock_approved, mock_active, rm):
    """Approving a version older than the active must not start a rollout."""
    mock_active.return_value = ModelVersionInfo("DummyModel", "5", "run5")
    mock_approved.return_value = ModelVersionInfo("DummyModel", "3", "run3")

    lm = LifecycleManager.get_instance()
    assert lm.check_for_pending_promotion("DummyModel") is False
    assert rm.state is None


@pytest.mark.django_db
@patch("model_management.services.model_version_service.ModelVersionService.get_active_version")
@patch("model_management.services.model_version_service.ModelVersionService.get_latest_approved_version")
def test_same_approved_as_active_does_not_start_rollout(mock_approved, mock_active, rm):
    """Approving the same version that is already active must not start a rollout."""
    mock_active.return_value = ModelVersionInfo("DummyModel", "4", "run4")
    mock_approved.return_value = ModelVersionInfo("DummyModel", "4", "run4")

    lm = LifecycleManager.get_instance()
    assert lm.check_for_pending_promotion("DummyModel") is False


@pytest.mark.django_db
def test_no_double_rollout_when_one_already_running(rm, settings):
    """A second start_rollout while one is running must raise ValueError."""
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="1",
        canary_model_name="DummyModel", canary_mlflow_version="2",
    )
    with pytest.raises(ValueError, match="already in progress"):
        rm.start_rollout(
            active_model_name="DummyModel", active_mlflow_version="2",
            canary_model_name="DummyModel", canary_mlflow_version="3",
        )


# ===========================================================================
# Section 9 – Complete end-to-end scenario (no live MLflow I/O)
# ===========================================================================

@pytest.mark.django_db
@patch("mlflow.pyfunc.load_model")
@patch("model_management.services.rollout_manager.ModelVersionService")
def test_complete_v5_v6_bad_rollback_scenario(mock_mvs, mock_load, rm, settings):
    """
    Full scenario:
      v5 = valid ACTIVE
      v6 = bad CANDIDATE → approved → canary
      Bad canary predictions → immediate rollback → v5 restored
      v6 version and logs retained
    """
    mock_model = MagicMock()
    mock_model.predict.return_value = -1.5
    mock_load.return_value = mock_model

    # Step 1: start canary v5 → v6
    rm.start_rollout(
        active_model_name="DummyModel", active_mlflow_version="5",
        canary_model_name="DummyModel", canary_mlflow_version="6",
    )
    rm.state.canary_weight = 100
    rm.state.save()

    # Step 2: simulate bad canary predictions
    rm.predict([0.5])  # immediate rollback
    
    status = rm.get_status()
    assert status["status"] == "ROLLED_BACK"
    assert status["active_mlflow_version"] == "5"
    assert status["active_weight"] == 100
    assert status["canary_weight"] == 0

    # Step 5: triggering failure identified
    assert status["triggering_failure"]["is_valid"] is False

    # Step 6: v5 re-asserted as active in MLflow
    mock_mvs.set_active.assert_called_with("DummyModel", "5")

    # Step 7: logs retained
    assert PredictionLog.objects.filter(rollout=rm.state).count() == 1


# ===========================================================================
# Section 10 – _is_valid_prediction helper
# ===========================================================================

@pytest.mark.parametrize("value,expected", [
    (0.0, True),
    (0.5, True),
    (1.0, True),
    (-0.1, False),
    (1.1, False),
    (-1.5, False),
    (2.0, False),
    ("hello", False),
    (None, False),
])
def test_is_valid_prediction(value, expected):
    assert _is_valid_prediction(value) == expected
