from rest_framework import serializers


class ModelTrainSerializer(serializers.Serializer):
    model_type = serializers.CharField(max_length=100)
    experiment_name = serializers.CharField(max_length=200)
    params = serializers.DictField(required=False, default=dict)


class ModelApproveSerializer(serializers.Serializer):
    """Validates the body of POST /api/v1/models/approve/."""
    registered_name = serializers.CharField(max_length=200,
                                            help_text="MLflow registered model name, e.g. 'DummyModel'")
    version = serializers.CharField(max_length=20,
                                    help_text="MLflow model version number, e.g. '3'")
