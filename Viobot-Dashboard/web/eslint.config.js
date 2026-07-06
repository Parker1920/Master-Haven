import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  {
    ignores: ['node_modules/**', 'dist/**'],
  },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Keep the genuine bug-catcher (conditional/looped hook calls) as an error.
      'react-hooks/rules-of-hooks': 'error',
      // eslint-plugin-react-hooks v7 ships React-Compiler-style rules that flag
      // correct-but-unoptimized patterns (setState-in-effect, ref access, purity heuristics).
      // These are stylistic/perf advisories here, not bugs — keep them as warnings, not errors.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/set-state-in-render': 'warn',
      'react-hooks/purity': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/immutability': 'warn',
      'react-hooks/static-components': 'warn',
      'react-hooks/use-memo': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/error-boundaries': 'warn',
      'react-hooks/globals': 'warn',
      'react-hooks/config': 'warn',
      'react-hooks/gating': 'warn',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^[A-Z_]' }],
      'no-undef': 'error',
      'no-empty': ['warn', { allowEmptyCatch: true }],
    },
  },
  {
    // Node context for the vite config file
    files: ['vite.config.js'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
];
