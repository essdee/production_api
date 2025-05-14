frappe.listview_settings["Cutting LaySheet"] = {
    add_fields: ["status"],
    get_indicator:function(doc) {
		var colors = {
			'Started': 'light-blue',
			'Completed': 'darkgrey',
			'Bundles Generated': 'orange',
			'Label Printed': 'green',
			'Cancelled': 'red',
		};
		let status = doc.status;
		return [__(status), colors[status], 'status,=,' + status];
    },
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: false,
}