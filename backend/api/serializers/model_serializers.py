from rest_framework import serializers

class ModelTrainSerializer(serializers.Serializer):
    model_type = serializers.CharField(max_length=100)
    experiment_name = serializers.CharField(max_length=200)
    params = serializers.DictField(required=False, default=dict)
