// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item', {
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			hide_field(["attribute_list_html", "bom_attribute_mapping_html", "price_html"]);
		} else {
			unhide_field(["attribute_list_html", "bom_attribute_mapping_html"]);

			// Setting the HTML for the attribute list
			$(frm.fields_dict['attribute_list_html'].wrapper).html("");
			new frappe.production.ui.ItemAttributeList({
				wrapper: frm.fields_dict["attribute_list_html"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});

			// Setting the HTML for the BOM item attribute mapping
			$(frm.fields_dict['bom_attribute_mapping_html'].wrapper).html("");
			new frappe.production.ui.BomItemAttributeMapping({
				wrapper: frm.fields_dict["bom_attribute_mapping_html"].wrapper,
			});

			// Setting the HTML for Item Price List
			$(frm.fields_dict['price_html'].wrapper).html("");
			new frappe.production.ui.ItemPriceList({
				wrapper: frm.fields_dict["price_html"].wrapper,
			});
		}
	}
});
