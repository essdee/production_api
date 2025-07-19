// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item BOM Attribute Mapping', {
	setup: function(frm) {
		frm.set_query('attribute', 'item_attributes', (doc) => {
			return {
				query: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_item_attributes',
				filters: {
					item_production_detail: doc.item_production_detail,
				}
			}
		})
		frm.set_query('attribute', 'bom_item_attributes', (doc) => {
			return {
				query: 'production_api.production_api.doctype.item.item.get_item_attributes',
				filters: {
					item: doc.bom_item,
				}
			}
		})
	},

	refresh: function(frm) {
		$(frm.fields_dict['attribute_mapping_html'].wrapper).html("");
		frm.bomEditor = new frappe.production.ui.EditBOMAttributeMapping(frm.fields_dict["attribute_mapping_html"].wrapper);
		let attributes = get_attributes(frm);
		if (attributes) {
			frm.bomEditor.load_data({
				attributes,
				data: frm.doc.values,
			});
		}
	},

	validate: function(frm) {
		if(frm.bomEditor){
			let items = frm.bomEditor.get_items();
			if (items && items.attributes && items.attributes.length == 0) {
				frm.doc.values = []
				frm.refresh_field('values');
			} else if(items && items.output && items.output.length > 0) {
				frm.doc['item_details'] = JSON.stringify(items);
				frm.doc.values = []
				for (var i = 0;i < items.output.length;i++) {
					frm.add_child('values', items.output[i]);
				}
				frm.refresh_field('values')
			}
			else {
				frappe.throw(__('Add Items to continue'));
			}
		}
		else {
			frappe.throw(__('Please refresh and try again.'));
		}
	},

	before_save: function(frm) {
		if(frm.bomEditor) {
			console.log(frm.bomEditor);
		}
	},

	get_combination: function(frm) {
		let attributes = get_attributes(frm);
		if (attributes) {
			frm.bomEditor.set_attributes(attributes);
		}
	},
});

function get_attributes(frm) {
	let attributes = [];
	let item_attributes = [];
	let same_item_attributes = [];
	$.each(frm.doc.item_attributes || [], function(i, v) {
		let attribute_value = frm.doc.item_attributes[i];
		if (attribute_value.same_attribute) {
			same_item_attributes.push(attribute_value.attribute);
		}
		item_attributes.push(attribute_value.attribute);
	});
	let same_attributes = [];
	$.each(frm.doc.bom_item_attributes || [], function(i, v) {
		let attribute_value = frm.doc.bom_item_attributes[i];
		let flag = 0;
		if (attribute_value.same_attribute) {
			if (same_item_attributes.includes(attribute_value.attribute)) {
				same_attributes.push(attribute_value.attribute);
				let index = item_attributes.indexOf(attribute_value.attribute);
				if (index > -1) {
					item_attributes.splice(index, 1);
				}
				flag = 1;
			}
		}
		if (flag == 0) {
			attributes.push({
				type: 'bom',
				attribute: attribute_value.attribute,
				same_attribute: attribute_value.same_attribute,
			});
		}
	});
	if (same_attributes.length != 0 && item_attributes.length == 0) {
		return []
	} else if (item_attributes.length == 0) {
		return null;
	}
	let m = null
	frappe.call({
		method: "production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_values",
		args: {
			'item_production_detail': frm.doc.item_production_detail,
			'attributes': item_attributes,
		},
		async: false,
		callback: function(r) {
			if (r.message) {
				m = r.message;
			}
		}
	});
	if (!m) return null;
	$.each(frm.doc.item_attributes || [], function(i, v) {
		let attribute_value = frm.doc.item_attributes[i];
		if (!same_attributes.includes(attribute_value.attribute)) {
			if (m[attribute_value.attribute]) {
				attributes.push({
					type: 'item',
					attribute: attribute_value.attribute,
					attribute_values: m[attribute_value.attribute],
				});
			} else {
				return null;
			}
		}
	});
	return attributes;
}
