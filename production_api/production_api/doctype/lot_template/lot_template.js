// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lot Template', {
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			hide_field(["item_attribute_list_html", "bom_attribute_mapping_html"]);
		} else {
			unhide_field(["attribute_list_html", "bom_attribute_mapping_html"]);

			// Setting the HTML for the attribute list
			$(frm.fields_dict['item_attribute_list_html'].wrapper).html("");
			new frappe.production.ui.ItemAttributeList({
				wrapper: frm.fields_dict["item_attribute_list_html"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});

			// Setting the HTML for the BOM item attribute mapping
			$(frm.fields_dict['bom_attribute_mapping_html'].wrapper).html("");
			new frappe.production.ui.BomItemAttributeMapping(frm.fields_dict["bom_attribute_mapping_html"].wrapper);
		}
	},

	item: function(frm) {
		if (frm.doc.item) {
			frappe.call({
				method: "production_api.production_api.doctype.item.item.get_complete_item_details",
				args: {
					item_name: frm.doc.item
				},
				callback: function(r) {
					if (r.message) {
						console.log(r.message);
						let values = {
							'primary_item_attribute': r.message.primary_attribute,
							'item_attributes': r.message.attributes,
						}
						frm.set_value(values);
					}
				}
			});
		}
	},
});
