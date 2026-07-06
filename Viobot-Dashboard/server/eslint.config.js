import js from '@eslint/js';
import globals from 'globals';

export default [
  {
    ignores: ['node_modules/**', 'dashboard-data/**', '**/dashboard-backups/**'],
  },
  js.configs.recommended,
  {
    files: ['**/*.js', '**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: {
        ...globals.node,
      },
    },
    rules: {
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'no-empty': ['warn', { allowEmptyCatch: true }],
      // Defensive `let x = default` before a try/catch that reassigns is intentional here, not a bug.
      'no-useless-assignment': 'warn',
    },
  },
];
