// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("GRN Rework Item", {
	refresh(frm) {
        frm.add_custom_button("Cancel", ()=> {
            let d = new frappe.ui.Dialog({
                title: "Are you sure want to revert the process",
                primary_action_label: "Yes",
                secondary_action_label: "No",
                primary_action(){
                    d.hide()
                    frappe.call({
                        method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.revert_reworked_item",
                        args: {
                            "docname": frm.doc.name
                        }
                    })
                },
                secondary_action(){
                    d.hide()
                }
            })
            d.show()
        })
	},
});
