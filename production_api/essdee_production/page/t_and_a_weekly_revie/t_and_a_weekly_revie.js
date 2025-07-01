frappe.pages['t-and-a-weekly-revie'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Time and Action Weekly Review Report',
		single_column: true
	});
}

frappe.pages['t-and-a-weekly-revie'].refresh = function(wrapper) {
	new frappe.production.ui.TimeAndActionWeeklyReport(wrapper);
}
