import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { ToastProvider } from './components/Toast';

console.log('index.tsx: Starting React mounting process...');
const rootElement = document.getElementById('root');
if (!rootElement) {
  console.error("index.tsx: Could not find root element to mount to");
  throw new Error("Could not find root element to mount to");
}

console.log('index.tsx: Root element found, creating React root...');
const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </React.StrictMode>
);