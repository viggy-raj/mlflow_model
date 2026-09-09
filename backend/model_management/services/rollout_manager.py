"""
RolloutManager
==============
Singleton service managing the complete canary rollout lifecycle:

  start_rollout()       — start a new canary rollout
  advance_step()        — timer callback: shift traffic or trigger rollback
  predict()             — route a request to active/canary, log everything
  rollback()            — manual force-rollback
  get_status()          — full status dict including triggering_failure and canary_failures
  resume_from_db()      — called on startup to resume any in-flight rollout
"""
import logging
import threading
import random
import mlflow.pyfunc
from typing import Optional, Dict, Any

from django.conf import settings

from .model_registry import ModelRegistry
from .model_version_service import ModelVersionService
from ..models import RolloutState, PredictionLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_prediction(value: Any) -> bool:
    """A prediction is valid if it is a finite float/int in [0.0, 1.0]."""
    return isinstance(value, (int, float)) and 0.0 <= value <= 1.0


def _build_mlflow_uri(mlflow_name: str, mlflow_version: str) -> str:
    return f"models:/{mlflow_name}/{mlflow_version}"


def _serialize_log(log: "PredictionLog") -> Dict[str, Any]:
    """Return a JSON-safe dict for a PredictionLog entry."""
    return {
        "request_number": log.request_number,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "registered_model_name": log.registered_model_name,
        "exact_mlflow_version": log.exact_mlflow_version,
        "is_canary": log.is_canary,
        "input_data": log.input_data,
        "prediction_result": log.prediction_result,
        "is_valid": log.is_valid,
        "error_reason": log.error_reason,
    }


# ---------------------------------------------------------------------------
# RolloutManager singleton
# ---------------------------------------------------------------------------

class RolloutManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.timer: Optional[threading.Timer] = None
        self.state: Optional[RolloutState] = None

    @classmethod
    def get_instance(cls) -> "RolloutManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = RolloutManager()
        return cls._instance

    # ------------------------------------------------------------------
    # Startup helpers
    # ------------------------------------------------------------------

    def resume_from_db(self):
        """Called on app startup to resume any active rollout."""
        active_rollout = RolloutState.objects.filter(status="ROLLING_OUT").last()
        if active_rollout:
            self.state = active_rollout
            logger.info("Resumed active rollout %s from DB.", self.state.id)
        else:
            self.state = RolloutState.objects.order_by("id").last()

    def start_timer_if_active(self):
        if self.state and self.state.status == "ROLLING_OUT":
            self._schedule_next_step()

    def _schedule_next_step(self):
        if self.timer:
            self.timer.cancel()
        interval = (
            self.state.interval_sec
            if self.state
            else getattr(settings, "ROLLOUT_INTERVAL_SECONDS", 5)
        )
        self.timer = threading.Timer(interval, self.advance_step)
        self.timer.daemon = True
        self.timer.start()

    # ------------------------------------------------------------------
    # Core lifecycle
    # ------------------------------------------------------------------

    def start_rollout(
        self,
        active_model_name: Optional[str] = None,
        active_mlflow_version: Optional[str] = None,
        canary_model_name: Optional[str] = None,
        canary_mlflow_version: Optional[str] = None,
    ) -> RolloutState:
        """Start a new canary rollout. Raises ValueError if one is already running."""
        with self._lock:
            if self.state and self.state.status == "ROLLING_OUT":
                raise ValueError("A rollout is already in progress.")

            step_size_val = getattr(settings, "ROLLOUT_STEP_SIZE", 10)
            self.state = RolloutState.objects.create(
                status="ROLLING_OUT",
                active_model_name=active_model_name,
                active_mlflow_version=active_mlflow_version,
                canary_model_name=canary_model_name,
                canary_mlflow_version=canary_mlflow_version,
                active_weight=100 - step_size_val,
                canary_weight=step_size_val,
                step_size=step_size_val,
                interval_sec=getattr(settings, "ROLLOUT_INTERVAL_SECONDS", 5),
                error_threshold=getattr(settings, "ROLLOUT_ERROR_THRESHOLD", 0.20),
            )
            self._schedule_next_step()
            return self.state

    def advance_step(self):
        """Called by the background timer. Checks canary error rate and advances or rolls back."""
        with self._lock:
            if not self.state:
                return
            
            try:
                self.state.refresh_from_db()
            except Exception:
                pass

            if self.state.status != "ROLLING_OUT":
                return

            # Error rate check is removed. Rollback is triggered synchronously
            # on the first invalid canary prediction inside predict().

            # Advance traffic weights.
            if self.state.canary_weight + self.state.step_size >= 100:
                self.state.canary_weight = 100
                self.state.active_weight = 0
                self.state.status = "COMPLETE"
                logger.info("Rollout complete.")
            else:
                self.state.canary_weight += self.state.step_size
                self.state.active_weight -= self.state.step_size

            self.state.save()

            if self.state.status == "COMPLETE" and self.state.canary_model_name:
                self._promote_canary_to_active()

            if self.state.status == "ROLLING_OUT":
                self._schedule_next_step()



    def _promote_canary_to_active(self):
        """Sets the 'active' MLflow alias on the canary after a successful rollout."""
        try:
            ModelVersionService.set_active(
                self.state.canary_model_name,
                self.state.canary_mlflow_version,
            )
            logger.info(
                "Promoted '%s' v%s to 'active' after successful rollout.",
                self.state.canary_model_name,
                self.state.canary_mlflow_version,
            )
        except Exception as exc:
            logger.error("Failed to promote Canary to active in MLflow: %s", exc)

    def _do_rollback(self):
        """Restore 100% traffic to the active model and mark state as ROLLED_BACK."""
        if self.state:
            self.state.status = "ROLLED_BACK"
            self.state.active_weight = 100
            self.state.canary_weight = 0
            self.state.save()
            logger.info(
                "Rollback complete. Restored 100%% traffic to %s v%s",
                self.state.active_model_name,
                self.state.active_mlflow_version,
            )
            # Re-assert the ACTIVE alias in MLflow so it is not left pointing at canary.
            if self.state.active_model_name and self.state.active_mlflow_version:
                try:
                    ModelVersionService.set_active(
                        self.state.active_model_name,
                        self.state.active_mlflow_version,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to re-assert active alias during rollback: %s", exc
                    )

    def rollback(self):
        """Manual force-rollback."""
        with self._lock:
            if not self.state or self.state.status != "ROLLING_OUT":
                raise ValueError("No active rollout to rollback.")
            self.state.rollback_reason = "Manual rollback requested."
            self._do_rollback()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a complete status dict, including triggering_failure and canary_failures."""
        if not self.state:
            return {"status": "IDLE"}

        canary_error_rate = 0.0
        if self.state.canary_request_count > 0:
            canary_error_rate = (
                self.state.canary_error_count / self.state.canary_request_count
            )

        # Up to 10 canary failures for the UI table.
        canary_failures = list(
            self.state.prediction_logs
            .filter(is_canary=True, is_valid=False)
            .order_by("request_number")
            .values(
                "request_number",
                "timestamp",
                "registered_model_name",
                "exact_mlflow_version",
                "input_data",
                "prediction_result",
                "is_valid",
                "error_reason",
            )[:10]
        )
        for f in canary_failures:
            if f.get("timestamp"):
                f["timestamp"] = f["timestamp"].isoformat()

        # Triggering failure detail.
        triggering_failure = None
        if self.state.triggering_failure_id:
            try:
                triggering_failure = _serialize_log(self.state.triggering_failure)
            except Exception:
                pass

        return {
            "status": self.state.status,
            "rollout_id": self.state.id,
            "active_model_name": self.state.active_model_name,
            "active_mlflow_version": self.state.active_mlflow_version,
            "canary_model_name": self.state.canary_model_name,
            "canary_mlflow_version": self.state.canary_mlflow_version,
            "active_weight": self.state.active_weight,
            "canary_weight": self.state.canary_weight,
            "error_rate": canary_error_rate,
            "request_count": self.state.request_count,
            "error_count": self.state.error_count,
            "active_request_count": self.state.active_request_count,
            "active_error_count": self.state.active_error_count,
            "canary_request_count": self.state.canary_request_count,
            "canary_error_count": self.state.canary_error_count,
            "error_threshold": self.state.error_threshold,
            "rollback_reason": self.state.rollback_reason,
            "triggering_failure": triggering_failure,
            "canary_failures": canary_failures,
        }

    # ------------------------------------------------------------------
    # Prediction routing
    # ------------------------------------------------------------------

    def predict(self, input_data: list) -> Dict[str, Any]:
        """
        Routes one prediction request to the active or canary model according to
        current traffic weights, logs all details, and returns the result.
        """
        if not self.state:
            model = ModelRegistry.get_model("dummy_model")
            res = model.predict(input_data)
            return {
                "result": res,
                "model": "dummy_model",
                "valid": _is_valid_prediction(res),
                "is_canary": False,
                "request_number": None,
                "error_reason": None,
            }

        with self._lock:
            if self.state:
                try:
                    self.state.refresh_from_db()
                except Exception:
                    pass

            # ── Routing decision ────────────────────────────────────────────
            is_canary = False
            if self.state.status == "ROLLING_OUT":
                is_canary = random.random() < (self.state.canary_weight / 100.0)
            elif self.state.status == "COMPLETE":
                is_canary = True  # all traffic to the new model after completion

            # ── Build model URI ─────────────────────────────────────────────
            if self.state.active_model_name:
                mlflow_name = (
                    self.state.canary_model_name
                    if is_canary
                    else self.state.active_model_name
                )
                mlflow_version = (
                    self.state.canary_mlflow_version
                    if is_canary
                    else self.state.active_mlflow_version
                )
                model_uri = _build_mlflow_uri(mlflow_name, mlflow_version)
            else:
                model_uri = "models:/DummyModel/latest"
                mlflow_name = "dummy_model"
                mlflow_version = "latest"

            # ── Load and run the model ──────────────────────────────────────
            error_reason = None
            try:
                loaded = mlflow.pyfunc.load_model(model_uri)
                result = loaded.predict(input_data)
                is_valid = _is_valid_prediction(result)
                if not is_valid:
                    error_reason = (
                        f"Prediction result {result!r} is outside the valid range [0.0, 1.0]"
                    )
            except Exception as exc:
                logger.error(
                    "Failed to load model from MLflow URI '%s': %s", model_uri, exc
                )
                # Local fallback — never block a prediction due to a load failure
                model = ModelRegistry.get_model("dummy_model")
                result = model.predict(input_data)
                is_valid = _is_valid_prediction(result)
                mlflow_name = "dummy_model"
                mlflow_version = "latest"

            # ── Update counters and write prediction log ────────────────────
            if self.state.status == "ROLLING_OUT":
                self.state.request_count += 1
                request_number = self.state.request_count  # 1-based sequential

                if is_canary:
                    self.state.canary_request_count += 1
                    if not is_valid:
                        self.state.error_count += 1
                        self.state.canary_error_count += 1
                else:
                    self.state.active_request_count += 1
                    if not is_valid:
                        self.state.active_error_count += 1

                self.state.save(
                    update_fields=[
                        "request_count",
                        "error_count",
                        "active_request_count",
                        "active_error_count",
                        "canary_request_count",
                        "canary_error_count",
                    ]
                )

                log = PredictionLog.objects.create(
                    rollout=self.state,
                    request_number=request_number,
                    registered_model_name=mlflow_name,
                    exact_mlflow_version=mlflow_version,
                    is_canary=is_canary,
                    input_data=input_data,
                    prediction_result=result,
                    is_valid=is_valid,
                    error_reason=error_reason,
                )
                
                # IMMEDIATE ROLLBACK ON FIRST INVALID CANARY PREDICTION
                if is_canary and not is_valid:
                    self.state.rollback_reason = "Rollback Trigger: FIRST INVALID CANARY PREDICTION"
                    self.state.triggering_failure = log
                    self._do_rollback()
                    if self.timer:
                        self.timer.cancel()

            else:
                request_number = None

            return {
                "result": result,
                "model": f"{mlflow_name} v{mlflow_version}",
                "valid": is_valid,
                "is_canary": is_canary,
                "request_number": request_number,
                "error_reason": error_reason,
            }
