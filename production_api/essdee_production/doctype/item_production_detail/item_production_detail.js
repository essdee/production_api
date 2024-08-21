// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item Production Detail", {
	setup:async function(frm) {
		let packing_attr_map = null;
		frm.set_packing_attr_map = null;
		frm.set_item_attr = null
		frm.packing_stage = null
		for(let i = 0; i < frm.doc.item_attributes.length; i++){
			if(frm.doc.item_attributes[i].attribute == frm.doc.packing_attribute){
				packing_attr_map = frm.doc.item_attributes[i].mapping;
				frm.set_packing_attr_map = frm.doc.item_attributes[i].mapping;
			}
			if(frm.doc.item_attributes[i].attribute == frm.doc.set_item_attribute){
				frm.set_item_attr= frm.doc.item_attributes[i].mapping
			}
			if(frm.doc.item_attributes[i].attribute == frm.doc.dependent_attribute){
				frm.packing_stage = frm.doc.item_attributes[i].mapping
			}
		}
		let attributes = []
		for(let i = 0 ; i < frm.doc.item_attributes.length; i++){
			attributes.push(frm.doc.item_attributes[i].attribute)
		}
		frm.set_query('set_item_attribute', ()=> {
			return {
				filters: {
					name: ["in", attributes],
				},
			};
		})
		frm.set_query('attribute_value','packing_item_details',() => {
			if(!frm.doc.packing_attribute){
				frappe.throw("Please select the packing attribute first")
			}
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': packing_attr_map,
				}
			}
		});
		frm.set_query('packing_stage', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.packing_stage,
				}
			}
		})
		frm.set_query('major_attribute_value', ()=> {
			if(!frm.doc.set_item_attribute){
				frappe.throw("Please set the Set Attribute Item")
			}
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.set_item_attr,
				}
			}
		})
	},
	refresh:async function(frm) {
		if (frm.doc.__islocal) {
			hide_field(["item_attribute_list_values", "bom_attribute_mapping"]);
		} else {
			if (frm.doc.dependent_attribute_mapping){
				frm.set_df_property('packing_stage','reqd', true);
			}
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
		if (!frm.doc.is_set_item){
			hide_field(['set_items_html','get_combination'])
		} else{
			unhide_field(['set_items_html','get_combination'])
			if(!frm.doc.is_local){
				$(frm.fields_dict['set_items_html'].wrapper).html("");
				frm.set_item = new frappe.production.ui.SetItemDetail(frm.fields_dict['set_items_html'].wrapper);
				if(frm.doc.__onload && frm.doc.__onload.set_item_detail) {
					frm.doc['set_item_detail'] = JSON.stringify(frm.doc.__onload.set_item_detail);
					await frm.set_item.load_data(frm.doc.__onload.set_item_detail);
					await frm.set_item.set_attributes()
				}
				else{
					if(frm.doc.is_set_item){
						frm.trigger('get_combination')
					}
				}
			}
		}
	},
	validate: function(frm){
		frm.dirty()
		if(frm.set_item && frm.doc.is_set_item){
			let item_details = frm.set_item.get_data()
			frm.doc['set_item_detail'] = JSON.stringify(item_details);
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
	async get_combination(frm){
		let data = null
		await frappe.call({
			method:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_new_set_item_details',
			args: {
				map : frm.set_item_attr,
				pack_details : frm.doc.packing_item_details,
			},
			callback: function(r){
				data = r.message
			}
		})
		await frm.set_item.load_data(data)
		await frm.set_item.set_attributes()
	},
	set_item_attribute(frm){
		if(frm.doc.is_set_item && frm.doc.set_item_attribute){
			frm.trigger('setup')
			unhide_field(['set_items_html','get_combination'])
			frm.set_item = new frappe.production.ui.SetItemDetail(frm.fields_dict['set_items_html'].wrapper);
			frm.trigger('get_combination')
		}
	},
});
