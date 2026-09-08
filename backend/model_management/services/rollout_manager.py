import logging
import threading
import random
from typing import Optional, Dict, Any
from django.conf import settings
from .model_registry import ModelRegistry
from ..models import RolloutState

logger = logging.getLogger(__name__)

def _is_valid_prediction(value: Any) -> bool:
    return isinstance(value, (int, float)) and 0.0 <= value <= 1.0

class RolloutManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.timer: Optional[threading.Timer] = None
        self.state: Optional[RolloutState] = None

    @classmethod
    def get_instance(cls) -> 'RolloutManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = RolloutManager()
        return cls._instance

    def resume_from_db(self):
        """Called on app startup to resume any active rollout."""
        active_rollout = RolloutState.objects.filter(status='ROLLING_OUT').last()
        if active_rollout:
            self.state = active_rollout
            logger.info(f"Resumed active rollout {self.state.id} from DB.")
        else:
            # Load the last COMPLETE or ROLLED_BACK state if any
            self.state = RolloutState.objects.order_by('id').last()
            
    def start_timer_if_active(self):
        if self.state and self.state.status == 'ROLLING_OUT':
            self._schedule_next_step()

    def _schedule_next_step(self):
        if self.timer:
            self.timer.cancel()
        
        interval = self.state.interval_sec if self.state else getattr(settings, 'ROLLOUT_INTERVAL_SECONDS', 5)
        self.timer = threading.Timer(interval, self.advance_step)
        self.timer.daemon = True
        self.timer.start()

    def start_rollout(self, v1_model_type: str, v2_model_type: str) -> RolloutState:
        with self._lock:
            # If already rolling out, cancel
            if self.state and self.state.status == 'ROLLING_OUT':
                raise ValueError("A rollout is already in progress.")
                
            self.state = RolloutState.objects.create(
                status='ROLLING_OUT',
                v1_model_type=v1_model_type,
                v2_model_type=v2_model_type,
                v1_weight=100,
                v2_weight=0,
                step_size=getattr(settings, 'ROLLOUT_STEP_SIZE', 10),
                interval_sec=getattr(settings, 'ROLLOUT_INTERVAL_SECONDS', 5),
                error_threshold=getattr(settings, 'ROLLOUT_ERROR_THRESHOLD', 0.20)
            )
            
            self._schedule_next_step()
            return self.state

    def advance_step(self):
        with self._lock:
            if not self.state or self.state.status != 'ROLLING_OUT':
                return
                
            # Check error rate
            error_rate = 0.0
            if self.state.request_count > 0:
                error_rate = self.state.error_count / self.state.request_count
                
            if error_rate > self.state.error_threshold:
                logger.warning(f"Error rate {error_rate:.2f} > threshold {self.state.error_threshold}. Rolling back.")
                self._do_rollback()
                return

            # Advance weights
            if self.state.v2_weight + self.state.step_size >= 100:
                self.state.v2_weight = 100
                self.state.v1_weight = 0
                self.state.status = 'COMPLETE'
                logger.info("Rollout complete.")
            else:
                self.state.v2_weight += self.state.step_size
                self.state.v1_weight -= self.state.step_size
                
            self.state.save()
            
            if self.state.status == 'ROLLING_OUT':
                self._schedule_next_step()

    def _do_rollback(self):
        if self.state:
            self.state.status = 'ROLLED_BACK'
            self.state.v1_weight = 100
            self.state.v2_weight = 0
            self.state.save()

    def rollback(self):
        """Manual rollback"""
        with self._lock:
            if not self.state or self.state.status != 'ROLLING_OUT':
                raise ValueError("No active rollout to rollback.")
            self._do_rollback()

    def get_status(self) -> Dict[str, Any]:
        if not self.state:
            return {"status": "IDLE"}
            
        error_rate = 0.0
        if self.state.request_count > 0:
            error_rate = self.state.error_count / self.state.request_count
            
        return {
            "status": self.state.status,
            "v1_model_type": self.state.v1_model_type,
            "v2_model_type": self.state.v2_model_type,
            "v1_weight": self.state.v1_weight,
            "v2_weight": self.state.v2_weight,
            "error_rate": error_rate,
            "request_count": self.state.request_count,
            "error_count": self.state.error_count,
        }

    def predict(self, input_data: list) -> Dict[str, Any]:
        """Routes prediction to correct model based on current weights and validates result."""
        if not self.state:
            # Fallback if no rollout ever started
            model = ModelRegistry.get_model('dummy_model')
            res = model.predict(input_data)
            return {"result": res, "model": "dummy_model", "valid": _is_valid_prediction(res)}

        with self._lock:
            # Decide routing
            is_v2 = False
            if self.state.status == 'ROLLING_OUT':
                is_v2 = random.random() < (self.state.v2_weight / 100.0)
            elif self.state.status == 'COMPLETE':
                is_v2 = True
                
            model_type = self.state.v2_model_type if is_v2 else self.state.v1_model_type
            
            try:
                import mlflow.pyfunc
                registry_name = "DummyModelBad" if model_type == "dummy_model_bad" else "DummyModel"
                model_uri = f"models:/{registry_name}/latest"
                
                # Pull the artifact directly through MLflow from Ozone
                mlflow_model = mlflow.pyfunc.load_model(model_uri)
                result = mlflow_model.predict(input_data)
                
            except Exception as e:
                logger.error(f"Failed to pull model {model_type} from MLflow: {e}")
                # Local fallback if not yet trained/registered in MLflow
                model = ModelRegistry.get_model('dummy_model')
                model_type = 'dummy_model'
                result = model.predict(input_data)
            is_valid = _is_valid_prediction(result)
            
            # Update metrics if we are in active rollout and routed to V2
            if self.state.status == 'ROLLING_OUT':
                self.state.request_count += 1
                # We only count errors for the NEW model (V2) as the rollback trigger
                if is_v2 and not is_valid:
                    self.state.error_count += 1
                
                # Save occasionally (for demo we save every time, in prod batch it)
                self.state.save(update_fields=['request_count', 'error_count'])

            return {
                "result": result,
                "model": model_type,
                "valid": is_valid
            }
