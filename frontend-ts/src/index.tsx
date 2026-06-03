import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { atelierTheme } from './theme/atelier-theme';

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
root.render(
  <React.StrictMode>
    <ConfigProvider theme={atelierTheme}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);

reportWebVitals();
