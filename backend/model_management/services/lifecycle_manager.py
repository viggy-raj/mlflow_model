"""
LifecycleManager
================
Singleton service that contains the auto-promotion decision logic:

    "If the latest APPROVED version of a model is numerically newer than
     the currently ACTIVE version, automatically start a canary rollout
     from the active version to the approved version."

This is the only place the comparison and trigger live.
It delegates all MLflow queries to ModelVersionService and all rollout
mechanics to RolloutManager.
"""
import logging
import threading
from typing import Optional

from django.conf import settings

from .model_version_service import ModelVersionService
from .rollout_manager import RolloutManager

logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    Singleton that auto-detects pending promotions and triggers rollouts.

    Call check_for_pending_promotion(registered_name) after:
      - A model version is approved (POST /api/v1/models/approve/).
      - Server startup (to catch approvals that happened while the server was down).
    """

    _instance: Optional["LifecycleManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._mvs = ModelVersionService()

    @classmethod
    def get_instance(cls) -> "LifecycleManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LifecycleManager()
        return cls._instance

    def check_for_pending_promotion(self, registered_name: str) -> bool:
        """
        Compares the latest APPROVED version against the currently ACTIVE version
        for the given MLflow registered model name.

        Rules:
        1. If no approved version exists → do nothing.
        2. If no active version exists → first-ever deployment: set it as active
           immediately without a canary (no previous baseline to protect).
        3. If approved.version <= active.version → already promoted or same
           version; do nothing.
        4. If approved.version > active.version → start a canary rollout from
           active → approved.

        Returns True if a new rollout was started, False otherwise.
        """

        approved = ModelVersionService.get_latest_approved_version(registered_name)
        if approved is None:
            logger.debug("No approved version for '%s'; nothing to do.", registered_name)
            return False

        active = ModelVersionService.get_active_version(registered_name)

        if active is None:
            # First-ever deployment: promote immediately, no canary needed.
            logger.info(
                "No active version for '%s'. Marking v%s as active immediately.",
                registered_name, approved.version
            )
            ModelVersionService.set_active(registered_name, approved.version)
            return False  # no rollout started, but lifecycle advanced

        if int(approved.version) <= int(active.version):
            logger.debug(
                "Approved v%s is not newer than active v%s for '%s'; nothing to do.",
                approved.version, active.version, registered_name
            )
            return False

        # Approved is strictly newer → start the canary rollout.
        rm = RolloutManager.get_instance()
        try:
            rm.start_rollout(
                active_model_name=registered_name,
                active_mlflow_version=active.version,
                canary_model_name=registered_name,
                canary_mlflow_version=approved.version,
            )
            logger.info(
                "Auto-started canary rollout for '%s': v%s → v%s",
                registered_name, active.version, approved.version
            )
            return True
        except ValueError as exc:
            # A rollout is already in progress — do not interrupt it.
            logger.warning(
                "Could not start rollout for '%s' v%s → v%s: %s",
                registered_name, active.version, approved.version, exc
            )
            return False

    def check_for_pending_promotion_all(self) -> None:
        """
        Checks every registered model name in the MLflow registry for a
        pending promotion.  Called on server startup to catch approvals that
        occurred while the server was offline.
        """
        names = ModelVersionService.get_all_registered_names()
        for name in names:
            try:
                self.check_for_pending_promotion(name)
            except Exception as exc:
                logger.error("Error checking lifecycle for '%s': %s", name, exc)
