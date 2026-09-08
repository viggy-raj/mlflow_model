import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Lazy load the remote component
const ModelManagementRemote = React.lazy(() => import('modelManagement/App').catch(() => {
  return { default: () => <div>Failed to load Model Management Microfrontend. Ensure the MFE is running on port 3001.</div> };
}));

const Router = () => {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Routes>
        <Route path="/models/*" element={<ModelManagementRemote />} />
        <Route path="/" element={<Navigate to="/models" replace />} />
      </Routes>
    </Suspense>
  );
};

export default Router;
