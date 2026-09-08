import React, { useState } from 'react';
import apiClient from '../api/apiClient';

const TrainingPanel = () => {
  const [modelType, setModelType] = useState('dummy_model');
  const [experimentName, setExperimentName] = useState('demo-experiment');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleTrain = async () => {
    setLoading(true);
    try {
      const response = await apiClient.post('/models/train/', {
        model_type: modelType,
        experiment_name: experimentName,
        params: { epochs: 10, learning_rate: 0.01 }
      });
      setResult(response.data);
    } catch (error) {
      setResult({ error: error.response?.data || error.message });
    }
    setLoading(false);
  };

  const handleStartRollout = async () => {
    setLoading(true);
    try {
      const response = await apiClient.post('/rollout/start/', {
        v1_model_type: 'dummy_model',
        v2_model_type: modelType
      });
      setResult(response.data);
    } catch (error) {
      setResult({ error: error.response?.data || error.message });
    }
    setLoading(false);
  };

  return (
    <div style={{ border: '1px solid #ccc', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', backgroundColor: '#fff' }}>
      <h2>Training & Rollout</h2>
      <div style={{ marginBottom: '1rem' }}>
        <label>
          Model Type:
          <select value={modelType} onChange={e => setModelType(e.target.value)} style={{ marginLeft: '1rem', padding: '0.25rem' }}>
            <option value="dummy_model">dummy_model (Valid)</option>
            <option value="dummy_model_bad">dummy_model_bad (Invalid/Rollback)</option>
          </select>
        </label>
      </div>
      
      <div style={{ marginBottom: '1rem' }}>
        <label>
          Experiment Name:
          <input 
            type="text" 
            value={experimentName} 
            onChange={e => setExperimentName(e.target.value)}
            style={{ marginLeft: '1rem', padding: '0.25rem' }}
          />
        </label>
      </div>
      
      <div style={{ display: 'flex', gap: '1rem' }}>
        <button onClick={handleTrain} disabled={loading} style={{ padding: '0.5rem 1rem', cursor: 'pointer', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px' }}>
          {loading ? 'Processing...' : 'Train Model'}
        </button>
        <button onClick={handleStartRollout} disabled={loading} style={{ padding: '0.5rem 1rem', cursor: 'pointer', backgroundColor: '#2196F3', color: 'white', border: 'none', borderRadius: '4px' }}>
          {loading ? 'Processing...' : 'Start Rollout (V1=dummy -> V2=selected)'}
        </button>
      </div>
      
      {result && (
        <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
          <h4>Result:</h4>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default TrainingPanel;
