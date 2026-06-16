frappe.pages['finishing-plan-report'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Finishing Plan Report',
		single_column: true
	});
}
frappe.pages['finishing-plan-report'].refresh = function(wrapper) {
	new frappe.production.ui.FinishingPlanReport(wrapper);
}
