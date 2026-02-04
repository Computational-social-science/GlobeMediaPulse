# Floating Panel Spec

## Scope
- Applies to all floating windows, including Status/Autoheal and Workflow Monitor
- Covers layout, typography, spacing, color, and interaction behaviors

## Layout
- Use flexible layouts with clear left/right hierarchy
- Primary content uses flexible columns, secondary content uses fixed-width panels
- Minimum size 720×520 for heavy panels, 560×420 for standard panels
- Responsive behavior: stack secondary panels below primary when width < 900px

## Spacing
- 8pt grid baseline (4, 8, 12, 16, 24, 32)
- Panel padding: 12–16px
- Control groups: 8px gap
- Section gap: 12–16px

## Typography
- Titles: 12px, semibold, tracking 0.02em
- Subtitles: 11px, regular
- Labels: 10px, mono, muted
- Values: 10–12px, mono, high contrast

## Color
- Base surfaces: light neutral with soft shadow
- Borders: low-contrast neutral
- Status colors: OK/Success green, Warning amber, Error red, Neutral slate
- Text contrast meets WCAG 2.1 AA against panel background

## Components
- Titlebar: 44px height, drag handle, action buttons on the right
- Tabs: compact labels, clear active state, keyboard focusable
- Panels: rounded corners, soft separators, consistent icon size (14–16px)
- Lists: virtualized for large data sets

## Interactions
- Keyboard: ESC closes panel, Arrow Up/Down navigates lists
- Focus: visible outline for keyboard users
- Tabs are selectable by keyboard and pointer

## Performance
- First render target ≤120ms under typical dataset
- Scroll target ≥55 FPS for lists with 500+ items
- Virtualization enabled for long lists and log streams
