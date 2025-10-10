// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Action Master Template", {
    refresh(frm){
        $(".layout-side-section").css("display", "none")
        $(frm.fields_dict['action_master_html'].wrapper).html("")
        frm.action_detail = new frappe.production.ui.ActionDetail(frm.fields_dict['action_master_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.action_data){
            frm.doc['action_data'] = frm.doc.__onload.action_data['data']
            frm.action_detail.load_data(frm.doc.__onload.action_data['data'], frm.doc.__onload.action_data['previous'])
        }
    },
    validate(frm){
        if(frm.action_detail){
            let data = frm.action_detail.get_data()
            frm.doc['action_details'] = data
        }
    }
});
