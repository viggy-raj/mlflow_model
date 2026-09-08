from rest_framework import serializers
from model_management.models import RolloutState

class RolloutStartSerializer(serializers.Serializer):
    v1_model_type = serializers.CharField(max_length=100)
    v2_model_type = serializers.CharField(max_length=100)

class RolloutStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolloutState
        fields = '__all__'

class PredictInputSerializer(serializers.Serializer):
    input_data = serializers.ListField(child=serializers.FloatField())
