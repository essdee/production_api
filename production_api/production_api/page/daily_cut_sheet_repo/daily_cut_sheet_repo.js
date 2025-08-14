frappe.pages['daily-cut-sheet-repo'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Daily Cut Sheet Report',
		single_column: true
	});
}

frappe.pages['daily-cut-sheet-repo'].refresh = function(wrapper){
	new frappe.production.ui.DailyCutSheetReport(wrapper)
}