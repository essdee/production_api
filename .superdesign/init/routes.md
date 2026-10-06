# Routes

This application uses Frappe Desk page routing rather than Vue Router.

## `/app/audit-pending-finishing-plans`

- Route/page name: `audit-pending-finishing-plans`
- Frappe page definition: `production_api/production_api/page/audit_pending_finishing_plans/audit_pending_finishing_plans.json`
- Page controller: `production_api/production_api/page/audit_pending_finishing_plans/audit_pending_finishing_plans.js`
- Vue entry component: `production_api/public/js/AuditPendingFinishingPlans/AuditPendingFinishingPlans.vue`
- Outer layout: standard Frappe Desk shell, single-column app page
- Roles: Accounts User, Accounts Manager, System Manager

Full route controller:

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
