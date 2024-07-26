// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item Production Detail", {
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			hide_field(["item_attribute_list_values", "bom_attribute_mapping"]);
		} else {
			unhide_field(["item_attribute_list_values", "bom_attribute_mapping"]);

			$(frm.fields_dict['item_attribute_list_values'].wrapper).html("");
			new frappe.production.ui.ItemAttributeList({
				wrapper: frm.fields_dict["item_attribute_list_values"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});
			$(frm.fields_dict['dependent_attribute_details'].wrapper).html("");
			new frappe.production.ui.ItemDependentAttributeDetail(frm.fields_dict["dependent_attribute_details"].wrapper);

			$(frm.fields_dict['bom_attribute_mapping'].wrapper).html("");
			new frappe.production.ui.BomItemAttributeMapping(frm.fields_dict["bom_attribute_mapping"].wrapper);
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
						console.log(r.message)
						frm.set_value('primary_item_attribute',r.message.primary_attribute)
                        frm.set_value('item_attributes',r.message.attributes)
						frm.set_value('dependent_attribute', r.message.dependent_attribute)
						frm.set_value('dependent_attribute_mapping', r.message.dependent_attribute_mapping)
					}
				}
			});
		}
        else{
            frm.set_value('primary_item_attribute','')
            frm.set_value('item_attributes',[])
			frm.set_value('dependent_attribute','')
			frm.set_value('dependent_attribute_mapping','')
        }
	},
});
