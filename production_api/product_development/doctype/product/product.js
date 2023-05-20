// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Product', {
	refresh: function(frm) {
		if (frm.is_new()) {
			$(frm.fields_dict['file_html'].wrapper).html("");
		} else {
			$(frm.fields_dict['file_html'].wrapper).html("");
			frm.fileEditor = new frappe.production.product_development.ui.ProductFileVersions(frm.fields_dict["file_html"].wrapper);
		}
	}
});
