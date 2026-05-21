frappe.pages['finishing-plan-ironi'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Finishing Plan Ironing Report',
		single_column: true
	});
}

frappe.pages['finishing-plan-ironi'].refresh = function(wrapper) {
	new frappe.production.ui.FinishingPlanIroningReport(wrapper);
}