# Theme

## Compact token summary

- Framework: Vue 3 single-file component embedded in Frappe Desk.
- CSS approach: component-scoped vanilla CSS; standard Frappe globals remain outside the component.
- Font: inherits Frappe Desk's sans-serif system font.
- Canvas width: `1400px` maximum, centered.
- Colours:
  - Border: `#e2e8f0`
  - Surface: `#ffffff`
  - Soft surface: `#f8fafc`
  - Primary text: `#1e293b`
  - Body text: `#334155`
  - Secondary text: `#64748b`
  - Muted text: `#94a3b8`
  - Action blue: `#1a73e8`
  - Warning: `#d97706` on `#fef3c7`
  - Success: `#059669` on `#d1fae5`
  - Danger: `#dc2626` on `#fee2e2`
- Type scale: 10.8, 12, 13.2, 14.4, 15.6, 21.6, 24, 28.8px.
- Radius: 7–15px; compact tables use 8–9px, cards use 12–14px.
- Shadows: subtle `0 4px 12px rgba(15, 23, 42, .025/.03)`; modal `0 24px 60px rgba(15, 23, 42, .22)`.
- Breakpoints: 900px and 600px.

## Raw source tokens and target styles

Source: scoped style in `production_api/public/js/AuditPendingFinishingPlans/AuditPendingFinishingPlans.vue`

```css
.audit-dashboard { --border: #e2e8f0; --surface: #fff; --soft: #f8fafc; --primary: #1e293b; --body: #334155; --secondary: #64748b; --muted: #94a3b8; --blue: #1a73e8; max-width: 1400px; margin: 0 auto; padding: 18px 8px 28px; color: var(--body); }
.dashboard-header, .title-line, .filter-card, .filter-label, .refresh-button, .oldest-value, .history-content h3, .size-detail-heading { display: flex; align-items: center; }
.dashboard-header { justify-content: space-between; gap: 18px; margin-bottom: 20px; }
.dashboard-header h2 { margin: 0; color: var(--primary); font-size: 28.8px; font-weight: 800; }
.dashboard-header p { margin: 5px 0 0; color: var(--secondary); font-size: 15.6px; }
.title-line { flex-wrap: wrap; gap: 10px; }
.as-of { padding: 4px 8px; border: 1px solid var(--border); border-radius: 7px; background: #f1f5f9; color: var(--secondary); font-size: 14.4px; }
.secondary-button { min-height: 36px; padding: 7px 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: #475569; font-size: 15.6px; font-weight: 600; cursor: pointer; }
.secondary-button:hover { background: #f1f5f9; color: var(--primary); }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }
.summary-card { padding: 15px 17px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .03); }
.summary-card > span { display: block; margin-bottom: 4px; color: var(--secondary); font-size: 13.2px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.summary-card strong { color: var(--primary); font-size: 28.8px; font-variant-numeric: tabular-nums; }
.filter-card { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; padding: 12px 16px; border: 1px solid #edf1f5; border-radius: 14px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .025); }
.table-shell, .history-shell, .size-table-shell { overflow-x: auto; }
.table-shell { border: 1px solid var(--border); border-radius: 12px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .025); }
table { width: 100%; border-collapse: collapse; }
th { padding: 10px; border-bottom: 1px solid var(--border); background: var(--soft); color: #475569; font-size: 12px; font-weight: 700; letter-spacing: .025em; text-align: left; text-transform: uppercase; }
td { padding: 11px 10px; border-bottom: 1px solid var(--border); color: var(--body); font-size: 14.4px; font-weight: 500; vertical-align: middle; }
.status-pill, .age-badge { display: inline-flex; align-items: center; justify-content: center; border-radius: 7px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.status-dispatched { border-color: #fde68a; background: #fef3c7; color: #d97706; }
.status-fully { border-color: #a7f3d0; background: #d1fae5; color: #059669; }
.age-danger { background: #fee2e2; color: #dc2626; }
.age-critical { background: #dc2626; color: #fff; }
.history-panel > td { padding: 0; border-top: 1px dashed var(--border); background: var(--soft); }
.history-content { padding: 14px 14px 18px 52px; }
.history-table { min-width: 760px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
.history-table th { padding: 8px 9px; background: #f1f5f9; font-size: 10.8px; }
.history-table td { padding: 8px 9px; border-bottom-color: #f1f5f9; font-size: 13.2px; }
@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .filter-card { flex-wrap: wrap; } }
@media (max-width: 600px) { .dashboard-header h2 { font-size: 24px; } .history-content { padding-left: 14px; } }
```
