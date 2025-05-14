// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cut Panel Movement", {
    setup(frm){
        frm.set_query("cutting_plan", (doc)=> {
            if (!doc.lot) {
				frappe.throw(__("Please set {0}", [__(frappe.meta.get_label(doc.doctype, 'lot', doc.name))]));
			}
            return {
                filters: {
                    "lot": doc.lot
                }
            }
        })
    },
	refresh(frm) {
        $(frm.fields_dict['cut_panel_movement_html'].wrapper).html("")
        frm.cutting_movement = new frappe.production.ui.CutPanelMovementBundle(frm.fields_dict['cut_panel_movement_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.movement_details){
            frm.doc['movement_data'] = JSON.stringify(frm.doc.__onload.movement_details)
            frm.cutting_movement.load_data(frm.doc.__onload.movement_details)
        }
        if(frm.doc.cutting_plan && frm.doc.process_name && frm.doc.docstatus == 0){
            if(frm.doc.cut_panel_movement_json){
                frm.add_custom_button("Fetch Panels", ()=> {
                    fetch_panels(frm)
                    frm.dirty()
                })
            }
            else{
                fetch_panels(frm)
                frm.dirty()
            }
        }
        if(frm.doc.docstatus == 1){
            frm.add_custom_button("Create Stock Entry", ()=> {
                frappe.call({
                    method:"production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.create_stock_entry",
                    args: {
                        doc_name: frm.doc.name,
                    },
                    freeze: true,
                    freeze_message:"Creating Stock Entry",
                    callback: function(r){
                        let y = r.message
                        sessionStorage.setItem("cut_panel_stock", true)
                        sessionStorage.setItem("stock_entry_onload_data", JSON.stringify(y))
                        let x = frappe.model.get_new_doc("Stock Entry")
                        x.purpose = "Send to Warehouse"
                        x.posting_date = frappe.datetime.nowdate()
                        x.cut_panel_movement = frm.doc.name
                        x.posting_time = new Date().toTimeString().split(' ')[0]
                        frappe.set_route("Form", x.doctype, x.name);
                    }   
                })
            },"Create")
            frm.add_custom_button("Create DC", ()=> {
                let d = new frappe.ui.Dialog({
                    title:"Select Work Order",
                    fields: [
                        {
                            "fieldname":"work_order",
                            "fieldtype":"Link",
                            "options":"Work Order",
                            "label":"Work Order",
                            "reqd": true,
                            get_query:()=> {
                                return {
                                    filters: {
                                        "lot": frm.doc.lot,
                                        "process_name": frm.doc.process_name
                                    }
                                }
                            }
                        },
                        {
                            "fieldname": "from_location",
                            "fieldtype": "Link",
                            "options": "Supplier",
                            "label": "From Location",
                            "reqd": true,
                        }
                    ],
                    primary_action(values){
                        d.hide()
                        frappe.call({
                            method:"production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.create_delivery_challan",
                            args: {
                                doc_name: frm.doc.name,
                                work_order: values.work_order,
                                process_name: frm.doc.process_name
                            },
                            callback: function(r){
                                let data = r.message
                                sessionStorage.setItem("cut_panel_dc", true)
                                sessionStorage.setItem("delivery_challan_onload_data", JSON.stringify(data.item_details))
                                let x = frappe.model.get_new_doc("Delivery Challan")
                                x.work_order = values.work_order
                                x.naming_series = "DC-"
                                x.from_location = values.from_location
                                x.posting_date = frappe.datetime.nowdate()
                                x.posting_time = new Date().toTimeString().split(' ')[0]
                                x.lot = frm.doc.lot
                                x.process_name = frm.doc.process_name,
                                x.supplier = data.supplier
                                x.supplier_name = data.supplier_name
                                x.supplier_address = data.supplier_address
                                x.supplier_address_details = data.supplier_address_details
                                x.vehicle_no = "NA"
                                frappe.set_route("Form", x.doctype, x.name);
                            }   
                        })
                    }
                })
                d.show()
            },"Create")
        }
	},
    validate(frm){
        if(!frm.is_new()){
            let items = frm.cutting_movement.get_items()
            frm.doc['movement_data'] = JSON.stringify(items)
        }
    }
});

function fetch_panels(frm){
    frm.cutting_movement.load_data({})
    frappe.call({
        method: "production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.get_cutting_plan_unmoved_data",
        args: {
            cutting_plan: frm.doc.cutting_plan,
            process_name: frm.doc.process_name,
        },
        callback: function(r){
            frm.cutting_movement.load_data(r.message)
        }
    })
}
