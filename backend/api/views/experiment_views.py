import mlflow
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from model_management.services.experiment_service import ExperimentService
from ..serializers.experiment_serializers import ExperimentCreateSerializer

class ExperimentListView(APIView):
    def get(self, request):
        service = ExperimentService()
        experiments = service.list_experiments()
        data = [{"id": e.experiment_id, "name": e.name, "stage": e.lifecycle_stage} for e in experiments]
        return Response(data)

    def post(self, request):
        serializer = ExperimentCreateSerializer(data=request.data)
        if serializer.is_valid():
            service = ExperimentService()
            exp_id = service.get_or_create_experiment(serializer.validated_data['name'])
            return Response({"experiment_id": exp_id}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ExperimentRunListView(APIView):
    def get(self, request, experiment_id):
        # Using native MLflow client to get runs for simplicity
        client = mlflow.tracking.MlflowClient()
        runs = client.search_runs([experiment_id])
        data = [{
            "run_id": r.info.run_id,
            "name": r.info.run_name,
            "status": r.info.status,
            "metrics": r.data.metrics,
            "params": r.data.params,
        } for r in runs]
        return Response(data)

class RunDetailView(APIView):
    def get(self, request, experiment_id, run_id):
        client = mlflow.tracking.MlflowClient()
        try:
            run = client.get_run(run_id)
            data = {
                "run_id": run.info.run_id,
                "name": run.info.run_name,
                "status": run.info.status,
                "metrics": run.data.metrics,
                "params": run.data.params,
            }
            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
