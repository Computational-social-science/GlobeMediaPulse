# Contributing Guidelines

## 🚨 Non-Negotiable Engineering Standards

This project enforces strict engineering standards. Violations will result in rejected PRs and mandatory refactoring.

### 1. Language Standardization (English Only)
- **Code**: All variable names, function names, comments, and strings must be in **English**.
- **Documentation**: All Markdown files, PR descriptions, and commit messages must be in **English**.
- **Prohibited**: Chinese characters (Hanzi) in source code (including comments and logs).
  - *Exception*: Content data (e.g., news articles) can be in any language, but the *code* handling it must be English.

### 2. Path & Import Policy
- **Absolute Paths**: Use `@/` alias for all internal imports.
- **Prohibited**:
  - Relative paths like `../../components` (except for immediate siblings `./` if strictly necessary, but `@/` is preferred).
  - Imports starting with `src/`.
- **Configuration**:
  - Frontend: `@` maps to `src/` (configured in `vite.config.js` and `tsconfig.json`).

### 3. "Optimization as Fix" Quality Gate
Every optimization or code change must pass the following pipeline *before* commit:

1.  **Type Check**: `tsc --noEmit` (Zero errors)
2.  **Lint**: `eslint --fix` (Zero errors, Zero warnings)
3.  **Format**: `prettier --write .`
4.  **Unit Test**: `npm run test` (Vitest/Playwright, 100% pass)
5.  **Build**: `npm run build` (Zero build errors)

**Rule**: If any step fails, the optimization is considered "broken" and must be reverted or fixed immediately. Do not commit broken code.

### 4. Sidebar & UI Integrity
- **Visual Consistency**: Ensure sidebar navigation works on all device sizes.
- **Regression Testing**: Run `npx playwright test e2e/sidebar.spec.ts` after any sidebar changes.

---

## Workflow
1.  **Branching**: Feature branches from `main`.
2.  **Commits**: Conventional Commits (e.g., `feat: add new map layer`, `fix: sidebar z-index`).
3.  **PR**: Must include "Test Plan" and verification screenshots.
