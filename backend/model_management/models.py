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
    v1_model_type = models.CharField(max_length=50)
    v2_model_type = models.CharField(max_length=50, null=True, blank=True)
    
    v1_weight = models.IntegerField(default=100)
    v2_weight = models.IntegerField(default=0)
    
    request_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    step_size = models.IntegerField(default=10)
    interval_sec = models.IntegerField(default=5)
    error_threshold = models.FloatField(default=0.20)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rollout {self.id} ({self.status})"
