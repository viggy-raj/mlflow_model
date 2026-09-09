"""
Unit tests for ModelVersionService.

All MLflow calls are mocked — no real MLflow server needed.
Tests cover alias path (MLflow ≥ 2.3) and tag fallback path.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from model_management.services.model_version_service import (
    ModelVersionService, ModelVersionInfo, ALIAS_APPROVED, ALIAS_ACTIVE,
    TAG_APPROVED, TAG_ACTIVE,
)


def _make_mv(version: str, run_id: str = "run-abc", tags: dict = None):
    """Helper: creates a mock ModelVersion object."""
    mv = MagicMock()
    mv.version = version
    mv.run_id = run_id
    mv.tags = tags or {}
    return mv


# ─────────────────────────────────────────────────────────────
# get_latest_approved_version — alias path
# ─────────────────────────────────────────────────────────────

@patch("model_management.services.model_version_service._mlflow_client")
def test_get_latest_approved_via_alias(mock_client_fn):
    """Alias path: returns ModelVersionInfo for the aliased version."""
    client = MagicMock()
    client.get_model_version_by_alias.return_value = _make_mv("5", "run-5")
    mock_client_fn.return_value = client

    result = ModelVersionService.get_latest_approved_version("MyModel")

    assert result == ModelVersionInfo("MyModel", "5", "run-5")
    client.get_model_version_by_alias.assert_called_once_with("MyModel", ALIAS_APPROVED)


@patch("model_management.services.model_version_service._mlflow_client")
def test_get_latest_approved_returns_none_when_no_alias(mock_client_fn):
    """When neither alias nor tag exists, returns None."""
    from mlflow.exceptions import MlflowException
    client = MagicMock()
    client.get_model_version_by_alias.side_effect = MlflowException("no alias")
    client.search_model_versions.return_value = []  # no tag-approved versions
    mock_client_fn.return_value = client

    result = ModelVersionService.get_latest_approved_version("MyModel")

    assert result is None


@patch("model_management.services.model_version_service._mlflow_client")
def test_get_latest_approved_via_tag_fallback(mock_client_fn):
    """Tag fallback: when alias fails, picks the highest version tagged approved."""
    from mlflow.exceptions import MlflowException
    client = MagicMock()
    client.get_model_version_by_alias.side_effect = MlflowException("no alias")
    client.search_model_versions.return_value = [
        _make_mv("2", "run-2", {TAG_APPROVED: "true"}),
        _make_mv("4", "run-4", {TAG_APPROVED: "true"}),
        _make_mv("5", "run-5", {}),  # not approved
    ]
    mock_client_fn.return_value = client

    result = ModelVersionService.get_latest_approved_version("MyModel")

    # Should pick version 4, the highest approved
    assert result.version == "4"
    assert result.run_id == "run-4"


# ─────────────────────────────────────────────────────────────
# Unapproved version must not be selected
# ─────────────────────────────────────────────────────────────

@patch("model_management.services.model_version_service._mlflow_client")
def test_unapproved_newer_version_not_selected(mock_client_fn):
    """
    If version 5 is unapproved and version 3 is approved, must return v3.
    An unapproved version must never outrank an approved one.
    """
    from mlflow.exceptions import MlflowException
    client = MagicMock()
    client.get_model_version_by_alias.side_effect = MlflowException("no alias")
    client.search_model_versions.return_value = [
        _make_mv("3", "run-3", {TAG_APPROVED: "true"}),
        _make_mv("5", "run-5", {}),  # newer but NOT approved
    ]
    mock_client_fn.return_value = client

    result = ModelVersionService.get_latest_approved_version("MyModel")
    assert result.version == "3"


# ─────────────────────────────────────────────────────────────
# get_active_version
# ─────────────────────────────────────────────────────────────

@patch("model_management.services.model_version_service._mlflow_client")
def test_get_active_version_via_alias(mock_client_fn):
    client = MagicMock()
    client.get_model_version_by_alias.return_value = _make_mv("3", "run-3")
    mock_client_fn.return_value = client

    result = ModelVersionService.get_active_version("MyModel")

    assert result == ModelVersionInfo("MyModel", "3", "run-3")
    client.get_model_version_by_alias.assert_called_once_with("MyModel", ALIAS_ACTIVE)


@patch("model_management.services.model_version_service._mlflow_client")
def test_get_active_version_returns_none_when_none(mock_client_fn):
    from mlflow.exceptions import MlflowException
    client = MagicMock()
    client.get_model_version_by_alias.side_effect = MlflowException("no alias")
    client.search_model_versions.return_value = []
    mock_client_fn.return_value = client

    result = ModelVersionService.get_active_version("MyModel")
    assert result is None


# ─────────────────────────────────────────────────────────────
# set_approved / set_active — alias path
# ─────────────────────────────────────────────────────────────

@patch("model_management.services.model_version_service._mlflow_client")
def test_set_approved_calls_alias(mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client

    ModelVersionService.set_approved("MyModel", "7")

    client.set_registered_model_alias.assert_called_once_with("MyModel", ALIAS_APPROVED, "7")


@patch("model_management.services.model_version_service._mlflow_client")
def test_set_active_calls_alias(mock_client_fn):
    client = MagicMock()
    mock_client_fn.return_value = client

    ModelVersionService.set_active("MyModel", "7")

    client.set_registered_model_alias.assert_called_once_with("MyModel", ALIAS_ACTIVE, "7")


# ─────────────────────────────────────────────────────────────
# get_all_registered_names
# ─────────────────────────────────────────────────────────────

@patch("model_management.services.model_version_service._mlflow_client")
def test_get_all_registered_names(mock_client_fn):
    client = MagicMock()
    m1 = MagicMock(); m1.name = "ModelA"
    m2 = MagicMock(); m2.name = "ModelB"
    client.search_registered_models.return_value = [m1, m2]
    mock_client_fn.return_value = client

    names = ModelVersionService.get_all_registered_names()
    assert names == ["ModelA", "ModelB"]
