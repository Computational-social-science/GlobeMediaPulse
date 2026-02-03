# Sidebar Design Specification & Standards

## 1. Visual Standards
**Theme**: Deep Dark (Slate-950)
**Typography**: 
- Font: Inter / Sans-serif (System stack)
- Size: 11px (Labels), 10px (Metadata)
- Weight: Regular (400) / Semibold (600)
- Tracking: Widest (0.1em) for caps labels

**Color Palette**:
- Background: `bg-slate-950` (#020617)
- Border: `border-slate-800/60`
- Text Primary: `text-slate-300`
- Text Muted: `text-slate-500`
- Text Dim: `text-slate-600`
- Accents: 
  - Active: `text-sky-400`
  - Critical: `text-rose-400`
  - Success: `text-emerald-400`
  - Warning: `text-amber-400`

**Interaction**:
- Hover: `bg-slate-900/50` (Subtle lightening)
- Active: `border-l-2` indicator (Sky-400)
- Transition: 200ms ease-out

## 2. Accessibility (WCAG 2.2 AA)
- **Contrast**: Text ratios must exceed 4.5:1 for normal text.
  - Slate-300 on Slate-950 is ~11:1 (Pass).
  - Slate-500 on Slate-950 is ~4.7:1 (Pass).
- **Keyboard Navigation**: 
  - All interactive elements must be `<button>` or `<a>`.
  - Focus rings must be visible (Tailwind `focus:ring`).
- **Screen Readers**:
  - `aria-label` or `title` on icon-only buttons.
  - `aria-expanded` on accordion toggles.
  - `aria-pressed` on toggle switches.

## 3. Responsive Behavior
- **Desktop (>1024px)**: Expanded by default (Width 320px).
- **Tablet/Laptop**: Collapsed by default (Width 56px).
- **Mobile (<640px)**: Collapsed overlay or hidden.
- **Auto-Collapse**: Sidebar collapses after 12s of inactivity (mouse leave).

## 4. Component Architecture
- **File**: `src/lib/components/Sidebar.svelte`
- **Props**:
  - `sidebarCollapsed` (Boolean)
  - `activeView` (Enum: 'health' | 'autoheal' | 'gde')
  - `statusPanelExpanded` (Boolean)
  - Data props: `totalSources`, `healthUpdatedAt`, etc.
- **Events**:
  - `onExpand`, `onCollapse`, `onTogglePanel`
  - `onActivity` (resets idle timer)

## 5. Testing Strategy
- **Unit**: Check prop rendering and state logic.
- **Visual**: Playwright screenshot comparison.
- **Manual**: Dark mode toggle (if supported), Zoom to 200%.
