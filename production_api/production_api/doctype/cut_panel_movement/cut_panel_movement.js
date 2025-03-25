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
                    callback: function(r){
                        let y = r.message
                        sessionStorage.setItem("cut_panel_stock", true)
                        sessionStorage.setItem("onload_data", JSON.stringify(y))
                        let x = frappe.model.get_new_doc("Stock Entry")
                        x.purpose = "Send to Warehouse"
                        x.posting_date = frappe.datetime.nowdate()
                        x.posting_time = new Date().toTimeString().split(' ')[0]
                        frappe.set_route("Form", x.doctype, x.name);
                    }   
                })
            })
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
