// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item Attribute", {
	refresh: function (frm) {
		if (frm.doc.__islocal) {
			hide_field(["section_break_8"]);
		} else {
			unhide_field(["section_break_8"]);
			if (frm.fields_dict["item_attribute_values_html"]) {
				$(frm.fields_dict['item_attribute_values_html'].wrapper).html("");
				new frappe.production.ui.ItemAttributeValues({
					wrapper: frm.fields_dict["item_attribute_values_html"].wrapper,
					attr_values: frm.doc.__onload["attr_values"],
					attr_name: frm.doc.attribute_name
				});
			}
		}
	},
});
