import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { BrowserRouter } from 'react-router-dom';

const container = document.getElementById('root');
const root = createRoot(container);

// This ensures we can run the MFE standalone
root.render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
);
