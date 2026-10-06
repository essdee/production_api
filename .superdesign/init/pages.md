# Key Pages

## `/app/audit-pending-finishing-plans`

Entry: `production_api/production_api/page/audit_pending_finishing_plans/audit_pending_finishing_plans.js`

Dependencies:

- `production_api/production_api/page/audit_pending_finishing_plans/audit_pending_finishing_plans.js`
  - Frappe Desk `frappe.ui.make_app_page` shell
  - `frappe.production.ui.AuditPendingFinishingPlans` global wrapper
- `production_api/public/js/vue_plugins.js`
  - `production_api/public/js/AuditPendingFinishingPlans/AuditPendingFinishingPlans.vue`
    - `production_api/public/js/AuditPendingFinishingPlans/dashboard_utils.mjs`
- `production_api/production_api/page/audit_pending_finishing_plans/audit_pending_finishing_plans.py`
  - dashboard and dispatch-detail RPC responses

The Vue target is self-contained: its template includes the dashboard header, four summary cards, filters, master table, expanded Dispatch History panel, footer, and size-wise dispatch modal. Its scoped style contains all target-local visual rules.
