// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt


frappe.ui.form.on('Lot', {
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
			new frappe.production.ui.BomItemAttributeMapping({
				wrapper: frm.fields_dict["bom_attribute_mapping_html"].wrapper,
			});
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
						let bom_summary = []
						for(let i = 0; i < r.message.bom.length; i++){
							bom_summary.push({item_name: r.message.bom[i].item, required_qty: 0});
						}
						let values = {
							'primary_item_attribute': r.message.primary_attribute,
							'item_attributes': r.message.attributes,
							'bom': r.message.bom,
							'bom_summary': bom_summary,
						}
						for(let i = 0; i < r.message.attributes.length; i++){
							if(r.message.attributes[i].attribute == 'Size'){
								frappe.call({
									method: "frappe.client.get",
									args: {
										doctype: "Item Item Attribute Mapping",
										name: r.message.attributes[i].mapping
									},
									callback: function(r) {
										if (r.message) {
											console.log('planned_qty', r.message)
											let planned_qty = []
											for(let i = 0; i < r.message.values.length; i++){
												planned_qty.push({size: r.message.values[i].attribute_value, qty: 0})
											}
											values['planned_qty'] = planned_qty
											console.log(values);
											frm.set_value(values);
										}
									}
								})
							}
						}
						
					}
				}
			});
		}
	},

});

function update_bom_summary(frm){
	let bom_summary = [];
	let sum = 0;
	for(let i = 0; i < frm.doc.planned_qty.length; i++){
		sum += frm.doc.planned_qty[i].qty;
	}
	let remove_index = [];
	for(let i = 0; i < frm.doc.bom_summary.length; i++){
		let found = false;
		for(let j = 0; j < frm.doc.bom.length; j++){
			if(frm.doc.bom_summary[i].item_name == frm.doc.bom[j].item){
				if(frm.doc.bom[j].qty_of_bom_item && frm.doc.bom[j].qty_of_product){
					let required_qty = frm.doc.bom[j].qty_of_bom_item * sum / frm.doc.bom[j].qty_of_product;
					frm.doc.bom_summary[i].required_qty = required_qty;
					frm.doc.bom_summary[i].pending_for_po_qty = required_qty - frm.doc.bom_summary[i].po_generated_qty;
				}
				found = true;
				break;
			}
		}
		if(!found){
			remove_index.push(i);
		}
	}
	while(remove_index.length) {
		frm.doc.bom_summary.splice(remove_index.pop(), 1);
	}
	frm.refresh_field('bom_summary');
}

frappe.ui.form.on('Lot Planned Qty', {
	qty: function(frm, cdt, cdn) {
		update_bom_summary(frm);
	},
})

frappe.ui.form.on('Item BOM', {
	qty_of_bom_item: function(frm, cdt, cdn) {
		update_bom_summary(frm);
	},
	qty_of_product: function(frm, cdt, cdn) {
		update_bom_summary(frm);
	},
	bom_remove: function(frm, cdt, cdn) {
		update_bom_summary(frm);
	}
})