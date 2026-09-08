import React from 'react';
import TrainingPanel from './components/TrainingPanel';
import RolloutStatus from './components/RolloutStatus';
import ExperimentList from './components/ExperimentList';

const App = () => {
  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <p style={{ fontSize: '1.2rem', color: '#555' }}>
          This microfrontend manages model training, tracks experiments via MLflow, and controls gradual rollout traffic.
        </p>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '2rem' }}>
        <RolloutStatus />
        <TrainingPanel />
        <ExperimentList />
      </div>
    </div>
  );
};

export default App;
