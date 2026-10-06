# Shared UI Components

The Audit Pending Finishing Plans page does not import a shared Vue component library. It uses native HTML controls and tables inside a self-contained Vue single-file component, with Frappe Desk providing the outer application shell.

The only shared mounting primitive used by the page is the global Vue setup performed in `production_api/public/js/vue_plugins.js`. The target-specific wrapper is:

```js
// Audit Pending Finishing Plans
frappe.production.ui.AuditPendingFinishingPlans = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.app = createApp(AuditPendingFinishingPlans)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}
```

All visual primitives used by this target (secondary buttons, summary cards, status pills, filter controls, data tables, expanded panels, and modals) are defined directly in `production_api/public/js/AuditPendingFinishingPlans/AuditPendingFinishingPlans.vue`.
