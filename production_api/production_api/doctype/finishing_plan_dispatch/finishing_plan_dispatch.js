// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Finishing Plan Dispatch", {
	refresh(frm) {
        $(frm.fields_dict['finishing_plan_dispatch_html'].wrapper).html("")
        frm.finishing = new frappe.production.ui.FinishingPlanDispatch(frm.fields_dict['finishing_plan_dispatch_html'].wrapper)
		const has_loaded_items = Boolean(
			frm.doc.__onload && Array.isArray(frm.doc.__onload.items)
		)
        if(has_loaded_items){
            frm.doc['finishing_items'] = JSON.stringify(frm.doc.__onload.items)
            frm.finishing.load_data(frm.doc.__onload.items)
        }
        if(frm.doc.docstatus == 0 && !has_loaded_items){
            fetch_finishing_items(frm)
        }
        if(frm.doc.docstatus == 1){
            frm.page.btn_secondary.hide()
            frm.add_custom_button("Cancel", ()=> {
                frm._cancel()
            })
            frm.add_custom_button("Print Dispatch", ()=> {
                let w = window.open(
                    frappe.urllib.get_full_url(
                        "/printview?doctype=" + encodeURIComponent(frm.doc.doctype) +
                        "&name=" + encodeURIComponent(frm.doc.name) +
                        "&trigger_print=1&format=" + encodeURIComponent("Finishing Plan Dispatch") +
                        "&no_letterhead=1"
                    )
                );
                if (!w) frappe.msgprint(__("Please enable pop-ups"));
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
        frm.doc['finishing_items'] = JSON.stringify(frm.finishing.get_data())
    }
});


function fetch_finishing_items(frm){
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan_dispatch.finishing_plan_dispatch.fetch_fp_items",
		freeze: true,
		freeze_message: __("Fetching Finishing Plans..."),
        callback: function(r){
			const items = r.message || []
			frm.finishing.load_data(items)
			frm.doc['finishing_items'] = JSON.stringify(items)
			frm.dirty()
			frappe.show_alert({
				message: __("{0} Finishing Plan(s) fetched", [items.length]),
				indicator: items.length ? "green" : "orange",
			})
        }
    })
}
