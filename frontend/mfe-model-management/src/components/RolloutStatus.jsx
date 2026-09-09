import React, { useState, useEffect, useCallback } from 'react';
import apiClient from '../api/apiClient';

/* ─── helpers ─────────────────────────────────────────────────────────────── */
const fmt = (ts) => ts ? new Date(ts).toLocaleString() : '—';
const pct = (n) => `${Number(n ?? 0).toFixed(1)}%`;

const COLORS = {
  active:  '#22c55e',   // green-500
  canary:  '#facc15',   // yellow-400
  failed:  '#f87171',   // red-400
  neutral: '#94a3b8',   // slate-400
  bg:      '#0f172a',   // slate-900
  card:    '#1e293b',   // slate-800
  border:  '#334155',   // slate-700
  text:    '#f1f5f9',   // slate-100
  muted:   '#94a3b8',   // slate-400
};

const badge = (label, color) => (
  <span style={{
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: 12,
    background: color,
    color: '#000',
    fontWeight: 700,
    fontSize: 11,
    letterSpacing: 1,
    textTransform: 'uppercase',
  }}>{label}</span>
);

/* ─── sub-components ──────────────────────────────────────────────────────── */

const ModelBar = ({ label, name, version, weight, color }) => (
  <div style={{ marginBottom: 12 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
      <span style={{ color: COLORS.muted, fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</span>
      <span style={{ color, fontWeight: 700 }}>{name} v{version} — {weight}%</span>
    </div>
    <div style={{ background: COLORS.border, borderRadius: 4, height: 8 }}>
      <div style={{ width: `${weight}%`, background: color, height: '100%', borderRadius: 4, transition: 'width 0.6s ease' }} />
    </div>
  </div>
);

const FailedRequestPanel = ({ log }) => {
  if (!log) return null;
  return (
    <div style={{
      margin: '16px 0',
      padding: '16px',
      border: `1px solid ${COLORS.failed}`,
      borderRadius: 8,
      background: '#1a0a0a',
    }}>
      <div style={{ color: COLORS.failed, fontWeight: 700, fontSize: 13, marginBottom: 10, letterSpacing: 1 }}>
        ⛔ FAILED REQUEST — TRIGGERED ROLLBACK
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace', fontSize: 12 }}>
        <tbody>
          {[
            ['Request ID', `#${String(log.request_number).padStart(4, '0')}`],
            ['Timestamp',  fmt(log.timestamp)],
            ['Model',      log.registered_model_name],
            ['MLflow Ver', `v${log.exact_mlflow_version}`],
            ['Input',      JSON.stringify(log.input_data)],
            ['Result',     String(log.prediction_result)],
            ['Status',     'INVALID'],
            ['Error',      log.error_reason],
          ].map(([k, v]) => (
            <tr key={k} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
              <td style={{ color: COLORS.muted, padding: '4px 8px', width: 110 }}>{k}</td>
              <td style={{ color: k === 'Status' ? COLORS.failed : COLORS.text, padding: '4px 8px' }}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const FailedRequestsTable = ({ failures }) => {
  if (!failures || failures.length === 0) return null;
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ color: COLORS.muted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
        Canary Failures ({failures.length})
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace', fontSize: 11 }}>
          <thead>
            <tr style={{ background: COLORS.border }}>
              {['Req#', 'Timestamp', 'Version', 'Input', 'Result', 'Error'].map(h => (
                <th key={h} style={{ padding: '6px 8px', color: COLORS.muted, textAlign: 'left', fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {failures.map((f) => (
              <tr key={f.request_number} style={{ borderBottom: `1px solid ${COLORS.border}`, color: COLORS.failed }}>
                <td style={{ padding: '4px 8px' }}>#{String(f.request_number).padStart(4,'0')}</td>
                <td style={{ padding: '4px 8px' }}>{fmt(f.timestamp)}</td>
                <td style={{ padding: '4px 8px' }}>v{f.exact_mlflow_version}</td>
                <td style={{ padding: '4px 8px' }}>{JSON.stringify(f.input_data)}</td>
                <td style={{ padding: '4px 8px' }}>{String(f.prediction_result)}</td>
                <td style={{ padding: '4px 8px', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.error_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ─── main component ──────────────────────────────────────────────────────── */

const RolloutStatus = () => {
  const [status, setStatus] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await apiClient.get('/rollout/status/');
      setStatus(r.data);
    } catch (e) {
      console.error('Failed to fetch rollout status', e);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 2000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handleSimulateTraffic = async (count = 5) => {
    setSimulating(true);
    setSimResult(null);
    const results = [];
    for (let i = 0; i < count; i++) {
      try {
        const r = await apiClient.post('/predict/', { input_data: [0.5, 0.2] });
        results.push(r.data);
      } catch (e) {
        results.push({ error: String(e) });
      }
    }
    setSimResult(results);
    setSimulating(false);
    await fetchStatus();
  };

  const handleForceRollback = async () => {
    try {
      await apiClient.post('/rollout/rollback/');
      await fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  if (!status) return (
    <div style={{ background: COLORS.bg, padding: 24, borderRadius: 12, color: COLORS.muted, fontFamily: 'monospace' }}>
      Loading rollout status…
    </div>
  );

  const isIdle        = status.status === 'IDLE';
  const isRolling     = status.status === 'ROLLING_OUT';
  const isComplete    = status.status === 'COMPLETE';
  const isRolledBack  = status.status === 'ROLLED_BACK';

  const statusColor = isRolling ? COLORS.canary : isComplete ? COLORS.active : isRolledBack ? COLORS.failed : COLORS.neutral;

  return (
    <div style={{
      background: COLORS.bg,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 12,
      padding: 24,
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      color: COLORS.text,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
          Rollout Status&nbsp;&nbsp;{badge(status.status, statusColor)}
        </h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => handleSimulateTraffic(5)}
            disabled={simulating || isIdle || isRolledBack}
            style={{
              padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 13,
              opacity: (simulating || isIdle || isRolledBack) ? 0.5 : 1,
            }}
          >
            {simulating ? 'Simulating…' : 'Simulate 5 Requests'}
          </button>
          <button
            onClick={handleForceRollback}
            disabled={!isRolling}
            style={{
              padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: COLORS.failed, color: '#fff', fontWeight: 600, fontSize: 13,
              opacity: !isRolling ? 0.5 : 1,
            }}
          >
            Force Rollback
          </button>
        </div>
      </div>

      {/* IDLE */}
      {isIdle && (
        <div style={{ color: COLORS.muted, textAlign: 'center', padding: '32px 0', fontSize: 14 }}>
          No active rollout. Train and approve a model to begin.
        </div>
      )}

      {/* COMPLETE — just show active */}
      {isComplete && (
        <div style={{
          padding: 20, background: COLORS.card, borderRadius: 8,
          border: `1px solid ${COLORS.active}`, textAlign: 'center',
        }}>
          <div style={{ color: COLORS.muted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
            Current Active Model
          </div>
          <div style={{ color: COLORS.active, fontWeight: 700, fontSize: 22 }}>
            {status.canary_model_name} v{status.canary_mlflow_version} — 100%
          </div>
          <div style={{ color: COLORS.muted, fontSize: 12, marginTop: 6 }}>
            Canary rollout completed successfully
          </div>
        </div>
      )}

      {/* ROLLING_OUT */}
      {isRolling && (
        <div style={{ background: COLORS.card, borderRadius: 8, padding: 16, border: `1px solid ${COLORS.border}` }}>
          <div style={{ color: COLORS.muted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 }}>
            Canary Rollout In Progress
          </div>
          <ModelBar label="Active"  name={status.active_model_name}  version={status.active_mlflow_version}  weight={status.active_weight}  color={COLORS.active} />
          <ModelBar label="Canary"  name={status.canary_model_name}  version={status.canary_mlflow_version}  weight={status.canary_weight}  color={COLORS.canary} />
          
          {/* Live metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginTop: 16 }}>
            {[
              ['Canary Reqs',   status.canary_request_count],
              ['Canary Errors', status.canary_error_count],
              ['Error Rate',    pct((status.error_rate ?? 0) * 100)],
            ].map(([k, v]) => (
              <div key={k} style={{ background: COLORS.bg, borderRadius: 6, padding: '10px 14px', border: `1px solid ${COLORS.border}` }}>
                <div style={{ color: COLORS.muted, fontSize: 10, textTransform: 'uppercase', marginBottom: 4 }}>{k}</div>
                <div style={{ color: COLORS.text, fontWeight: 700, fontSize: 16 }}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{ color: COLORS.muted, fontSize: 11, marginTop: 8, textAlign: 'right' }}>
            Threshold: 20.0%  •  Step: {status.rollout_id ? `Rollout #${status.rollout_id}` : ''}
          </div>

          {/* Canary failures table while still rolling */}
          {status.canary_failures?.length > 0 && (
            <FailedRequestsTable failures={status.canary_failures} />
          )}
        </div>
      )}

      {/* ROLLED_BACK */}
      {isRolledBack && (
        <div>
          {/* Traffic bars */}
          <div style={{ background: COLORS.card, borderRadius: 8, padding: 16, border: `1px solid ${COLORS.border}`, marginBottom: 12 }}>
            <ModelBar label="Active (Restored)" name={status.active_model_name} version={status.active_mlflow_version} weight={status.active_weight} color={COLORS.active} />
            <ModelBar label="Failed Canary"     name={status.canary_model_name} version={status.canary_mlflow_version} weight={status.canary_weight} color={COLORS.failed} />
          </div>

          {/* Triggering failure */}
          <FailedRequestPanel log={status.triggering_failure} />

          {/* Rollback summary */}
          <div style={{
            background: '#1a0a0a',
            border: `1px solid ${COLORS.failed}`,
            borderRadius: 8,
            padding: 16,
            marginBottom: 12,
          }}>
            <div style={{ color: COLORS.failed, fontWeight: 700, fontSize: 13, marginBottom: 10, letterSpacing: 1 }}>
              ⚠ AUTOMATIC ROLLBACK
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10 }}>
              {[
                ['Canary Requests',  status.canary_request_count],
                ['Canary Errors',    status.canary_error_count],
                ['Error Rate',       pct((status.error_rate ?? 0) * 100)],
                ['Threshold',        '20.0%'],
              ].map(([k, v]) => (
                <div key={k} style={{ background: COLORS.bg, borderRadius: 6, padding: '10px 14px', border: `1px solid ${COLORS.border}` }}>
                  <div style={{ color: COLORS.muted, fontSize: 10, textTransform: 'uppercase', marginBottom: 4 }}>{k}</div>
                  <div style={{ color: COLORS.text, fontWeight: 700, fontSize: 15 }}>{v}</div>
                </div>
              ))}
            </div>
            {status.rollback_reason && (
              <div style={{ color: COLORS.muted, fontSize: 12, marginTop: 10, fontFamily: 'monospace' }}>
                {status.rollback_reason}
              </div>
            )}
          </div>

          {/* All canary failures table */}
          {status.canary_failures?.length > 0 && (
            <FailedRequestsTable failures={status.canary_failures} />
          )}
        </div>
      )}

      {/* Last simulate result */}
      {simResult && (
        <div style={{ marginTop: 16, background: COLORS.card, borderRadius: 8, padding: 12, border: `1px solid ${COLORS.border}` }}>
          <div style={{ color: COLORS.muted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>Last Simulate Results</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {simResult.map((r, i) => (
              <div key={i} style={{
                padding: '4px 10px',
                borderRadius: 4,
                background: r.valid === false ? '#3b1111' : '#0d2a1a',
                border: `1px solid ${r.valid === false ? COLORS.failed : COLORS.active}`,
                color: r.valid === false ? COLORS.failed : COLORS.active,
                fontFamily: 'monospace',
                fontSize: 11,
              }}>
                {r.model} → {r.result !== undefined ? Number(r.result).toFixed(4) : 'err'}
                &nbsp;{r.valid === false ? '✗' : '✓'}
                {r.is_canary ? ' [C]' : ' [A]'}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default RolloutStatus;
