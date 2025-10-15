frappe.pages['month-wise-detail-re'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Month Wise Detail Report',
		single_column: true
	});
}
frappe.pages['month-wise-detail-re'].refresh = function(wrapper){
	new frappe.production.ui.MonthWiseDetailReport(wrapper);
}
