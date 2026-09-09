# Inspection Report: Model Replacement Lifecycle & Canary Monitoring

Based on a read-only inspection of the codebase, here is the current state of the requested features and the identified gaps.

## 1. Automated Model Promotion Lifecycle

**Status: Supported (Implemented in the previous phase)**

The full dynamic lifecycle is implemented and covered by unit tests (e.g., `test_lifecycle_manager.py`).

- **V1 active → V2 approved → automatic canary → V2 healthy → V2 active**: Supported. `LifecycleManager` detects V2 > V1, triggers a rollout. If `RolloutManager` completes the rollout successfully (weight reaches 100), `_promote_v2_to_active()` is called, moving the `active` alias to V2 in MLflow.
- **V1 active → V2 approved → automatic canary → V2 errors → automatic rollback → V1 active**: Supported. If V2's error rate exceeds the threshold, `_do_rollback()` is triggered. V2 weight drops to 0, status becomes `ROLLED_BACK`, and the `active` alias remains on V1.
- **V2 active → V3 candidate/unapproved → V3 must not affect production predictions**: Supported. `ModelVersionService.get_latest_approved_version()` only fetches versions with the `approved` alias. Unapproved models are completely ignored by the auto-promotion logic.
- **V3 approved → automatic V2 → V3 canary → successful promotion or rollback**: Supported. The logic is fully dynamic (comparing integer versions) and works for any progression (V2→V3, V5→V6, etc.).

## 2. Prediction and Error Monitoring

**Status: Partially Supported / Significant Gaps Exist**

The user requested detailed monitoring during a canary rollout. Here is how the current implementation stacks up against the requirements:

### Currently Supported
- **Which model version handled the request**: Handled dynamically in `RolloutManager.predict()` (returns the model display name, e.g., `DummyModel/v3`).
- **Prediction returned**: Returned in the API response.
- **Whether the prediction was valid or erroneous**: Evaluated via `_is_valid_prediction()` and returned in the API response.
- **Configured rollback threshold**: Stored on `RolloutState.error_threshold`.

### Identified Gaps (Missing Functionality)
1. **Prediction/Request ID & Individual Logging**:
   - *Missing*: There is no database table (e.g., `PredictionLog`) to record individual prediction events. We cannot currently look back and see what a specific request looked like.
2. **Input used for the prediction**:
   - *Missing*: Inputs are not logged anywhere.
3. **Error reason/type**:
   - *Missing*: The system only flags predictions as valid/invalid based on a boolean check. It does not record *why* it failed (e.g., "Out of bounds", "Type error").
4. **Cumulative requests & Error count per model**:
   - *Gap*: `RolloutState` currently tracks a single global `request_count` and a single `error_count` (which only increments for V2 errors). We need explicit `v1_request_count`, `v1_error_count`, `v2_request_count`, and `v2_error_count` to properly compare the models side-by-side.
5. **Exact point at which automatic rollback was triggered**:
   - *Gap*: While the status changes to `ROLLED_BACK`, there is no record of *why* or exactly *when* (e.g., no `rollback_reason` field on `RolloutState` like "Rollback triggered at request #45: V2 error rate 25% > 20% threshold").

## Next Steps

To satisfy the monitoring requirements, I propose the following implementation plan. Please let me know if you approve:

1.  **Data Layer Updates**:
    *   Add `v1_request_count`, `v1_error_count`, `v2_request_count`, `v2_error_count` fields to `RolloutState`.
    *   Add a `rollback_reason` (TextField) to `RolloutState`.
    *   Create a new `PredictionLog` model (linked to `RolloutState`) to store: Request ID, Timestamp, Model Version used, Input Data (JSON), Output Data (JSON), Is Valid (Boolean), and Error Reason (String).
2.  **Service Layer Updates (`RolloutManager`)**:
    *   Update `predict()` to persist a `PredictionLog` entry for every request.
    *   Update `predict()` to track per-model requests and errors correctly.
    *   Update `advance_step()` to populate `rollback_reason` when triggering an auto-rollback.
3.  **API Layer Updates**:
    *   Update the `/rollout/status/` endpoint to return the new granular metrics and the `rollback_reason`.
    *   Create a new endpoint (e.g., `/rollout/<id>/logs/`) to fetch the detailed prediction logs for UI display.
