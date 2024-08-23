// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order", {
    refresh(frm) {
        $(frm.fields_dict['items_html'].wrapper).html("")
        frm.item = new frappe.production.ui.PPOpage(frm.fields_dict['items_html'].wrapper)
		frm.set_df_property('bom_summary','cannot_add_rows',true);
		frm.set_df_property('bom_summary','cannot_delete_rows',true);
        if(frm.doc.__onload && frm.doc.__onload.item_details) {
            frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
            frm.item.load_data(frm.doc.__onload.item_details);
        }
        else{
			if (frm.doc.item){
				frappe.call({
					method : 'production_api.essdee_production.doctype.production_order.production_order.get_item_details',
					args : {
						item_name : frm.doc.item,
						uom: frm.doc.uom,
					},
					callback:function(r){
						frm.item.load_data(r.message) 
					}
				})
			}
			else{
				frm.item.load_data([])
			}
        }
		frm.order_detail = new frappe.production.ui.PPODetail(frm.fields_dict['item_order'].wrapper)
		if(frm.doc.__onload && frm.doc.__onload.order_item_details) {
			// frappe.call({
			// 	method: 'production_api.essdee_production.doctype.production_order.production_order.fetch_order_item_details',
			// 	args: {
			// 		items : frm.doc.production_order_details,
			// 		production_detail: frm.doc.production_detail,
			// 	},
			// 	callback:function(r){
			// 		frm.doc['order_item_details'] = JSON.stringify(r.message);
            // 		frm.order_detail.load_data(r.message);
			// 	}
			// })  
			frm.order_detail.load_data(frm.doc.__onload.order_item_details);

        }
        else{
			frm.order_detail.load_data([])
		}
    },
    validate(frm){
        let items = frm.item.get_data()
        frm.doc['item_details'] = JSON.stringify(items)
    },
	async production_detail(frm){
		if(frm.doc.production_detail){
			await frappe.call({
				method : 'production_api.essdee_production.doctype.production_order.production_order.get_isfinal_uom',
                args : {
                    item_production_detail: frm.doc.production_detail,
                },
				callback: function(r){
					if(r.message){
						frm.set_value('uom', r.message)
						frm.refresh_field('uom')
					}
				}
			})
			await frappe.call({
				method : 'production_api.essdee_production.doctype.production_order.production_order.get_pack_stage_uom',
                args : {
                    item_production_detail: frm.doc.production_detail,
                },
				callback: function(r){
					if(r.message){
						frm.set_value('packing_stage', r.message.packing_stage)
						frm.set_value('packing_uom', r.message.packing_uom)
					}
				}
			})
			if (frm.doc.item){
				frappe.call({
					method : 'production_api.essdee_production.doctype.production_order.production_order.get_item_details',
					args : {
						item_name : frm.doc.item,
						uom: frm.doc.uom,
					},
					callback:function(r){
						frm.item.load_data(r.message) 
					}
				})
			}
			else{
				frm.item.load_data([])
			}
		}
	},
    calculate_bom:async function(frm) {
		if(frm.is_dirty()){
			frappe.msgprint("Save the document before calculate the BOM")
			return
		}
		if (frm.doc.item && frm.doc.production_detail) {
			frappe.call({
				method: "production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_calculated_bom",
				args: {
					item_production_detail: frm.doc.production_detail,
					items: frm.doc.items,
					production_order: frm.doc.name
				},
				callback:function(r) {
					let res = r.message;
					frappe.call({
						method: 'production_api.essdee_production.doctype.production_order.production_order.update_bom_summary',
						args: {
							doc_name: frm.doc.name,
							bom : res
						},
						freeze:true,
						freeze_message: __("Calculating BOM..."),
						callback: function(r){
							frm.refresh()
						}
					})
				}
			});
		}
	}
});
