from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from model_management.services.rollout_manager import RolloutManager
from ..serializers.rollout_serializers import PredictInputSerializer

class PredictView(APIView):
    def post(self, request):
        serializer = PredictInputSerializer(data=request.data)
        if serializer.is_valid():
            input_data = serializer.validated_data['input_data']
            rm = RolloutManager.get_instance()
            result = rm.predict(input_data)
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
