from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class TimeStampedModel(models.Model):
    """
    Abstract base class following Pattern 1 from OOP Extensibility Guide.
    Provides standard timestamp fields for inherited models.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LogicalModel(TimeStampedModel):
    """
    Represents the logical model identity.
    Multiple versions of the same model exist under this logical model.
    """
    name = models.CharField(max_length=255, unique=True)
    model_type = models.CharField(max_length=100)
    mlflow_name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class ModelVersion(TimeStampedModel):
    """
    Represents a specific version of a logical model.
    Stores all version-specific metadata and artifact references.
    """
    logical_model = models.ForeignKey(
        LogicalModel, on_delete=models.CASCADE, related_name='versions'
    )
    version_number = models.IntegerField()

    # Version-specific metadata
    architecture = models.CharField(max_length=100, blank=True)
    accuracy = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    priority = models.IntegerField(null=True, blank=True)
    is_deployable = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)
    deployment_points = models.JSONField(default=list)

    # Artifact metadata
    original_filename = models.CharField(max_length=255)
    file_format = models.CharField(max_length=20)
    file_size = models.PositiveBigIntegerField()

    # MLflow metadata
    run_id = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default="PENDING")

    def __str__(self):
        return f"{self.logical_model.name} v{self.version_number}"
