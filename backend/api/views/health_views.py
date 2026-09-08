from rest_framework.views import APIView
from rest_framework.response import Response

class HealthView(APIView):
    def get(self, request):
        # We could add MLflow/Ozone checks here if needed
        return Response({"status": "ok"})
