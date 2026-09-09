"""
ModelVersionService
===================
Pure query/command facade over MlflowClient for the lifecycle concepts:
  - "approved" alias  → operator has approved this version as a deployment candidate
  - "active"   alias  → this version is currently serving 100% production traffic

Uses MLflow registered-model aliases (MLflow ≥ 2.3).  If the server is older
and aliases are unsupported, falls back transparently to model-version tags
("approved"="true" / "active"="true").

Contains NO business logic — all decisions live in LifecycleManager.
"""
import logging
from dataclasses import dataclass
from typing import Optional, List

import mlflow
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException
from django.conf import settings

logger = logging.getLogger(__name__)

ALIAS_APPROVED = "approved"
ALIAS_ACTIVE = "active"
TAG_APPROVED = "lifecycle.approved"
TAG_ACTIVE = "lifecycle.active"


@dataclass
class ModelVersionInfo:
    """Carries the minimal facts needed by LifecycleManager."""
    registered_name: str
    version: str       # string, e.g. "3"  (MLflow versions are strings)
    run_id: str


def _mlflow_client() -> MlflowClient:
    mlflow.set_tracking_uri(getattr(settings, "MLFLOW_TRACKING_URI", "http://localhost:5000"))
    return MlflowClient()


def _aliases_supported(client: MlflowClient) -> bool:
    """Returns True if the connected MLflow server supports aliases (≥ 2.3)."""
    return hasattr(client, "set_registered_model_alias")


class ModelVersionService:
    """Thin facade over MlflowClient for approval/active lifecycle markers."""

    # ------------------------------------------------------------------ #
    # Reads                                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_latest_approved_version(registered_name: str) -> Optional[ModelVersionInfo]:
        """
        Returns the ModelVersionInfo for the version currently holding the
        'approved' alias (or tag), or None if no version is approved.
        """
        client = _mlflow_client()
        try:
            if _aliases_supported(client):
                mv = client.get_model_version_by_alias(registered_name, ALIAS_APPROVED)
                return ModelVersionInfo(registered_name, mv.version, mv.run_id)
        except MlflowException:
            pass  # alias not set → fall through to tag search

        # Tag-based fallback
        try:
            versions = client.search_model_versions(f"name='{registered_name}'")
            approved = [
                v for v in versions
                if v.tags.get(TAG_APPROVED) == "true"
            ]
            if not approved:
                return None
            # Pick the highest version number
            best = max(approved, key=lambda v: int(v.version))
            return ModelVersionInfo(registered_name, best.version, best.run_id)
        except MlflowException as exc:
            logger.warning("Could not fetch approved versions for %s: %s", registered_name, exc)
            return None

    @staticmethod
    def get_active_version(registered_name: str) -> Optional[ModelVersionInfo]:
        """
        Returns the ModelVersionInfo for the version currently holding the
        'active' alias (or tag), or None if nothing is marked active.
        """
        client = _mlflow_client()
        try:
            if _aliases_supported(client):
                mv = client.get_model_version_by_alias(registered_name, ALIAS_ACTIVE)
                return ModelVersionInfo(registered_name, mv.version, mv.run_id)
        except MlflowException:
            pass

        # Tag-based fallback
        try:
            versions = client.search_model_versions(f"name='{registered_name}'")
            active = [v for v in versions if v.tags.get(TAG_ACTIVE) == "true"]
            if not active:
                return None
            best = max(active, key=lambda v: int(v.version))
            return ModelVersionInfo(registered_name, best.version, best.run_id)
        except MlflowException as exc:
            logger.warning("Could not fetch active version for %s: %s", registered_name, exc)
            return None

    @staticmethod
    def get_all_registered_names() -> List[str]:
        """Returns all registered model names from the MLflow model registry."""
        client = _mlflow_client()
        try:
            return [m.name for m in client.search_registered_models()]
        except MlflowException as exc:
            logger.warning("Could not list registered models: %s", exc)
            return []

    # ------------------------------------------------------------------ #
    # Writes                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_approved(registered_name: str, version: str) -> None:
        """Marks a specific model version as 'approved' for deployment."""
        client = _mlflow_client()
        try:
            if _aliases_supported(client):
                client.set_registered_model_alias(registered_name, ALIAS_APPROVED, version)
                logger.info("Set alias '%s' → version %s for model '%s'",
                            ALIAS_APPROVED, version, registered_name)
                # Also set the status tag for easy visibility
                client.set_model_version_tag(registered_name, version, "lifecycle.status", "APPROVED")
                return
        except MlflowException as exc:
            logger.warning("Alias set failed, falling back to tag: %s", exc)

        # Tag fallback — clear old approved tags first, then set new one
        try:
            all_versions = client.search_model_versions(f"name='{registered_name}'")
            for v in all_versions:
                if v.tags.get(TAG_APPROVED) == "true" and v.version != version:
                    client.delete_model_version_tag(registered_name, v.version, TAG_APPROVED)
            client.set_model_version_tag(registered_name, version, TAG_APPROVED, "true")
            client.set_model_version_tag(registered_name, version, "lifecycle.status", "APPROVED")
            logger.info("Set tag '%s' and status=APPROVED on version %s for model '%s'",
                        TAG_APPROVED, version, registered_name)
        except MlflowException as exc:
            logger.error("Failed to set approved marker on %s v%s: %s",
                         registered_name, version, exc)
            raise

    @staticmethod
    def set_active(registered_name: str, version: str) -> None:
        """Marks a specific model version as 'active' (serving 100% traffic)."""
        client = _mlflow_client()
        try:
            if _aliases_supported(client):
                client.set_registered_model_alias(registered_name, ALIAS_ACTIVE, version)
                logger.info("Set alias '%s' → version %s for model '%s'",
                            ALIAS_ACTIVE, version, registered_name)
                # Also set the status tag for easy visibility
                client.set_model_version_tag(registered_name, version, "lifecycle.status", "ACTIVE")
                return
        except MlflowException as exc:
            logger.warning("Alias set failed, falling back to tag: %s", exc)

        # Tag fallback
        try:
            all_versions = client.search_model_versions(f"name='{registered_name}'")
            for v in all_versions:
                if v.tags.get(TAG_ACTIVE) == "true" and v.version != version:
                    client.delete_model_version_tag(registered_name, v.version, TAG_ACTIVE)
            client.set_model_version_tag(registered_name, version, TAG_ACTIVE, "true")
            client.set_model_version_tag(registered_name, version, "lifecycle.status", "ACTIVE")
            logger.info("Set tag '%s' and status=ACTIVE on version %s for model '%s'",
                        TAG_ACTIVE, version, registered_name)
        except MlflowException as exc:
            logger.error("Failed to set active marker on %s v%s: %s",
                         registered_name, version, exc)
            raise
