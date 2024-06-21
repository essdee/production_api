// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Process Cost", {
	setup: function(frm) {
        frm.set_query('attribute', function(doc) {
			if(!doc.item) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'item', doc.name))]));
			}
			return {
				query: 'production_api.production_api.doctype.item.item.get_item_attributes',
				filters: {
					item: doc.item,
				}
			};
		});
        frm.set_query('attribute_value', 'process_cost_values', (doc) => {
            if(!doc.item) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'item', doc.name))]));
			}
            if(!doc.attribute) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'attribute', doc.name))]));
			}
			return {
				query: 'production_api.production_api.doctype.item.item.get_item_attribute_values',
				filters: {
					item: doc.item,
					attribute: doc.attribute,
				}
			};
        });
	},
	item: function(frm){
		if(frm.doc.item){
			frappe.call({
				method: 'production_api.production_api.doctype.item.item.get_dependent_attribute',
				args: {
					'item_name': frm.doc.item,
				},
				callback: function(r){
					if(r.message){
						frm.set_value('dependent_attribute',r.message[0])
						frm.set_df_property("dependent_attribute_values", "options", r.message[1]);
					}
					else{
						frm.set_value('dependent_attribute',"")
						frm.set_df_property("dependent_attribute_values", "options", []);
					}
				}
			})
		}
		else{
			frm.set_value('dependent_attribute',"")
			frm.set_value("dependent_attribute_values","")
		}
		
	}
});
