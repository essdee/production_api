frappe.pages['ppo-report'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'PPO Report',
		single_column: true
	});
}

frappe.pages['ppo-report'].refresh = function(wrapper) {
	new frappe.production.ui.PPOReport(wrapper);
}
