// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cut Bundle Edit", {
	refresh(frm) {
        frm.page.btn_secondary.hide()
        $(".layout-side-section").css("display", "None");
        if(frm.is_new() || frm.doc.docstatus == 2){
            $(frm.fields_dict['cut_bundles_html'].wrapper).html("")
            return
        }
        frm.cut_bundle = new frappe.production.ui.CutBundleEdit(frm.fields_dict['cut_bundles_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.movement_json){
            frm.cut_bundle.load_data(frm.doc.__onload.movement_json)
        }
        if(frm.doc.docstatus == 1){
            frm.add_custom_button("Cancel", ()=> {
                frm._cancel()
            })
        }
    },
    validate(frm){
        if(frm.cut_bundle && !frm.is_new()){
            frm.doc['movement_data'] = frm.cut_bundle.get_items()
        }
    }
});
