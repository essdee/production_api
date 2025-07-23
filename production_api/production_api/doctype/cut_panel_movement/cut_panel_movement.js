// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cut Panel Movement", {
    setup(frm){
        frm.set_query('cutting_plan',(doc)=> {
            if(!doc.lot || !doc.item){
                frappe.throw("Set Lot and Item before select Cutting Plan")
            }
			return{
				filters: {
					'lot':doc.lot,
                    'item': doc.item
				}
			}
		})
    },
	refresh(frm) {
        $(".layout-side-section").css("display", "None")
        $(frm.fields_dict['cut_panel_movement_html'].wrapper).html("")
        frm.cutting_movement = new frappe.production.ui.CutPanelMovementBundle(frm.fields_dict['cut_panel_movement_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.movement_details){
            frm.doc['movement_data'] = JSON.stringify(frm.doc.__onload.movement_details)
            frm.cutting_movement.load_data(frm.doc.__onload.movement_details)
        }
        if(frm.doc.docstatus == 0 && !frm.is_new()){
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
        if(frm.doc.docstatus == 1 && !frm.doc.against){
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
                        x.from_warehouse = frm.doc.from_warehouse
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
                                        "docstatus": 1,
                                    }
                                }
                            }
                        },
                    ],
                    primary_action(values){
                        d.hide()
                        frappe.call({
                            method:"production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.create_delivery_challan",
                            args: {
                                doc_name: frm.doc.name,
                                work_order: values.work_order,
                            },
                            callback: function(r){
                                let data = r.message
                                sessionStorage.setItem("cut_panel_dc", true)
                                sessionStorage.setItem("delivery_challan_onload_data", JSON.stringify(data.item_details))
                                let x = frappe.model.get_new_doc("Delivery Challan")
                                x.work_order = values.work_order
                                x.naming_series = "DC-"
                                x.from_location = frm.doc.from_warehouse
                                x.posting_date = frappe.datetime.nowdate()
                                x.posting_time = new Date().toTimeString().split(' ')[0]
                                x.lot = frm.doc.lot
                                x.supplier = data.supplier
                                x.supplier_name = data.supplier_name
                                x.supplier_address = data.supplier_address
                                x.supplier_address_details = data.supplier_address_details,
                                x.cut_panel_movement = frm.doc.name
                                frappe.set_route("Form", x.doctype, x.name);
                            }   
                        })
                    }
                })
                d.show()
            },"Create")
            frm.add_custom_button("Create GRN", ()=> {
                let d = new frappe.ui.Dialog({
                    title: "Select the Work Order",
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
                                        "docstatus": 1,
                                    }
                                }
                            }
                        },
                    ],
                    primary_action(values){
                        d.hide()
                        frappe.call({
                            method:"production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.create_goods_received_note",
                            args: {
                                doc_name: frm.doc.name,
                                work_order: values.work_order,
                            },
                            callback: function(r){
                                let data = r.message
                                sessionStorage.setItem("cut_panel_grn", true)
                                sessionStorage.setItem("grn_onload_data", JSON.stringify(data.item_details))
                                let x = frappe.model.get_new_doc("Goods Received Note")
                                x.against = "Work Order"
                                x.against_id = values.work_order
                                x.posting_date = frappe.datetime.nowdate()
                                x.delivery_date = frappe.datetime.nowdate()
                                x.posting_time = new Date().toTimeString().split(' ')[0]
                                x.lot = frm.doc.lot
                                x.supplier = data.supplier
                                x.supplier_name = data.supplier_name
                                x.supplier_address = data.supplier_address
                                x.supplier_address_display = data.supplier_address_details
                                x.delivery_location = data.delivery_location
                                x.delivery_location_name = data.delivery_location_name  
                                x.delivery_address = data.delivery_address
                                x.delivery_address_display = data.delivery_address_details
                                x.cut_panel_movement = frm.doc.name
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
        method: "production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.get_cut_bundle_unmoved_data",
        args: {
            from_location: frm.doc.from_warehouse,
            lot: frm.doc.lot,
            posting_date: frm.doc.posting_date,
            posting_time: frm.doc.posting_time,
            movement_from_cutting: frm.doc.movement_from_cutting,
            cutting_plan: frm.doc.cutting_plan,
            get_collapsed: true,
        },
        callback: function(r){
            frm.cutting_movement.load_data(r.message)
        }
    })
}
