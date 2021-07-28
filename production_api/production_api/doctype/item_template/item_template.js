// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Template', {
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			hide_field(["attribute_list_html"]);
		} else {
			unhide_field(["attribute_list_html"]);
			$(frm.fields_dict['attribute_list_html'].wrapper).html("");
			new frappe.ui.ItemAttributeList({
				wrapper: frm.fields_dict["attribute_list_html"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});
		}
	}
});
