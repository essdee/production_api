// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Plan", {
	refresh(frm) {
        frm.lot_details = new 
	},
    production_detail(frm){
        if(frm.doc.production_detail){
            frappe.call({
                method:"production_api.production_api.doctype.cutting_plan.cutting_plan.get_items",
                args: {
                    lot: frm.doc.lot
                },
                callback: function(r){
                    console.log(r.message)
                }
            })
        }
    }
});
