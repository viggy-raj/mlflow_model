import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';

const RolloutStatus = () => {
  const [status, setStatus] = useState(null);
  
  const fetchStatus = async () => {
    try {
      const response = await apiClient.get('/rollout/status/');
      setStatus(response.data);
    } catch (error) {
      console.error("Failed to fetch rollout status", error);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleSimulateTraffic = async () => {
    try {
      // Send 5 quick predict requests
      await Promise.all(Array(5).fill().map(() => 
        apiClient.post('/predict/', { input_data: [Math.random(), Math.random()] })
      ));
      fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRollback = async () => {
    try {
      await apiClient.post('/rollout/rollback/');
      fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  if (!status) return <div>Loading rollout status...</div>;

  return (
    <div style={{ border: '1px solid #ccc', padding: '1rem', borderRadius: '8px', backgroundColor: '#fff' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Rollout Status: <span style={{ 
          color: status.status === 'ROLLING_OUT' ? 'orange' : 
                 status.status === 'COMPLETE' ? 'green' : 
                 status.status === 'ROLLED_BACK' ? 'red' : 'black' 
        }}>{status.status}</span></h2>
        
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button onClick={handleSimulateTraffic} style={{ padding: '0.5rem', cursor: 'pointer' }}>
            Simulate Traffic
          </button>
          <button onClick={handleRollback} disabled={status.status !== 'ROLLING_OUT'} style={{ padding: '0.5rem', cursor: 'pointer', backgroundColor: '#f44336', color: 'white', border: 'none' }}>
            Force Rollback
          </button>
        </div>
      </div>

      {status.status !== 'IDLE' && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{ display: 'flex', marginBottom: '1rem', height: '30px', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{ width: `${status.v1_weight}%`, backgroundColor: '#e0e0e0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              V1 ({status.v1_model_type}): {status.v1_weight}%
            </div>
            <div style={{ width: `${status.v2_weight}%`, backgroundColor: '#4CAF50', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              V2 ({status.v2_model_type}): {status.v2_weight}%
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
              <strong>Traffic Metrics</strong><br/>
              Total Requests: {status.request_count}<br/>
              Total Errors: {status.error_count}
            </div>
            <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
              <strong>Validation Status</strong><br/>
              Error Rate: {(status.error_rate * 100).toFixed(1)}%<br/>
              Threshold: 20.0%
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RolloutStatus;
