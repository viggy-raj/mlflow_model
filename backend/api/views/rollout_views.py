from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from model_management.services.rollout_manager import RolloutManager
from ..serializers.rollout_serializers import RolloutStartSerializer

class RolloutStartView(APIView):
    def post(self, request):
        serializer = RolloutStartSerializer(data=request.data)
        if serializer.is_valid():
            rm = RolloutManager.get_instance()
            try:
                state = rm.start_rollout(
                    active_model_name=serializer.validated_data.get('active_model_name'),
                    active_mlflow_version=serializer.validated_data.get('active_mlflow_version'),
                    canary_model_name=serializer.validated_data.get('canary_model_name'),
                    canary_mlflow_version=serializer.validated_data.get('canary_mlflow_version')
                )
                return Response(rm.get_status(), status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RolloutStatusView(APIView):
    def get(self, request):
        rm = RolloutManager.get_instance()
        return Response(rm.get_status())

class RolloutAdvanceView(APIView):
    def post(self, request):
        rm = RolloutManager.get_instance()
        rm.advance_step()
        return Response(rm.get_status())

class RolloutRollbackView(APIView):
    def post(self, request):
        rm = RolloutManager.get_instance()
        try:
            rm.rollback()
            return Response(rm.get_status())
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RolloutLogsView(APIView):
    """
    GET /api/v1/rollout/<id>/logs/
    Returns the prediction logs for a specific rollout, newest first.
    """
    def get(self, request, pk):
        from model_management.models import RolloutState
        from django.shortcuts import get_object_or_404
        from ..serializers.rollout_serializers import PredictionLogSerializer
        
        rollout = get_object_or_404(RolloutState, pk=pk)
        logs = rollout.prediction_logs.order_by('-timestamp')
        serializer = PredictionLogSerializer(logs, many=True)
        return Response(serializer.data)
