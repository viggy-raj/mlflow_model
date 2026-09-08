from rest_framework import serializers

class ExperimentCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)

class RunStartSerializer(serializers.Serializer):
    run_name = serializers.CharField(max_length=200, required=False)
    params = serializers.DictField(required=False)
