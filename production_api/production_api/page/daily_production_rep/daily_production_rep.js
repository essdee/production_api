frappe.pages['daily-production-rep'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Daily Production Report',
		single_column: true
	});
}

frappe.pages['daily-production-rep'].refresh = function(wrapper) {
	new frappe.production.ui.DailyProductionReport(wrapper);
}