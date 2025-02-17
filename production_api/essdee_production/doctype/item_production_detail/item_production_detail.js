// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt
frappe.ui.form.on("Item Production Detail", {
	setup:function(frm) {
		frm.trigger("declarations")
		const setAttributeQuery = (doc)=>{
			const attributes = doc.item_attributes.map(attr => attr.attribute)
			return { filters: { name: ["in", attributes] } };
		};
		frm.set_query('set_item_attribute', setAttributeQuery);
		frm.set_query('packing_attribute', setAttributeQuery);
		frm.set_query('stiching_attribute', setAttributeQuery);

		frm.set_query('attribute_value','packing_attribute_details',() => {
			if(!frm.doc.packing_attribute){
				frappe.throw("Please select the packing attribute first")
			}
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.set_packing_attr_map_value,
				}
			}
		});
		frm.set_query('stage','ipd_processes',() => {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stage,
				}
			}
		});
		frm.set_query('pack_in_stage', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stage,
				}
			}
		})
		frm.set_query('cutting_in_stage', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stage,
				}
			}
		})
		frm.set_query('stiching_out_stage', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stage,
				}
			}
		})
		frm.set_query('stiching_in_stage', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stage,
				}
			}
		})
		frm.set_query('pack_out_stage', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stage,
				}
			}
		})
		frm.set_query('stiching_attribute_value','stiching_item_details', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stiching_attribute_mapping,
				}
			}
		})
		frm.set_query('stiching_major_attribute_value', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stiching_attribute_mapping,
				}
			}
		})
		frm.set_query('set_item_attribute_value','stiching_item_details', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.set_item_attr_map_value,
				}
			}
		})
		frm.set_query('dependent_attribute_value','item_bom', ()=> {
			return {
				query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
				filters: {
					'mapping': frm.stage,
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
					'mapping': frm.set_item_attr_map_value,
				}
			}
		})
	},
	declarations(frm){
		frm.set_packing_attr_map_value = null;
		frm.set_item_attr_map_value = null
		frm.stage = null
		frm.stiching_attribute_mapping = null

		for(let i = 0; i < frm.doc.item_attributes.length; i++){
			if(frm.doc.item_attributes[i].attribute == frm.doc.packing_attribute){
				frm.set_packing_attr_map_value = frm.doc.item_attributes[i].mapping;
			}
			if(frm.doc.item_attributes[i].attribute == frm.doc.set_item_attribute){
				frm.set_item_attr_map_value= frm.doc.item_attributes[i].mapping
			}
			if(frm.doc.item_attributes[i].attribute == frm.doc.dependent_attribute){
				frm.stage = frm.doc.item_attributes[i].mapping
			}
			if(frm.doc.item_attributes[i].attribute == frm.doc.stiching_attribute){
				frm.stiching_attribute_mapping = frm.doc.item_attributes[i].mapping
			}
		}
	},
	refresh: async function(frm) {
		frm.trigger('declarations')
		frm.trigger('onload_post_render')
		if(frm.doc.stiching_in_stage && frm.doc.dependent_attribute){
			frm.cutting_attrs = await get_stich_in_attributes(frm.doc.dependent_attribute_mapping,frm.doc.stiching_in_stage, frm.doc.item)
			if(frm.doc.is_set_item){
				frm.cutting_attrs.push(frm.doc.set_item_attribute)
			}
			make_select_attributes(frm,'select_attributes_html','select_attributes_wrapper','select_attrs_multicheck','cutting_attributes','cutting_items_json','get_cutting_combination')
			// if(frm.doc.cloth_detail.length > 0){
				make_select_attributes(frm,'select_cloths_attribute_html','select_cloths_attributes_wrapper','select_cloth_attrs_multicheck','cloth_attributes','cutting_cloths_json', 'get_cloth_combination')
			// }
			let accessoryClothTypeObj = JSON.parse(frm.doc.accessory_clothtype_json || '{}');
			if (Object.keys(accessoryClothTypeObj).length > 0) {
				make_select_attributes(frm, 'select_cloth_accessory_html', 'select_cloths_accessory_wrapper', 'select_cloth_accessory_multicheck', 'accessory_attributes', 'cloth_accessory_json', 'get_accessory_combination');
			}
		}
		frm.refresh_field('emblishment_details_json')
		frm.refresh_field('cutting_items_json')
		frm.refresh_field('cutting_cloths_json')
		frm.refresh_field('cloth_accessory_json')
		frm.refresh_field('accessory_clothtype_json')
		frm.refresh_field('stiching_accessory_json')

		if (frm.doc.__islocal) {
			hide_field(["item_attribute_list_values_html", "bom_attribute_mapping_html",'dependent_attribute_details_html']);
			$(frm.fields_dict['item_attribute_list_values_html'].wrapper).html("");
			$(frm.fields_dict['dependent_attribute_details_html'].wrapper).html("");
			$(frm.fields_dict['bom_attribute_mapping_html'].wrapper).html("");
			$(frm.fields_dict['set_items_html'].wrapper).html("");
			$(frm.fields_dict['stiching_items_html'].wrapper).html("");
			$(frm.fields_dict['cutting_items_html'].wrapper).html("");
			$(frm.fields_dict['cutting_cloths_html'].wrapper).html("");
			$(frm.fields_dict['cloth_accessories_html'].wrapper).html("");
			$(frm.fields_dict['stiching_accessory_html'].wrapper).html("");
			$(frm.fields_dict['accessory_clothtype_combination_html'].wrapper).html("");
			$(frm.fields_dict['emblishment_details_html'].wrapper).html("");
			$(frm.fields_dict['select_cloths_attribute_html'].wrapper).html("")
			$(frm.fields_dict['select_attributes_html'].wrapper).html("")
			$(frm.fields_dict['select_cloth_accessory_html'].wrapper).html("")
		} 
		else {
			unhide_field(["item_attribute_list_values_html", "bom_attribute_mapping_html",'dependent_attribute_details_html']);
			frm.trigger('load_item_attribute_details')
			
			if (!frm.doc.is_set_item){
				hide_field('set_items_html')
			} 
			else{
				unhide_field('set_items_html')
				frm.trigger('make_set_combination')
			}
		}
		
		frm.trigger('make_hide_and_unhide_tabs')
		if(frm.doc.cloth_detail.length == 0){
			frm.set_df_property('get_cutting_combination','hidden',true);
		}
		else{
			frm.set_df_property('get_cutting_combination','hidden',false);
		}
	},
	make_hide_and_unhide_tabs(frm){
		if(frm.doc.dependent_attribute){
			frm.trigger('make_stiching_combination')
			frm.trigger('make_cutting_combination')
			frm.trigger('make_cloth_accessories')
			frm.trigger('make_stiching_accessory_combination')
			frm.trigger("emblishment_details")
			if (frm.doc.cloth_detail.length > 0) {
				frm.trigger('make_clothtype_accessory_combination')
			}
		}

		if(!frm.doc.packing_attribute){
			frm.$wrapper.find("[data-fieldname='set_item_tab']").hide();
		}
		else{
			frm.$wrapper.find("[data-fieldname='set_item_tab']").show();
		}

	},
	load_item_attribute_details(frm){
		$(frm.fields_dict['item_attribute_list_values_html'].wrapper).html("");
		new frappe.production.ui.ItemAttributeList({
			wrapper: frm.fields_dict["item_attribute_list_values_html"].wrapper,
			attr_values: frm.doc.__onload["attr_list"]
		});
		$(frm.fields_dict['dependent_attribute_details_html'].wrapper).html("");
		new frappe.production.ui.ItemDependentAttributeDetail(frm.fields_dict["dependent_attribute_details_html"].wrapper);

		$(frm.fields_dict['bom_attribute_mapping_html'].wrapper).html("");
		new frappe.production.ui.BomItemAttributeMapping(frm.fields_dict["bom_attribute_mapping_html"].wrapper);

	},
	async make_set_combination(frm){
		$(frm.fields_dict['set_items_html'].wrapper).html("");
		frm.set_item = new frappe.production.ui.CombinationItemDetail(frm.fields_dict['set_items_html'].wrapper);
		if(frm.doc.__onload && frm.doc.__onload.set_item_detail) {
			frm.doc['set_item_detail'] = JSON.stringify(frm.doc.__onload.set_item_detail);
			await frm.set_item.load_data(frm.doc.__onload.set_item_detail);
			frm.set_item.set_attributes()
		}
	},
	async update_cloth_items(frm){
		if(frm.cloth_item){
			if(frm.doc.cutting_cloths_json) {
				let cloths = []
				for(let i = 0 ; i < frm.doc.cloth_detail.length; i++){
					if(frm.doc.cloth_detail[i].name1 && frm.doc.cloth_detail[i].cloth){
						cloths.push(frm.doc.cloth_detail[i].name1)
					}
				}
				let cut_json = frm.doc.cutting_cloths_json
				if (typeof(cut_json) == "string"){
					cut_json = JSON.parse(cut_json)
				}
				cut_json['select_list'] = cloths
				await frm.cloth_item.load_data(cut_json);
				frm.cloth_item.set_attributes()
			}
		}
		if(frm.stiching_accessory){
			if(frm.doc.stiching_accessory_json){
				let cloths = []
				for(let i = 0 ; i < frm.doc.cloth_detail.length; i++){
					if(frm.doc.cloth_detail[i].name1 && frm.doc.cloth_detail[i].cloth){
						cloths.push(frm.doc.cloth_detail[i].name1)
					}
				}	
				let stich_json = frm.doc.stiching_accessory_json
				stich_json = JSON.parse(stich_json)
				stich_json['select_list'] = cloths
				await frm.stiching_accessory.load_data(stich_json);
				frm.stiching_accessory.set_attributes()
			}
		}
	},
	async make_stiching_combination(frm){
		$(frm.fields_dict['stiching_items_html'].wrapper).html("");
		frm.stiching_item = new frappe.production.ui.CombinationItemDetail(frm.fields_dict['stiching_items_html'].wrapper);
		if(frm.doc.__onload && frm.doc.__onload.stiching_item_detail) {
			frm.doc['stiching_item_detail'] = JSON.stringify(frm.doc.__onload.stiching_item_detail);
			await frm.stiching_item.load_data(frm.doc.__onload.stiching_item_detail);
			frm.stiching_item.set_attributes()
		}
	},
	async make_cutting_combination(frm){
		$(frm.fields_dict['cutting_items_html'].wrapper).html("");
		frm.cutting_item = new frappe.production.ui.CuttingItemDetail(frm.fields_dict['cutting_items_html'].wrapper);
		if(frm.doc.cutting_items_json) {
			await frm.cutting_item.load_data(frm.doc.cutting_items_json);
			frm.cutting_item.set_attributes()
		}
		$(frm.fields_dict['cutting_cloths_html'].wrapper).html("");
		frm.cloth_item = new frappe.production.ui.CuttingItemDetail(frm.fields_dict['cutting_cloths_html'].wrapper);
		if(frm.doc.cutting_cloths_json) {
			await frm.cloth_item.load_data(frm.doc.cutting_cloths_json);
			frm.cloth_item.set_attributes()
		}
	},
	async make_cloth_accessories(frm){
		$(frm.fields_dict['cloth_accessories_html'].wrapper).html("");
		frm.cloth_accessories = new frappe.production.ui.ClothAccessory(frm.fields_dict['cloth_accessories_html'].wrapper);
		if(frm.doc.cloth_accessory_json) {
			await frm.cloth_accessories.load_data(frm.doc.cloth_accessory_json);
			frm.cloth_accessories.set_attributes()
		}
	},
	async make_stiching_accessory_combination(frm){
		$(frm.fields_dict['stiching_accessory_html'].wrapper).html("");
		frm.stiching_accessory = new frappe.production.ui.ClothAccessoryCombination(frm.fields_dict['stiching_accessory_html'].wrapper);
		if(frm.doc.stiching_accessory_json) {
			await frm.stiching_accessory.load_data(frm.doc.stiching_accessory_json);
			frm.stiching_accessory.set_attributes()
		}
	},
	async make_clothtype_accessory_combination(frm){
		$(frm.fields_dict['accessory_clothtype_combination_html'].wrapper).html("");
		frm.accessory_clothtype = new frappe.production.ui.AccessoryItems(frm.fields_dict['accessory_clothtype_combination_html'].wrapper);
		if(frm.doc.accessory_clothtype_json) {
			await frm.accessory_clothtype.load_data(frm.doc.accessory_clothtype_json);
		}
	},
	emblishment_details(frm){
		$(frm.fields_dict['emblishment_details_html'].wrapper).html("");
		frm.emblishment = new frappe.production.ui.EmblishmentDetails(frm.fields_dict['emblishment_details_html'].wrapper);
		if(frm.doc.emblishment_details_json){
			frm.emblishment.load_data(frm.doc.emblishment_details_json)
		}
	},
	onload_post_render(frm){
		showOrHideColumns(frm,['dependent_attribute_value'],'item_bom', frm.doc.dependent_attribute ? 0 : 1)
		updateChildTableReqd(frm, ['dependent_attribute_value'],'item_bom', frm.doc.dependent_attribute ? 1 : 0)
		showOrHideColumns(frm,['set_item_attribute_value','is_default'],'stiching_item_details', frm.doc.is_set_item ? 0 : 1)
		updateChildTableReqd(frm, ['set_item_attribute_value',"is_default"],'stiching_item_details', frm.doc.is_set_item ? 1 : 0)
	},
	is_set_item(frm){
		showOrHideColumns(frm,['set_item_attribute_value','is_default'],'stiching_item_details', frm.doc.is_set_item ? 0 : 1)
		updateChildTableReqd(frm, ['set_item_attribute_value',"is_default"],'stiching_item_details', frm.doc.is_set_item ? 1 : 0)
	},
	get_packing_attribute_values: function(frm){
		frappe.call({
			method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_mapping_attribute_values',
			args: {
				attribute_mapping_value: frm.set_packing_attr_map_value ,
				attribute_no : frm.doc.packing_attribute_no,
			},
			callback: function(r){
				if(r.message){
					frm.set_value('packing_attribute_details', r.message)
					frm.refresh_field('packing_attribute_details')
				}
			}
		})
	},
	get_stiching_attribute_values(frm){
		frappe.call({
			method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_mapping_attribute_values',
			args: {
				attribute_mapping_value: frm.stiching_attribute_mapping ,
				attribute_no : null,
			},
			callback: function(r){
				if(r.message){
					frm.set_value('stiching_item_details', r.message)
					frm.refresh_field('stiching_item_details')
				}
			}
		})
	},
	validate:async function(frm){
		if(!frm.doc.__islocal){
			if(frm.set_item && frm.doc.is_set_item){
				let item_details = frm.set_item.get_data()
				frm.doc['set_item_detail'] = JSON.stringify(item_details);
			}

			if(frm.stiching_item){
				let item_details = frm.stiching_item.get_data()
				if(item_details['values'].length > 0){
					frm.doc['stiching_item_detail'] = JSON.stringify(item_details);
				}
			}

			if(frm.select_attrs_multicheck){
				let cutting_attr_list = []
				let get_checked_attributes = frm.select_attrs_multicheck.get_checked_options()
				for(let i = 0 ; i< get_checked_attributes.length; i++){
					cutting_attr_list.push({'attribute':get_checked_attributes[i]})
				}
				frm.set_value('cutting_attributes',cutting_attr_list)
			}

			if(frm.select_cloth_attrs_multicheck){
				let cutting_attr_list = []
				let get_checked_attributes = frm.select_cloth_attrs_multicheck.get_checked_options()
				for(let i = 0 ; i< get_checked_attributes.length; i++){
					cutting_attr_list.push({'attribute':get_checked_attributes[i]})
				}
				frm.set_value('cloth_attributes',cutting_attr_list)
			}

			if(frm.select_cloth_accessory_multicheck){
				let cloth_accessories_list = []
				let get_checked_attributes = frm.select_cloth_accessory_multicheck.get_checked_options()
				for(let i = 0 ; i< get_checked_attributes.length; i++){
					cloth_accessories_list.push({'attribute':get_checked_attributes[i]})
				}
				frm.set_value('accessory_attributes',cloth_accessories_list)
			}

			if(frm.cutting_item){
				let item_details = frm.cutting_item.get_data()
				if(item_details == null){
					frm.doc.cutting_items_json = {}
				}
				else if(item_details.items.length > 0){
					frm.doc.cutting_items_json = item_details
				}
			}

			if(frm.cloth_item){
				let item_details = frm.cloth_item.get_data()
				if(item_details == null){
					frm.doc.cutting_cloths_json = {}
				}
				else if(item_details.items.length > 0){
					frm.doc.cutting_cloths_json = item_details
				}
			}

			if(frm.cloth_accessories){
				let item_details = frm.cloth_accessories.get_data()
				if(item_details == null){
					frm.doc.cloth_accessory_json = {}
				}
				else if(item_details.items.length > 0){
					frm.doc.cloth_accessory_json = item_details
				}
			}

			if(frm.stiching_accessory){
				let item_details = frm.stiching_accessory.get_data()
				if(item_details == null){
					frm.doc.stiching_accessory_json = {}
				}
				else if(item_details.items.length > 0){
					frm.doc.stiching_accessory_json = item_details
				}
			}

			if(frm.accessory_clothtype){
				let item_details = frm.accessory_clothtype.get_data()
				if(item_details == null){
					frm.doc.accessory_clothtype_json = {}
				}
				else {
					frm.doc.accessory_clothtype_json = item_details
				}
			}
			if(frm.emblishment){
				let items = frm.emblishment.get_items()
				if(items == null || !items ){
					frm.doc.emblishment_details_json = {}
				}
				else{
					frm.doc.emblishment_details_json = items
				}
			}
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
	get_set_item_combination(frm){
		if(!frm.doc.major_attribute_value){
			frappe.msgprint("Set the major attribute value")
			return
		}
		frappe.call({
			method:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_new_combination',
			args: {
				attribute_mapping_value : frm.set_item_attr_map_value,
				packing_attribute_details : frm.doc.packing_attribute_details,
				major_attribute_value : frm.doc.major_attribute_value,
			},
			callback:async function(r){
				await frm.set_item.load_data(r.message)
				frm.set_item.set_attributes()
			}
		})
	},
	get_stiching_item_combination(frm){
		if(!frm.doc.stiching_attribute){
			return
		}
		if(!frm.doc.stiching_major_attribute_value){
			frappe.msgprint("Set the stiching major attribute value")
			return
		}
		if(frm.doc.stiching_item_details.length == 0){
			frappe.msgprint("Set the Stiching Item Detail")
			return
		}
		frappe.call({
			method:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_new_combination',
			args: {
				attribute_mapping_value : frm.stiching_attribute_mapping,
				packing_attribute_details : frm.doc.packing_attribute_details,
				major_attribute_value : frm.doc.stiching_major_attribute_value,
				is_same_packing_attribute: frm.doc.is_same_packing_attribute,
				doc_name : frm.doc.name,
			},
			callback:async function(r){
				await frm.stiching_item.load_data(r.message)
				frm.stiching_item.set_attributes()
				frm.dirty()
			}
		})
	},
	get_cutting_combination(frm){
		let get_checked_attributes = frm.select_attrs_multicheck.get_checked_options()
		if(get_checked_attributes.length == 0){
			frappe.msgprint("Select the attributes to make combination")
			frm.cutting_item.load_data([])
		}
		else{
			frappe.call({
				method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_combination',
				args: {
					doc_name: frm.doc.name,
					attributes: get_checked_attributes,
					combination_type: 'Cutting',
				},
				callback:(async (r)=> {
					await frm.cutting_item.load_data(r.message)
					frm.cutting_item.set_attributes()
				})
			})
		}
	},
	get_cloth_combination(frm){
		if(frm.doc.cloth_detail.length == 0){
			frappe.msgprint("Fill The Cloth Details")
			return
		}
		let get_checked_attributes = frm.select_cloth_attrs_multicheck.get_checked_options()
		if(get_checked_attributes.length == 0){
			frappe.msgprint("Select the attributes to make combination")
			frm.cloth_item.load_data([])
			return
		}
		frappe.call({
			method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_combination',
			args: {
				doc_name: frm.doc.name,
				attributes: get_checked_attributes,
				combination_type:'Cloth',
			},
			callback:(async (r)=> {
				await frm.cloth_item.load_data(r.message)
				frm.cloth_item.set_attributes()
			})
		})
	},
	get_accessory_combination(frm){
		let get_checked_attributes = frm.select_cloth_accessory_multicheck.get_checked_options()
		if(get_checked_attributes.length == 0){
			frappe.msgprint("Select the attributes to make combination")
			frm.cloth_accessories.load_data([])
			return
		}
		frappe.call({
			method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_combination',
			args: {
				doc_name: frm.doc.name,
				attributes: get_checked_attributes,
				combination_type:'Accessory',
			},
			callback:(async (r)=> {
				await frm.cloth_accessories.load_data(r.message)
				frm.cloth_accessories.set_attributes()
			})
		})
	},
	get_stiching_accessory_combination(frm){
		frappe.call({
			method:"production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_stiching_accessory_combination",
			args: {
				doc_name:frm.doc.name,
			},
			callback:async function(r){
				await frm.stiching_accessory.load_data(r.message)
				frm.stiching_accessory.set_attributes()
			}
		})
	},
	set_item_attribute(frm){
		frm.set_item = new frappe.production.ui.CombinationItemDetail(frm.fields_dict['set_items_html'].wrapper);
		if(frm.doc.major_attribute_value){
			frm.trigger('get_set_item_combination')
		}
		if(frm.doc.is_set_item && frm.doc.set_item_attribute){
			frm.trigger('declarations')
			unhide_field(['set_items_html'])
			if(frm.doc.major_attr_value){
				frm.trigger('get_set_item_combination')
			}
		}
	},
	packing_attribute(frm){
		if(frm.doc.packing_attribute){
			frm.trigger('declarations')
		}
	},
	major_attribute_value(frm){
		frm.trigger('get_set_item_combination')
	},
	stiching_attribute(frm){
		if(frm.doc.stiching_attribute){
			frm.trigger('declarations')
		}
	}
});

function showOrHideColumns(frm, fields, table, hidden) {
	if (frappe.ui.form.editable_row) {
		frappe.ui.form.editable_row.toggle_editable_row(false)
	}
	let grid = frm.get_field(table).grid;
	for (let field of fields) {
		grid.fields_map[field].hidden = hidden;
	}
	grid.visible_columns = undefined;
	grid.setup_visible_columns();
	
	grid.header_row.wrapper.remove();
	delete grid.header_row;
	grid.make_head();
	
	for (let row of grid.grid_rows) {
		if (row.open_form_button) {
			row.open_form_button.parent().remove();
			delete row.open_form_button;
		}
		for (let field in row.columns) {
			if (row.columns[field] !== undefined) {
				row.columns[field].remove();
			}
		}
		for (let fieldname of fields) {
			let df = row.docfields.find(field => field.fieldname === fieldname)
			df && (df.hidden = hidden)
		}
		delete row.columns;
		row.columns = [];
		row.render_row();
	}
	frappe.ui.form.editable_row && frappe.ui.form.editable_row.toggle_editable_row(false)
}

function updateChildTableReqd(frm, fields, table, reqd) {
    let grid = frm.get_field(table).grid;
    for (let row of grid.grid_rows) {
        if (row.open_form_button) {
            row.open_form_button.parent().remove();
            delete row.open_form_button;
        }
        for (let field in row.columns) {
            if (row.columns[field] !== undefined) {
                row.columns[field].remove();
            }
        }
        for (let fieldname of fields) {
			let df = row.docfields.find(field => field.fieldname === fieldname)
            df && (df.reqd = reqd)
        }
        delete row.columns;
        row.columns = [];
        row.render_row();
    }
    frappe.ui.form.editable_row && frappe.ui.form.editable_row.toggle_editable_row(false)
}

async function get_stich_in_attributes(dependent_attribute_mapping, stiching_in_stage, item) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_stiching_in_stage_attributes',
            args: {
                dependent_attribute_mapping: dependent_attribute_mapping,
                stiching_in_stage: stiching_in_stage,
                item: item,
            },
            callback: function(r) {
                resolve(r.message); 
            },
        });
    });
}

function make_select_attributes(frm, html_field, html_class, name, attrs, json_field, combination_type){
	let $wrapper = frm.get_field(html_field).$wrapper;
	$wrapper.empty();
	const select_attributes_wrapper = $(`<div class="${html_class}"></div>`).appendTo($wrapper);
	let cutting_attr_list = frm.doc[attrs]
	let check_list = []
	for(let i = 0; i < cutting_attr_list.length; i++){
		check_list.push(cutting_attr_list[i].attribute)
	}
	frm[name] = frappe.ui.form.make_control({
		parent: select_attributes_wrapper,
		df: {
			fieldname: "select_attributes_wrapper",
			fieldtype: "MultiCheck",
			// select_all: true,
			sort_options: false,
			columns: 4,
			get_data: () => {
				return frm.cutting_attrs.map(attr => {
					let check = 0
					if(check_list.includes(attr)){
						check = 1
					}
					return {
						label: attr,   
						value: attr,  
						checked: check   
					};
				});
			},
			on_change:()=> {
				frm.set_value(json_field,{});
				frm.trigger(combination_type)
			}
		},
		render_input: true,
	});
	frm[name].refresh_input();
}
