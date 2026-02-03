# Development Recommendations & Code Quality Assessment

## 1. Potential Risks in Current Code Structure

### 1.1 Monolithic Components
**Observation**: `App.svelte` currently contains over 1000 lines of mixed concerns:
- UI Rendering (Map, Sidebar)
- State Management (Stores, Local State)
- Business Logic (Health Checks, WebSocket handling, Audio Context)
- Helper Functions (Status color mapping)

**Risk**: 
- **High Cognitive Load**: Difficult for new developers to navigate.
- **Testing Difficulty**: Hard to isolate specific logic for unit testing (as seen with the status helpers).
- **Fragility**: Changes in one area (e.g., audio) can accidentally impact others (e.g., sidebar rendering) due to shared scope.

### 1.2 Tight Coupling of UI and Logic
**Observation**: Functions like `getSystemSlotClass` previously relied on module-level reactive variables (`$systemStatus`), making them impure and hard to test outside the component context.

**Risk**:
- **Low Reusability**: Logic cannot be shared with other components.
- **Implicit Dependencies**: Functions depend on the specific context of `App.svelte`.

### 1.3 Lack of Automated Unit Testing
**Observation**: Project relies heavily on manual verification or E2E tests (Playwright), lacking granular unit tests for business logic.

**Risk**:
- **Regression**: Small logic errors can slip through if they don't break the main E2E flows.
- **Slow Feedback Loop**: E2E tests are slower than unit tests.

## 2. Recommended Coding Standards

### 2.1 Logic Extraction (The "Utils" Pattern)
- **Rule**: Any function that does not directly manipulate DOM or component lifecycle should be extracted to `src/utils/` or `src/lib/logic/`.
- **Benefit**: Enables pure unit testing (Vitest) and reuse.
- **Example**: The recent extraction of `statusHelpers.ts`.

### 2.2 Component Decomposition
- **Rule**: Components exceeding 300 lines should be candidates for splitting.
- **Strategy**:
  - `Sidebar.svelte`: Extract the sidebar UI.
  - `StatusPanel.svelte`: Extract the detailed status view.
  - `SoundManager.ts`: Move the class to a dedicated file in `src/lib/services/`.
  - `WebSocketService.ts`: Move to `src/lib/services/`.

### 2.3 Explicit Typing
- **Rule**: Avoid `any`. Use interfaces for all data structures (e.g., WebSocket messages, Health Check responses).
- **Benefit**: Improved IDE support and compile-time error catching.

## 3. Reusable Abstraction Schemes

### 3.1 Status System Abstraction
Instead of ad-hoc string comparisons (`status === 'ONLINE'`), define a shared enum and configuration object.

```typescript
// src/types/system.ts
export enum SystemStatus {
  ONLINE = 'ONLINE',
  DEGRADED = 'DEGRADED',
  OFFLINE = 'OFFLINE'
}

// src/config/statusConfig.ts
export const STATUS_CONFIG = {
  [SystemStatus.ONLINE]: { color: 'ok', icon: 'check_circle', label: 'Normal' },
  [SystemStatus.DEGRADED]: { color: 'warn', icon: 'warning', label: 'Degraded' },
  [SystemStatus.OFFLINE]: { color: 'error', icon: 'error', label: 'Offline' },
};
```

### 3.2 Service Layer Pattern
Formalize the "Service" pattern for singleton logic classes.
- `AudioService`
- `NetworkService` (WebSocket + Fetch wrapper)
- `TelemetryService`

## 4. Performance Optimization Points

### 4.1 Memoization of Derived State
**Current**: Reactive statements (`$: ...`) run whenever dependencies change.
**Optimization**: Ensure heavy computations (like filtering large lists of logs or map sources) are optimized or memoized.

### 4.2 Render Optimization
**Current**: The sidebar has many conditional checks inside the template.
**Optimization**: Extract complex conditions into derived stores to simplify the template and prevent unnecessary re-evaluations.

### 4.3 Bundle Size
**Current**: `maplibre-gl` is large.
**Optimization**: Verify dynamic import usage if the map is not immediately required on all views (though likely core here).

## 5. Key Lint Rules to Monitor

Ensure `.eslintrc.cjs` or `eslint.config.js` enforces:

1.  **`no-dupe-class-members` / `no-redeclare`**: To prevent the specific error encountered today.
2.  **`complexity`**: Warn if cyclomatic complexity of functions exceeds a threshold (e.g., 10), prompting extraction.
3.  **`max-lines`**: Warn if files exceed 500 lines.
4.  **`@typescript-eslint/explicit-function-return-type`**: Enforce return types for exported functions to prevent accidental API changes.
5.  **`svelte/no-at-html-tags`**: Security rule to prevent XSS (unless strictly necessary and sanitized).

## 6. Action Plan for Next Sprint

1.  **Refactor**: Move `SoundManager` and `WebSocketService` out of `App.svelte`.
2.  **Test**: Add unit tests for the newly extracted services.
3.  **Lint**: Update ESLint config to stricter standards.
4.  **Docs**: Generate TSDoc for all core services.
