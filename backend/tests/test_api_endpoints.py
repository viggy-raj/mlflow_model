import pytest
from django.urls import reverse
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

def test_health_endpoint(api_client):
    url = reverse('health')
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data == {"status": "ok"}

@pytest.mark.django_db
def test_predict_endpoint_no_rollout(api_client):
    url = reverse('predict')
    response = api_client.post(url, {"input_data": [0.5, 0.5]}, format='json')
    assert response.status_code == 200
    assert "result" in response.data
    assert response.data["model"] == "dummy_model"
    assert response.data["valid"] is True
