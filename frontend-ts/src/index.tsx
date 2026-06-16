import React from 'react';
import ReactDOM from 'react-dom/client';
import * as Sentry from '@sentry/react';
import { ConfigProvider } from 'antd';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { atelierTheme } from './theme/atelier-theme';

const DEFAULT_SENTRY_DSN =
  'https://DYwAS6KnxQkz9CnaCzMWiLNh@s2461160.eu-nbg-2.betterstackdata.com/2524149';
const sentryDsn = import.meta.env.VITE_SENTRY_DSN ?? DEFAULT_SENTRY_DSN;

if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.MODE,
    enabled: import.meta.env.PROD,
    tracesSampleRate: 1.0,
  });
}

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
root.render(
  <React.StrictMode>
    <ConfigProvider theme={atelierTheme}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);

reportWebVitals();
