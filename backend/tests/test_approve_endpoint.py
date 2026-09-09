"""
Unit tests for the POST /api/v1/models/approve/ endpoint.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


MVS_PATH = "model_management.services.model_version_service.ModelVersionService"
LM_PATH = "model_management.services.lifecycle_manager.LifecycleManager"
RM_PATH = "model_management.services.rollout_manager.RolloutManager"


@pytest.mark.django_db
@patch(RM_PATH)
@patch(LM_PATH)
@patch(MVS_PATH)
def test_approve_endpoint_sets_alias_and_triggers_check(mock_mvs, mock_lm_cls, mock_rm_cls, api_client):
    """
    POST /models/approve/ must:
    1. Call ModelVersionService.set_approved(registered_name, version).
    2. Call LifecycleManager.check_for_pending_promotion(registered_name).
    3. Return HTTP 200 with 'approved' and 'rollout' keys.
    """
    mock_lm = MagicMock()
    mock_lm_cls.get_instance.return_value = mock_lm

    mock_rm = MagicMock()
    mock_rm.get_status.return_value = {"status": "IDLE"}
    mock_rm_cls.get_instance.return_value = mock_rm

    url = reverse('model-approve')
    response = api_client.post(url, {"registered_name": "DummyModel", "version": "3"}, format='json')

    assert response.status_code == 200
    assert response.data["approved"]["registered_name"] == "DummyModel"
    assert response.data["approved"]["version"] == "3"
    assert "rollout" in response.data

    mock_mvs.set_approved.assert_called_once_with("DummyModel", "3")
    mock_lm.check_for_pending_promotion.assert_called_once_with("DummyModel")


@pytest.mark.django_db
def test_approve_endpoint_rejects_missing_fields(api_client):
    """Missing 'version' field must return HTTP 400."""
    url = reverse('model-approve')
    response = api_client.post(url, {"registered_name": "DummyModel"}, format='json')
    assert response.status_code == 400
    assert "version" in response.data


@pytest.mark.django_db
def test_approve_endpoint_rejects_empty_body(api_client):
    """Completely empty body must return HTTP 400."""
    url = reverse('model-approve')
    response = api_client.post(url, {}, format='json')
    assert response.status_code == 400
