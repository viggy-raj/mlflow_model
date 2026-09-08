from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from model_management.services.experiment_service import ExperimentService
from model_management.services.model_registry import ModelRegistry
from ..serializers.model_serializers import ModelTrainSerializer

class ModelListView(APIView):
    def get(self, request):
        service = ExperimentService()
        models = service.list_registered_models()
        data = [{
            "name": m.name,
            "versions": [{"version": v.version, "run_id": v.run_id, "status": v.status} for v in m.latest_versions]
        } for m in models]
        return Response(data)

class ModelTrainView(APIView):
    def post(self, request):
        serializer = ModelTrainSerializer(data=request.data)
        if serializer.is_valid():
            model_type = serializer.validated_data['model_type']
            exp_name = serializer.validated_data['experiment_name']
            params = serializer.validated_data.get('params', {})

            try:
                # 1. Get implementation
                model = ModelRegistry.get_model(model_type)
                metadata = model.get_metadata()
                
                # 2. Setup MLflow run
                exp_service = ExperimentService()
                exp_id = exp_service.get_or_create_experiment(exp_name)
                
                # 3. Train
                with exp_service.start_run(exp_id) as run:
                    run_id = run.info.run_id
                    exp_service.log_params(params)
                    exp_service.log_params(metadata)
                    
                    metrics = model.train(params)
                    exp_service.log_metrics(metrics)
                    
                    # 4. Native MLflow PyFunc Model Wrapper
                    import mlflow.pyfunc
                    class MLflowModelWrapper(mlflow.pyfunc.PythonModel):
                        def __init__(self, inner_model):
                            self.inner_model = inner_model
                        def predict(self, context, model_input):
                            # Handle both raw lists and Pandas DataFrames if MLflow passes them
                            data = model_input
                            if hasattr(model_input, 'values'):
                                data = model_input.values.tolist()
                            return self.inner_model.predict(data)
                            
                    # 5. Log & Register directly in MLflow (pushes to Ozone if configured)
                    model_info = mlflow.pyfunc.log_model(
                        artifact_path="model",
                        python_model=MLflowModelWrapper(model),
                        registered_model_name=metadata['name']
                    )
                    
                return Response({
                    "run_id": run_id,
                    "metrics": metrics,
                    "model_version": model_info.registered_model_version,
                    "artifact_uri": model_info.model_uri,
                    "metadata": metadata
                }, status=status.HTTP_201_CREATED)
                
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                import traceback
                return Response({"error": str(e), "traceback": traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ActiveModelView(APIView):
    def get(self, request):
        # We query RolloutManager for current state
        from model_management.services.rollout_manager import RolloutManager
        rm = RolloutManager.get_instance()
        return Response(rm.get_status())
