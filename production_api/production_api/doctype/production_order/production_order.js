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
            frm.item.load_data([])
        }
    },
    validate(frm){
        let items = frm.item.get_data()
        frm.doc['item_details'] = JSON.stringify(items)
    },
    item(frm){
        if (frm.doc.item){
            frappe.call({
                method : 'production_api.production_api.doctype.production_order.production_order.get_item_details',
                args : {
                    item_name : frm.doc.item,
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
    calculate_bom: function(frm) {
		if (frm.doc.item && frm.doc.production_detail) {
			frappe.call({
				method: "production_api.production_api.doctype.item_production_detail.item_production_detail.get_calculated_bom",
				args: {
					item_production_detail: frm.doc.production_detail,
					planned_qty: 75,
				},
				callback: function(r) {
					console.log(r.message['items']);
					if (r.message) {
						if (r.message['items']) {
							let items = r.message.items || [];
							for (let i = 0; i < items.length; i++) {
								let bom = frm.doc.bom_summary;
								let found = false;
								for (let j = 0; j < bom.length; j++) {
									if (bom[j].item_name == items[i].item) {
										bom[j].required_qty = items[i].required_qty;
										found = true;
										break;
									}
								}
								if (!found) {
									var childTable = frm.add_child("bom_summary");
									childTable.item_name = items[i].item;
									childTable.required_qty = items[i].required_qty;
								}
							}
							frm.refresh_field('bom_summary');
						}
					}
				}
			});
		}
	}
});
