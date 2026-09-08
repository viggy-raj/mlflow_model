from django.urls import path
from .views.experiment_views import ExperimentListView, ExperimentRunListView, RunDetailView
from .views.model_views import ModelListView, ModelTrainView, ActiveModelView
from .views.rollout_views import RolloutStartView, RolloutStatusView, RolloutAdvanceView, RolloutRollbackView
from .views.predict_views import PredictView
from .views.health_views import HealthView

urlpatterns = [
    # Experiments
    path('experiments/', ExperimentListView.as_view(), name='experiment-list'),
    path('experiments/<str:experiment_id>/runs/', ExperimentRunListView.as_view(), name='experiment-run-list'),
    path('experiments/<str:experiment_id>/runs/<str:run_id>/', RunDetailView.as_view(), name='run-detail'),
    
    # Models
    path('models/', ModelListView.as_view(), name='model-list'),
    path('models/train/', ModelTrainView.as_view(), name='model-train'),
    path('models/active/', ActiveModelView.as_view(), name='active-model'),
    
    # Rollout
    path('rollout/start/', RolloutStartView.as_view(), name='rollout-start'),
    path('rollout/status/', RolloutStatusView.as_view(), name='rollout-status'),
    path('rollout/advance/', RolloutAdvanceView.as_view(), name='rollout-advance'),
    path('rollout/rollback/', RolloutRollbackView.as_view(), name='rollout-rollback'),
    
    # Predict
    path('predict/', PredictView.as_view(), name='predict'),
    
    # Health
    path('health/', HealthView.as_view(), name='health'),
]
