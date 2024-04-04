// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Product', {
	refresh: function(frm) {
		if (frm.is_new()) {
			$(frm.fields_dict['file_html'].wrapper).html("");
			$(frm.fields_dict['costing_html'].wrapper).html("");
		} else {
			$(frm.fields_dict['file_html'].wrapper).html("");
			$(frm.fields_dict['costing_html'].wrapper).html("");
			let fileEditor = new frappe.production.product_development.ui.ProductFileVersions(frm.fields_dict["file_html"].wrapper);
			let costingList = new frappe.production.product_development.ui.ProductCostingList(frm.fields_dict["costing_html"].wrapper);
		}
	},

	size_range: function(frm) {
		if (frm.doc.size_range) {
			frm.trigger("get_sizes");
		} else {
			frm.set_value("sizes", []);
		}
	},

	get_sizes: function(frm) {
		frappe.db.get_doc("FG Item Size Range", frm.doc.size_range).then(size_range => {
			console.log(size_range);
			frm.set_value("sizes", []);
			size_range.sizes.forEach(size => {
				let row = frm.add_child("sizes");
				row.attribute_value = size.attribute_value;
			});
			frm.refresh_field("sizes");
		});
	}
});
