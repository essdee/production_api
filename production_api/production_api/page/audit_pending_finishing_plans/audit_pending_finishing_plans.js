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
