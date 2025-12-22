
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const rootElement = document.getElementById('root');

// Global error handler to catch "white screen" issues
window.onerror = function (message, source, lineno, colno, error) {
  if (rootElement) {
    rootElement.innerHTML = `
      <div style="color: #721c24; background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; font-family: sans-serif; margin: 20px; border-radius: 8px;">
        <h2 style="margin-top: 0;">Application Crashed</h2>
        <p><strong>Error:</strong> ${message}</p>
        <p><strong>Location:</strong> ${source}:${lineno}:${colno}</p>
        <pre style="background: rgba(0,0,0,0.05); padding: 10px; overflow: auto; margin-top: 10px;">${error?.stack || 'No stack trace'}</pre>
        <p style="margin-top: 20px; font-size: 0.9em; color: #666;">Please share this error with the developer.</p>
      </div>
    `;
  }
};

if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
