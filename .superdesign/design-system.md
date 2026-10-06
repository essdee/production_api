# Audit Pending Finishing Plans — Design System

## Product context

This is an internal accounts/audit dashboard inside Frappe Desk. It helps Accounts Users, Accounts Managers, and System Managers find Finishing Plans that have remained in Dispatched or Fully Dispatched status for more than seven days, review dispatch evidence, and identify quantities that still require operational clearance.

The target route is `/app/audit-pending-finishing-plans`. The design must feel like a dense, trustworthy operational audit screen rather than a marketing page.

## Visual foundation

- Inherit the Frappe Desk sans-serif system font; do not introduce external or decorative fonts.
- Maximum content width: 1400px, centered.
- Backgrounds: white surfaces on very light slate `#f8fafc`.
- Border: `#e2e8f0`; subtle dividers are preferred over heavy shadows.
- Primary text: `#1e293b`; body `#334155`; secondary `#64748b`; muted `#94a3b8`.
- Primary action/link: `#1a73e8`.
- Status colours: warning amber `#d97706`, success emerald `#059669`, danger red `#dc2626`.
- Cards: 12–14px radius with a quiet `0 4px 12px rgba(15, 23, 42, .025)` shadow.
- Dense data tables: uppercase 10.8–12px headers, 13.2–14.4px body, tabular numerals, right- or center-aligned quantities.
- Avoid gradients, oversized illustrations, novelty icons, glass effects, and excessive whitespace.

## Existing page structure

1. Compact title and as-of date with Refresh action.
2. Four summary cards: overdue plans, dispatched, fully dispatched, oldest pending.
3. One-row filter bar.
4. Master table of overdue Finishing Plans.
5. An expanded plan row with Dispatch History.
6. Size-wise dispatch detail in a modal.

## New pending-breakdown feature

Directly beneath Dispatch History inside the expanded plan row, render a section titled `Pending Quantity Breakdown`. Preserve the existing page hierarchy and visual language.

Show four distinct colour-by-size matrices:

1. Loose Piece — net current balance after lot transfers.
2. Loose Piece Set — separately tracked net current balance after lot transfers.
3. Rejected Pieces.
4. Rework Pending — quantity not yet reworked or rejected.

Each matrix must contain:

- A clearly differentiated title and total badge.
- Columns: Colour, each relevant size (for example S, M, L, XL, XXL), and Total.
- Colour rows with zero-only rows omitted.
- A Total footer row.
- A dash for zero cells to reduce visual noise.
- A compact empty state if the category has no quantity.

Use a responsive two-column grid of matrix cards on wide screens and one column on narrow screens. If a Finishing Plan is a set item, keep each part distinct with a small part label above its matrices.

## Interaction and states

- The page loads the pending breakdown only when the plan row is expanded.
- While loading, show a compact inline loading state below Dispatch History.
- Cache loaded breakdowns for the session.
- Loading or empty states must not shift the master table dramatically.
- Keep all existing document links and dispatch-detail interactions unchanged.

## Fidelity constraint

Use only the fonts, colours, spacing, radii, shadows, and component styles defined here and in the current Vue source. Do not introduce any fonts, colours, or visual styles outside this system.
