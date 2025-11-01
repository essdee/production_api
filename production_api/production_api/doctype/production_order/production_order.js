// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order", {
	refresh(frm) {
        frm.fields_dict["details_html"].$wrapper.html("")
        if(!frm.is_new()){
            console.log("HI")
            frm.packed_item = new frappe.production.ui.ProductionOrder(frm.fields_dict["details_html"].wrapper);
            if(frm.doc.__onload && frm.doc.__onload.items) {
                frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.items);
                frm.packed_item.load_data(frm.doc.__onload.items);
            }
        }
	},
    validate(frm){
        if(!frm.is_new()){
			if(frm.packed_item){
				let items = frm.packed_item.get_data();
				frm.doc['item_details'] = JSON.stringify(items);
                console.log(items)
			}
			else {
				frappe.throw(__('Please refresh and try again.'));
			}
		}
        frappe.call({
            method: "production_api.production_api.doctype.production_order.production_order.get_primary_values",
            args: {
                item: cur_frm.doc.item
            },
            callback: function(response) {
                if(cur_frm.doc.docstatus != 0){
                    disables.value = true
                }
                primary_values.value = response.message || [];
                primary_values.value.forEach(value => {
                    if (!(value in box_qty.value)) {
                        box_qty.value[value] = 0;
                    }
                });
            }
        })
    },
});
