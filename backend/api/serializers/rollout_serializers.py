from rest_framework import serializers
from model_management.models import RolloutState, PredictionLog

class RolloutStartSerializer(serializers.Serializer):
    active_model_name = serializers.CharField(max_length=200, required=False)
    active_mlflow_version = serializers.CharField(max_length=20, required=False)
    canary_model_name = serializers.CharField(max_length=200, required=False)
    canary_mlflow_version = serializers.CharField(max_length=20, required=False)

class RolloutStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolloutState
        fields = '__all__'

class PredictInputSerializer(serializers.Serializer):
    input_data = serializers.ListField(child=serializers.FloatField())

class PredictionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionLog
        fields = '__all__'
