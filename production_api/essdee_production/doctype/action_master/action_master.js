// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Action Master", {
    refresh(frm){
        $(".layout-side-section").css("display", "none")
        $(frm.fields_dict['action_master_html'].wrapper).html("")
        frm.action_detail = new frappe.production.ui.ActionDetail(frm.fields_dict['action_master_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.action_data){
            frm.doc['action_data'] = frm.doc.__onload.action_data['data']
            frm.action_detail.load_data(frm.doc.__onload.action_data['data'], frm.doc.__onload.action_data['previous'])
        }
        if(frm.doc.workflow_state == 'Approved'){
            frm.add_custom_button("Create Template", ()=> {
                let d = new frappe.ui.Dialog({
                    title: "Are you sure want to Create Action Master Template",
                    primary_action_label: "Yes",
                    secondary_action_label: "No",
                    primary_action(){
                        d.hide()
                        frappe.call({
                            method: "production_api.essdee_production.doctype.action_master.action_master.create_master_template",
                            args: {
                                doc_name: frm.doc.name,
                            },
                            freeze: true,
                            freeze_message: "Creating Action Master",
                            callback: function(r){
                                frappe.msgprint("Action Master Template Created")
                            }
                        })
                    },
                    secondary_action(){
                        d.hide()
                    }
                })
                d.show()
            })
        }
    },
    validate(frm){
        if(frm.action_detail){
            let data = frm.action_detail.get_data()
            frm.doc['action_details'] = data
        }
    },
    action_master_template(frm){
        if(frm.doc.action_master_template){
            frappe.call({
                method: "production_api.essdee_production.doctype.action_master.action_master.get_template_details",
                args: {
                    "template": frm.doc.action_master_template, 
                },
                callback: function(r){
                    let d =  new frappe.ui.Dialog({
                        title: "Update Lead time if any changes required",
                        size: "extra-large",
                        fields: [
                            {
                                "fieldname": "template_html",
                                "fieldtype": "HTML"
                            }
                        ],
                        primary_action_label: 'Update Action Master',
                        secondary_action_label: 'Close',
                        primary_action(){
                            let data = frm.action_master_detail.get_data()
                            frm.dirty()
                            frm.doc['action_details'] = data
                            frm.action_detail = null
                            frm.save()
                            d.hide()
                        },
                        secondary_action(){
                            d.hide()
                        }
                    })
                    frm.action_master_detail = new frappe.production.ui.ActionDetail(d.fields_dict['template_html'].wrapper)
                    frm.action_master_detail.load_data(r.message, [], true)
                    d.show()
                }
            })
        }
    }
});
