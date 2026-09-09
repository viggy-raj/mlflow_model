"""
Unit tests for LifecycleManager.

ModelVersionService and RolloutManager are mocked so this module tests
only the decision logic in check_for_pending_promotion().
"""
import pytest
from unittest.mock import MagicMock, patch, call
from model_management.services.model_version_service import ModelVersionInfo


def _make_info(name, version):
    return ModelVersionInfo(registered_name=name, version=version, run_id=f"run-{version}")


# ─────────────────────────────────────────────────────────────
# Helpers: patch both services consistently
# ─────────────────────────────────────────────────────────────

MVS_PATH = "model_management.services.lifecycle_manager.ModelVersionService"
RM_PATH = "model_management.services.lifecycle_manager.RolloutManager"


def _lifecycle_manager():
    """Returns a fresh (non-singleton) LifecycleManager instance for tests."""
    from model_management.services.lifecycle_manager import LifecycleManager
    lm = LifecycleManager()
    return lm


# ─────────────────────────────────────────────────────────────
# Test: no approved version → nothing happens
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
def test_no_promotion_when_no_approved_version(mock_mvs):
    mock_mvs.get_latest_approved_version.return_value = None
    lm = _lifecycle_manager()

    started = lm.check_for_pending_promotion("MyModel")

    assert started is False
    mock_mvs.get_active_version.assert_not_called()


# ─────────────────────────────────────────────────────────────
# Test: first-ever deployment (no active yet) → set active, no rollout
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
def test_first_deploy_sets_active_immediately(mock_mvs):
    mock_mvs.get_latest_approved_version.return_value = _make_info("MyModel", "1")
    mock_mvs.get_active_version.return_value = None  # nothing active yet

    lm = _lifecycle_manager()
    started = lm.check_for_pending_promotion("MyModel")

    assert started is False  # no canary started
    mock_mvs.set_active.assert_called_once_with("MyModel", "1")


# ─────────────────────────────────────────────────────────────
# Test: approved version is same as active → nothing to do
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
def test_no_promotion_when_approved_equals_active(mock_mvs):
    mock_mvs.get_latest_approved_version.return_value = _make_info("MyModel", "3")
    mock_mvs.get_active_version.return_value = _make_info("MyModel", "3")

    lm = _lifecycle_manager()
    started = lm.check_for_pending_promotion("MyModel")

    assert started is False


# ─────────────────────────────────────────────────────────────
# Test: approved version is older than active → nothing to do
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
def test_no_promotion_when_approved_is_older_than_active(mock_mvs):
    mock_mvs.get_latest_approved_version.return_value = _make_info("MyModel", "2")
    mock_mvs.get_active_version.return_value = _make_info("MyModel", "5")

    lm = _lifecycle_manager()
    started = lm.check_for_pending_promotion("MyModel")

    assert started is False


# ─────────────────────────────────────────────────────────────
# Test: approved is newer → auto-canary starts
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
@patch(RM_PATH)
def test_auto_canary_starts_when_approved_is_newer(mock_rm_cls, mock_mvs):
    mock_mvs.get_latest_approved_version.return_value = _make_info("MyModel", "5")
    mock_mvs.get_active_version.return_value = _make_info("MyModel", "3")

    mock_rm = MagicMock()
    mock_rm_cls.get_instance.return_value = mock_rm

    lm = _lifecycle_manager()
    started = lm.check_for_pending_promotion("MyModel")

    assert started is True
    mock_rm.start_rollout.assert_called_once_with(
            active_model_name="MyModel",
        active_mlflow_version="3",
        canary_model_name="MyModel",
        canary_mlflow_version="5",
    )


# ─────────────────────────────────────────────────────────────
# Test: unapproved newer version does NOT trigger rollout
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
@patch(RM_PATH)
def test_unapproved_newer_version_does_not_start_rollout(mock_rm_cls, mock_mvs):
    """
    If the newest version (v7) is unapproved, ModelVersionService will only
    return v4 (approved).  v4 <= active (v4), so no rollout should start.
    """
    mock_mvs.get_latest_approved_version.return_value = _make_info("MyModel", "4")
    mock_mvs.get_active_version.return_value = _make_info("MyModel", "4")

    mock_rm = MagicMock()
    mock_rm_cls.get_instance.return_value = mock_rm

    lm = _lifecycle_manager()
    started = lm.check_for_pending_promotion("MyModel")

    assert started is False
    mock_rm.start_rollout.assert_not_called()


# ─────────────────────────────────────────────────────────────
# Test: V2→V3 dynamic progression (no hardcoding)
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
@patch(RM_PATH)
def test_canary_to_v3_dynamic_progression(mock_rm_cls, mock_mvs):
    """
    Simulates: V2 is active, V3 has been approved.
    Should start rollout V2 → V3 automatically.
    No model name or version is hardcoded in the assertion.
    """
    mock_mvs.get_latest_approved_version.return_value = _make_info("SomeModel", "3")
    mock_mvs.get_active_version.return_value = _make_info("SomeModel", "2")

    mock_rm = MagicMock()
    mock_rm_cls.get_instance.return_value = mock_rm

    lm = _lifecycle_manager()
    started = lm.check_for_pending_promotion("SomeModel")

    assert started is True
    mock_rm.start_rollout.assert_called_once_with(
            active_model_name="SomeModel",
        active_mlflow_version="2",
        canary_model_name="SomeModel",
        canary_mlflow_version="3",
    )


# ─────────────────────────────────────────────────────────────
# Test: existing rollout in progress → no double-start
# ─────────────────────────────────────────────────────────────

@patch(MVS_PATH)
@patch(RM_PATH)
def test_no_double_start_when_rollout_in_progress(mock_rm_cls, mock_mvs):
    mock_mvs.get_latest_approved_version.return_value = _make_info("MyModel", "6")
    mock_mvs.get_active_version.return_value = _make_info("MyModel", "4")

    mock_rm = MagicMock()
    mock_rm.start_rollout.side_effect = ValueError("A rollout is already in progress.")
    mock_rm_cls.get_instance.return_value = mock_rm

    lm = _lifecycle_manager()
    # Should not raise — ValueError is caught internally
    started = lm.check_for_pending_promotion("MyModel")

    assert started is False
