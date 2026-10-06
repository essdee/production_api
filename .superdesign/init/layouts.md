# Shared Layouts

The page runs inside the standard Frappe Desk shell, which is supplied by the `frappe` app rather than by a Vue layout component in this repository. The app-level page wrapper creates a single-column Desk page and mounts the Vue dashboard into it.

## Frappe Desk page wrapper

Source: `production_api/production_api/page/audit_pending_finishing_plans/audit_pending_finishing_plans.js`

```js
frappe.pages['audit-pending-finishing-plans'].on_page_load = function(wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Audit Pending Finishing Plans',
        single_column: true,
    })
}

frappe.pages['audit-pending-finishing-plans'].refresh = function(wrapper) {
    if (!wrapper.audit_pending_finishing_plans) {
        wrapper.audit_pending_finishing_plans = new frappe.production.ui.AuditPendingFinishingPlans(wrapper)
    }
}
```

The dashboard component itself supplies the page-local header, summary cards, filters, master table, expandable detail area, footer, and modal.
