from django.apps import AppConfig


class ModelManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'model_management'

    def ready(self):
        import os
        from django.conf import settings

        # Only run the timer in the main worker process, not the reloader
        if os.environ.get('RUN_MAIN') == 'true':
            from .services.rollout_manager import RolloutManager
            from .services.lifecycle_manager import LifecycleManager
            import logging
            logger = logging.getLogger(__name__)

            try:
                # Ensure the DB tables exist before trying to resume
                from django.db import connection
                if 'model_management_rolloutstate' in connection.introspection.table_names():
                    rm = RolloutManager.get_instance()
                    rm.resume_from_db()
                    rm.start_timer_if_active()

                    # Check for any model approvals that happened while the server was down.
                    LifecycleManager.get_instance().check_for_pending_promotion_all()
            except Exception as e:
                logger.error(f"Failed to resume rollout on startup: {e}")
