// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order", {
    refresh(frm) {
        $(frm.fields_dict['items_html'].wrapper).html("")
        frm.item = new frappe.production.ui.PPOpage(frm.fields_dict['items_html'].wrapper)
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
			frappe.call({
				method: 'production_api.essdee_production.doctype.production_order.production_order.fetch_order_item_details',
				args: {
					items : frm.doc.production_order_details,
					production_detail: frm.doc.production_detail,
				},
				callback:function(r){
					frm.doc['order_item_details'] = JSON.stringify(r.message);
            		frm.order_detail.load_data(r.message);
				}
			})  
        }
        else{
			frm.order_detail.load_data([])
		}
    },
    validate(frm){
        let items = frm.item.get_data()
        frm.doc['item_details'] = JSON.stringify(items)
    },
    item(frm){
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
    },
	production_detail(frm){
		if(frm.doc.production_detail){
			frappe.call({
				method : 'production_api.essdee_production.doctype.production_order.production_order.get_isfinal_uom',
                args : {
                    item_production_detail: frm.doc.production_detail,
                },
				callback: function(r){
					frm.set_value('uom', r.message)
				}
			})
		}
	},
    calculate_bom:async function(frm) {
		if(frm.is_dirty()){
			frappe.msgprint("Save the document before calculate the BOM")
			return
		}
		if (frm.doc.item && frm.doc.production_detail) {
			let bom = [];
			let count = 0
			for (let i = 0; i < frm.doc.items.length; i++) {
				count++;
				await frappe.call({
					method: "production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_calculated_bom",
					args: {
						item_production_detail: frm.doc.production_detail,
						item: frm.doc.items[i],
						final_uom: frm.doc.uom || null,
					},
					callback:function(r) {
						let res = r.message;
						Object.keys(res).forEach(row => {
							let found = false;
							let temp = {}
							for (let j = 0; j < bom.length; j++) {
								if(res[row] == 0){
									continue;
								}
								if (bom[j]['item'] == row){
									bom[j]['required_qty'] += res[row];
									found = true;
									break;
								}
							}
							if (!found && res[row] != 0) {
								temp["item"] = row;
								temp['required_qty'] = res[row];
								bom.push(temp);
							}
						});
					}
				});
			}
			if(count == frm.doc.items.length){
				frappe.call({
					method: 'production_api.essdee_production.doctype.production_order.production_order.update_bom_summary',
					args: {
						doc_name: frm.doc.name,
						bom : bom
					},
					freeze:true,
					freeze_message: __("Calculating BOM..."),
					callback: function(r){
						frm.refresh()
					}
				})
			}
		}
	}
});
