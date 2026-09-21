from django.conf import settings
from django.urls import path
from . import views

urlpatterns = [
    # GET  http://127.0.0.1:8000/
    path("", views.register_page, name="register_page"),

    # POST http://127.0.0.1:8000/api/models/register/
    path(settings.REGISTER_MODEL, views.register_model, name="register_model"),

    # GET  http://127.0.0.1:8000/api/models/
    path(settings.LIST_MODELS, views.list_models, name="list_models"),

    # GET  http://127.0.0.1:8000/api/architectures/
    path("api/architectures/", views.architectures_api, name="architectures_api"),

    # DELETE http://127.0.0.1:8000/api/models/<mlflow_name>/version/<version>/
    path(
        "api/models/<str:mlflow_name>/version/<int:version>/",
        views.delete_model,
        name="delete_model",
    ),
]
