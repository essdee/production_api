frappe.pages['finishing-plan-dpr'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Finishing Packed Details',
		single_column: true
	});
}
frappe.pages['finishing-plan-dpr'].refresh = function(wrapper) {
	new frappe.production.ui.FinishingPlanDPR(wrapper);
}
