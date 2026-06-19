import type { ThemeConfig } from 'antd';

export const atelierTheme: ThemeConfig = {
  token: {
    colorPrimary: '#a67c35',
    colorSuccess: '#4a5c47',
    colorWarning: '#c9a227',
    colorError: '#6b2d3e',
    colorInfo: '#8b7355',
    colorBgContainer: '#faf3e8',
    colorBgElevated: '#f4e8d4',
    colorBgLayout: '#f0e4cc',
    colorText: '#2a2218',
    colorTextSecondary: '#5c4d3a',
    colorBorder: '#c9a227',
    colorBorderSecondary: 'rgba(201, 162, 39, 0.35)',
    borderRadius: 2,
    fontFamily: '"Cormorant Garamond", Georgia, serif',
    fontSize: 16,
    controlHeight: 40,
  },
  components: {
    Layout: {
      siderBg: '#1f1812',
      headerBg: '#faf3e8',
      bodyBg: 'transparent',
      triggerBg: '#3d2f24',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(201, 162, 39, 0.22)',
      darkItemColor: '#e8dcc4',
      darkItemSelectedColor: '#e8d48b',
      darkSubMenuItemBg: '#1f1812',
    },
    Card: {
      colorBgContainer: 'rgba(250, 243, 232, 0.97)',
      colorBorderSecondary: 'rgba(201, 162, 39, 0.45)',
    },
    Button: {
      primaryShadow: '0 4px 16px rgba(42, 34, 24, 0.2)',
      fontWeight: 600,
    },
    Input: {
      colorBgContainer: 'rgba(250, 243, 232, 0.9)',
      activeBorderColor: '#c9a227',
      hoverBorderColor: '#8b7355',
    },
    Select: {
      colorBgContainer: 'rgba(250, 243, 232, 0.9)',
    },
    Typography: {
      fontFamilyCode: 'ui-monospace, monospace',
    },
  },
};
