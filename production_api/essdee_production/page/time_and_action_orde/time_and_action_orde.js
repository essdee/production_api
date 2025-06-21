frappe.pages['time-and-action-orde'].on_page_load = function(wrapper) {
}
frappe.pages['time-and-action-orde'].refresh = function(wrapper) {
	new frappe.production.ui.TimeAndActionOrderTracking(wrapper);
}
