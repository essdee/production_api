// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cut Panel Movement", {
	refresh(frm) {
        $(frm.fields_dict['cut_panel_movement_html'].wrapper).html("")
        frm.cutting_movement = new frappe.production.ui.CutPanelMovementBundle(frm.fields_dict['cut_panel_movement_html'].wrapper)
        if(frm.doc.__onload.movement_details){
            frm.doc['movement_data'] = JSON.stringify(frm.doc.__onload.movement_details)
            frm.cutting_movement.load_data(frm.doc.__onload.movement_details)
        }
        if(frm.doc.cut_panel_movement_json && frm.doc.cutting_plan && frm.doc.docstatus == 0){
            frm.add_custom_button("Fetch Panels", ()=> {
                fetch_panels(frm)
                frm.dirty()
            })
        }
	},
    cutting_plan(frm){
        if(frm.doc.cutting_plan){
            fetch_panels(frm)
        }
    },
    validate(frm){
        let items = frm.cutting_movement.get_items()
        frm.doc['movement_data'] = JSON.stringify(items)
    }
});

function fetch_panels(frm){
    frappe.call({
        method: "production_api.production_api.doctype.cut_panel_movement.cut_panel_movement.get_cutting_plan_unmoved_data",
        args: {
            cutting_plan: frm.doc.cutting_plan,
        },
        callback: function(r){
            frm.cutting_movement.load_data(r.message)
        }
    })
}
