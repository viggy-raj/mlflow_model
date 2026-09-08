import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';

const ExperimentList = () => {
  const [experiments, setExperiments] = useState([]);

  useEffect(() => {
    apiClient.get('/experiments/')
      .then(res => setExperiments(res.data))
      .catch(console.error);
  }, []);

  return (
    <div style={{ border: '1px solid #ccc', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', backgroundColor: '#fff' }}>
      <h2>MLflow Experiments</h2>
      {experiments.length === 0 ? <p>No experiments found.</p> : (
        <ul style={{ listStyleType: 'none', padding: 0 }}>
          {experiments.map(exp => (
            <li key={exp.id} style={{ padding: '0.5rem', borderBottom: '1px solid #eee' }}>
              <strong>{exp.name}</strong> (ID: {exp.id}) - Stage: {exp.stage}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default ExperimentList;
