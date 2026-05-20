frappe.pages['work-order-pending-report'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'WORK ORDER PENDING REPORT',
		single_column: true
	});
}
frappe.pages['work-order-pending-report'].refresh = function(wrapper) {
	new frappe.production.ui.WorkOrderPendingReport(wrapper);
}

