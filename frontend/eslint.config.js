import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default [
  { ignores: ['dist'] },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { parser: tseslint.parser, ecmaVersion: 2020, globals: { window: 'readonly', document: 'readonly', fetch: 'readonly', Response: 'readonly', FormData: 'readonly', HTMLInputElement: 'readonly', URL: 'readonly' } },
    plugins: { 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    // The base no-unused-vars rule (run here with the TS parser) reports parameter names
    // inside function *type* annotations as unused; disable arg-position checks so those
    // documentation-only names are allowed while unused variables/imports are still caught.
    rules: { ...js.configs.recommended.rules, ...reactHooks.configs.recommended.rules, 'no-unused-vars': ['error', { args: 'none' }], 'react-refresh/only-export-components': ['warn', { allowConstantExport: true }] },
  },
  {
    // Node-context tooling and end-to-end specs run outside the browser bundle.
    files: ['playwright.config.ts', 'e2e/**/*.ts'],
    languageOptions: { globals: { process: 'readonly', console: 'readonly' } },
  },
]
