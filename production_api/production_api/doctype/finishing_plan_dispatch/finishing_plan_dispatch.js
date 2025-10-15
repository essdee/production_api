// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Finishing Plan Dispatch", {
	refresh(frm) {
        $(frm.fields_dict['finishing_plan_dispatch_html'].wrapper).html("")
        frm.finishing = new frappe.production.ui.FinishingPlanDispatch(frm.fields_dict['finishing_plan_dispatch_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.items){
            frm.doc['finishing_items'] = frm.doc.__onload.items
            frm.finishing.load_data(frm.doc.__onload.items)
        }
        if(frm.doc.finishing_plan_dispatch_items.length == 0){
            fetch_finishing_items(frm)
        }
        if(frm.doc.docstatus == 1){
            frm.page.btn_secondary.hide()
            frm.add_custom_button("Cancel", ()=> {
                frm._cancel()
            })
        }
        if(frm.doc.docstatus == 0){
            frm.add_custom_button("Fetch Items", ()=> {
                fetch_finishing_items(frm)
            })
        }

        if(!frm.doc.stock_entry && frm.doc.docstatus == 1){
            frm.add_custom_button("Dispatch Stock", ()=> {
                let d = new frappe.ui.Dialog({
                    title: 'Dispatch Box',
                    fields: [
                        {
                            "fieldname": "from_location",
                            "fieldtype": "Link",
                            "label": "From Location",
                            "options": "Supplier",
                            "reqd": 1,  
                        },
                        {
                            "fieldname": "to_location",
                            "fieldtype": "Link",
                            "label": "To Location",
                            "options": "Supplier",
                            "reqd": 1,
                        },
                        {
                            "fieldname": "goods_value",
                            "fieldtype": "Currency",
                            "label": "Goods Value",
                            "reqd": 1,
                        },
                        {
                            "fieldname": "vehicle_no",
                            "fieldtype": "Data",
                            "label": "Vehicle No",
                            "reqd": 1
                        }
                    ],
                    primary_action_label: 'Dispatch',
                    primary_action(values) {
                        d.hide();
                        frappe.call({
                            method: "production_api.production_api.doctype.finishing_plan_dispatch.finishing_plan_dispatch.create_stock_dispatch",
                            args: {
                                doc_name: frm.doc.name,
                                from_location: values.from_location,
                                to_location: values.to_location,
                                goods_value: values.goods_value,
                                vehicle_no: values.vehicle_no,
                            },
                            freeze: true,
                            freeze_message: "Dispatching Items...",
                            callback: function(response) {
                                frappe.msgprint("Stock Dispatched Successfully...")
                            } 
                        })
                    }
                })
                d.show()
            })
        }
	},
    validate(frm){
        frm.doc['finishing_items'] = frm.finishing.get_data()
    }
});


function fetch_finishing_items(frm){
    frm.dirty()
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan_dispatch.finishing_plan_dispatch.fetch_fp_items",
        callback: function(r){
            frm.finishing.load_data(r.message)
        }
    })
}