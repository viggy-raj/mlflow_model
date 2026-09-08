import React from 'react';
import { Link } from 'react-router-dom';

const Layout = ({ children }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <header style={{ backgroundColor: '#1a1a1a', color: 'white', padding: '1rem', display: 'flex', alignItems: 'center' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', marginRight: '2rem' }}>MLflow Platform (Shell)</h1>
        <nav>
          <Link to="/models" style={{ color: 'white', textDecoration: 'none', padding: '0.5rem 1rem', borderRadius: '4px', backgroundColor: '#333' }}>
            Model Management MFE
          </Link>
        </nav>
      </header>
      
      <main style={{ flex: 1, padding: '2rem' }}>
        {children}
      </main>
      
      <footer style={{ backgroundColor: '#f0f0f0', padding: '1rem', textAlign: 'center', color: '#666' }}>
        &copy; {new Date().getFullYear()} MLflow Platform Demo
      </footer>
    </div>
  );
};

export default Layout;
