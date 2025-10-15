frappe.pages['colour-wise-diff-rep'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Colour Wise Diff Report',
		single_column: true
	});
}

frappe.pages['colour-wise-diff-rep'].refresh = function(wrapper){
	new frappe.production.ui.ColourWiseDiffReport(wrapper)
}