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
        })
	},
});
