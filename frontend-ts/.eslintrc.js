module.exports = {
  extends: [
    'react-app',
    'react-app/jest',
    'plugin:react-hooks/recommended-latest',
    'prettier',
  ],
  plugins: ['prettier'],
  rules: {
    'prettier/prettier': 'warn',
    'react-hooks/todo': 'error',
    'react-hooks/unsupported-syntax': 'error',
  },
};
