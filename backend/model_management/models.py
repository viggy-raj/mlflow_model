from django.db import models
from django.utils import timezone


class RolloutState(models.Model):
    STATUS_CHOICES = [
        ('IDLE', 'Idle'),
        ('ROLLING_OUT', 'Rolling Out'),
        ('COMPLETE', 'Complete'),
        ('ROLLED_BACK', 'Rolled Back'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IDLE')

    # Explicit MLflow registered model name and version for each side of the canary.
    active_model_name = models.CharField(max_length=200, null=True, blank=True)
    active_mlflow_version = models.CharField(max_length=20, null=True, blank=True)
    canary_model_name = models.CharField(max_length=200, null=True, blank=True)
    canary_mlflow_version = models.CharField(max_length=20, null=True, blank=True)

    active_weight = models.IntegerField(default=100)
    canary_weight = models.IntegerField(default=0)

    active_request_count = models.IntegerField(default=0)
    active_error_count = models.IntegerField(default=0)
    canary_request_count = models.IntegerField(default=0)
    canary_error_count = models.IntegerField(default=0)

    request_count = models.IntegerField(default=0)  # global total
    error_count = models.IntegerField(default=0)    # global canary error total

    step_size = models.IntegerField(default=10)
    interval_sec = models.IntegerField(default=5)
    error_threshold = models.FloatField(default=0.20)

    rollback_reason = models.TextField(null=True, blank=True)

    # FK to the specific PredictionLog that pushed the error rate over threshold.
    # Set to null until rollback is triggered.
    triggering_failure = models.ForeignKey(
        'PredictionLog',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='caused_rollback',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rollout {self.id} ({self.status})"


class PredictionLog(models.Model):
    """Stores a record of every prediction made during a rollout."""
    rollout = models.ForeignKey(
        RolloutState,
        related_name='prediction_logs',
        on_delete=models.CASCADE,
    )
    # Sequential request number within this rollout (1-based).
    request_number = models.PositiveIntegerField(default=0)

    timestamp = models.DateTimeField(auto_now_add=True)

    registered_model_name = models.CharField(max_length=200, null=True, blank=True)
    exact_mlflow_version = models.CharField(max_length=20, null=True, blank=True)

    # Whether this prediction was routed to the canary or the active model.
    is_canary = models.BooleanField(default=False)

    input_data = models.JSONField(null=True, blank=True)
    prediction_result = models.JSONField(null=True, blank=True)

    is_valid = models.BooleanField(default=True)
    error_reason = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['request_number']

    def __str__(self):
        slot = "CANARY" if self.is_canary else "ACTIVE"
        return (
            f"Req#{self.request_number} [{slot}] "
            f"{self.registered_model_name} v{self.exact_mlflow_version} "
            f"-> {'OK' if self.is_valid else 'INVALID'}"
        )
