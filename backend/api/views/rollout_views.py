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
                    v1_model_type=serializer.validated_data['v1_model_type'],
                    v2_model_type=serializer.validated_data['v2_model_type']
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
