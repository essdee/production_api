// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("PPO", {
	refresh(frm) {
        $(frm.fields_dict['items_html'].wrapper).html("")
        frm.item = new frappe.production.ui.PPOpage(frm.fields_dict['items_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_details) {
            frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
		    frm.item.load_data(frm.doc.__onload.item_details);
        }
        else{
            frm.item.load_data([])
        }
	},
    validate(frm){
        let items = frm.item.get_data()
        frm.doc['item_details'] = JSON.stringify(items)
    },
    item(frm){
        if (frm.doc.item){
            frappe.call({
                method : 'production_api.production_api.doctype.ppo.ppo.get_item_details',
                args : {
                    item_name : frm.doc.item,
                },
                callback:function(r){
                    frm.item.load_data(r.message) 
                }
            })
        }
        else{
            frm.item.load_data([])
        }
    }
});
