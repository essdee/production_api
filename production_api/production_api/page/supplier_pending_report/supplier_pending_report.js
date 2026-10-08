frappe.pages['supplier-pending-report'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Supplier Pending Report',
		single_column: true,
	})
}

frappe.pages['supplier-pending-report'].refresh = function(wrapper) {
	if (!wrapper.supplier_pending_report) {
		wrapper.supplier_pending_report = new frappe.production.ui.SupplierPendingReport(wrapper)
	}
}
