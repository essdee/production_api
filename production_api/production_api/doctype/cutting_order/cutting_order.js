// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Order", {
	refresh(frm) {
		if (frm.doc.__islocal) {
			$(frm.fields_dict['item_attribute_list_values_html'].wrapper).html("");
		} else if (frm.doc.__onload && frm.doc.__onload["attr_list"]) {
			$(frm.fields_dict['item_attribute_list_values_html'].wrapper).html("");
			new frappe.production.ui.ItemAttributeList({
				wrapper: frm.fields_dict["item_attribute_list_values_html"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});
		}
	},
});
