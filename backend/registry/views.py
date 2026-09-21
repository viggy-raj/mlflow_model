import os
import json
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services import ModelServices
from .models import ModelVersion


def register_page(request):
    """Render the model registration page."""
    return render(request, "register.html")


@csrf_exempt
@require_http_methods(["POST"])
def register_model(request):
    """
    POST /api/models/register/

    Accepts a multipart form with:
      - model         (file)   : .pt or .onnx model file
      - model_name    (str)    : logical model name
      - model_type    (str)    : e.g. "Classification", "Detection"
      - accuracy      (float)  : 0–100
      - architecture  (str)    : e.g. "ResNet50"
      - priority      (int)    : optional ranking
      - is_deployable (bool)   : "true" / "false"
      - versioning    (str)    : default "Auto-increment"
      - remarks       (str)    : free-text notes
      - deployment_points (list): repeated field
    """
    model_file = request.FILES.get("model")
    model_name = request.POST.get("model_name", "").strip()

    if not model_file:
        return JsonResponse(
            {"success": False, "error": "No model file uploaded."}, status=400
        )
    if not model_name:
        return JsonResponse(
            {"success": False, "error": "Model name is required."}, status=400
        )

    ext = model_file.name.lower().rsplit('.', 1)[-1]
    if ext not in {"pt", "onnx"}:
        return JsonResponse(
            {"success": False, "error": "Only .pt and .onnx files are supported."},
            status=400,
        )

    # Parse metadata fields
    model_type = request.POST.get('model_type', 'Unknown').strip()

    try:
        accuracy = float(request.POST.get('accuracy', 0.0))
        if not (0 <= accuracy <= 100):
            return JsonResponse(
                {"success": False, "error": "Accuracy must be between 0 and 100."},
                status=400,
            )
    except ValueError:
        return JsonResponse(
            {"success": False, "error": "Accuracy must be a number."}, status=400
        )

    architecture = request.POST.get('architecture', '').strip()

    priority_str = request.POST.get('priority', '').strip()
    priority = int(priority_str) if priority_str.isdigit() else None

    is_deployable_val = request.POST.get('is_deployable', '').lower()
    is_deployable = is_deployable_val in ('true', 'on', '1')

    versioning = request.POST.get('versioning', 'Auto-increment').strip()
    remarks = request.POST.get('remarks', '').strip()
    deployment_points = request.POST.getlist('deployment_points')

    # Save uploaded file to a temporary scratch directory
    temp_dir = os.path.join(settings.BASE_DIR, 'scratch')
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, model_file.name)

    try:
        with open(file_path, 'wb+') as dest:
            for chunk in model_file.chunks():
                dest.write(chunk)

        result = ModelServices.register_model(
            file_path=file_path,
            original_filename=model_file.name,
            model_name=model_name,
            model_type=model_type,
            accuracy=accuracy,
            file_size=model_file.size,
            architecture=architecture,
            priority=priority,
            is_deployable=is_deployable,
            versioning=versioning,
            deployment_points=deployment_points,
            remarks=remarks,
        )
        return JsonResponse({"success": True, "message": "Model registered successfully.", **result})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@require_http_methods(["GET"])
def list_models(request):
    """
    GET /api/models/

    Returns all registered models with full enriched metadata.
    Auto-syncs any versions deleted directly in MLflow.
    """
    try:
        models = ModelServices.list_models()
    except Exception as err:
        return JsonResponse({"success": False, "error": str(err)}, status=502)

    return JsonResponse({"success": True, "models": models})


@require_http_methods(["GET"])
def architectures_api(request):
    """
    GET /api/architectures/

    Returns the list of distinct architecture strings recorded in the DB.
    Useful for populating filter dropdowns in the frontend.
    """
    try:
        archs = list(
            ModelVersion.objects
            .exclude(architecture='')
            .values_list('architecture', flat=True)
            .distinct()
        )
        return JsonResponse({"success": True, "architectures": archs})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_model(request, mlflow_name, version):
    """
    DELETE /api/models/<mlflow_name>/version/<version>/

    Removes the model version from:
      - The MLflow Model Registry
      - The underlying MLflow run
      - The local database

    Optional JSON body: { "db_id": <int> } for precise DB lookup.
    """
    db_id = None
    if request.body:
        try:
            body = json.loads(request.body)
            db_id = body.get("db_id")
        except (json.JSONDecodeError, AttributeError):
            pass

    try:
        ModelServices.delete_model_version(mlflow_name, version, db_id=db_id)
        return JsonResponse(
            {"success": True, "message": f"Deleted {mlflow_name} v{version} successfully."}
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)