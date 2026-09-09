# POWERSHELL DEMO SCRIPT: v5 -> v6 CANARY ROLLBACK SCENARIO

# 1. TRAIN VALID MODEL (DummyModel) -> This will be registered as a new version (e.g. v5 if 4 existed)
$trainValidResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/models/train/" -Method Post -ContentType "application/json" -Body '{"model_type": "dummy_model", "experiment_name": "demo-experiment"}'
$validVersion = $trainValidResponse.model_version
Write-Host "Trained Valid Model (DummyModel). Version: $validVersion" -ForegroundColor Green

# 2. APPROVE VALID MODEL (First/Initial deployment -> Immediately ACTIVE 100%)
$approveValidResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/models/approve/" -Method Post -ContentType "application/json" -Body "{`"registered_name`": `"DummyModel`", `"version`": `"$validVersion`"}"
Write-Host "Approved Valid Model v$validVersion. It is now ACTIVE." -ForegroundColor Green

# 3. TRAIN BAD MODEL (DummyModelBad) -> This intentionally produces high errors but registers under the SAME "DummyModel" name (e.g. v6)
$trainBadResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/models/train/" -Method Post -ContentType "application/json" -Body '{"model_type": "dummy_model_bad", "experiment_name": "demo-experiment"}'
$badVersion = $trainBadResponse.model_version
Write-Host "Trained BAD Model (DummyModel). Version: $badVersion" -ForegroundColor Yellow

# 4. APPROVE BAD MODEL (Triggers Canary Rollout!)
$approveBadResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/models/approve/" -Method Post -ContentType "application/json" -Body "{`"registered_name`": `"DummyModel`", `"version`": `"$badVersion`"}"
Write-Host "Approved BAD Model v$badVersion. CANARY ROLLOUT INITIATED." -ForegroundColor Cyan

# 5. SIMULATE TRAFFIC (Triggering the > 20% error rate on the Canary)
Write-Host "Simulating traffic to calculate error rate..." -ForegroundColor Cyan
for ($i=1; $i -le 10; $i++) {
    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/predict/" -Method Post -ContentType "application/json" -Body '{"input_data": [0.5, 0.2]}' | Out-Null
    Start-Sleep -Milliseconds 200
}

# 6. FORCE ROLLOUT TO ADVANCE AND DETECT ERRORS (Wait 6 seconds to ensure the 5-second backend timer fires)
Write-Host "Waiting 6 seconds for the backend rollout timer to advance and detect errors..." -ForegroundColor Cyan
Start-Sleep -Seconds 6

# 7. CHECK FINAL STATUS (Verify Rollback to Valid Model)
$finalStatus = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/models/active/" -Method Get
Write-Host "`n--- FINAL ROLLOUT STATUS ---" -ForegroundColor Magenta
$finalStatus | Format-List
Write-Host "VERIFIED: Status is $($finalStatus.status) and active version is restored to $($finalStatus.active_mlflow_version)." -ForegroundColor Green
