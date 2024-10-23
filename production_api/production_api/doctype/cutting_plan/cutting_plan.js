// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Plan", {
	refresh(frm) {
        frm.cut_plan_items = new frappe.production.ui.CutPlanItems(frm.fields_dict['items_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_details){
            frm.cut_plan_items.load_data(frm.doc.__onload.item_details)
        }
        else{
            frm.cut_plan_items.load_data([])
        }

        frm.cut_plan_cloth_items = new frappe.production.ui.CutPlanClothItems(frm.fields_dict['cloths_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_cloth_details){
            frm.cut_plan_cloth_items.load_data(frm.doc.__onload.item_cloth_details)
        }
        else{
            frm.cut_plan_cloth_items.load_data([])
        }

        if(!frm.is_new()){
            frm.add_custom_button("Generate",function(){
                frappe.call({
                    method:"production_api.production_api.doctype.cutting_plan.cutting_plan.get_cloth",
                    args: {
                        ipd: frm.doc.production_detail,
                        item_name: frm.doc.item,
                        items: frm.doc.items,
                        doc_name: frm.doc.name,
                    },
                })
            })
            frm.add_custom_button("Generate Lay Reports", function(){
                frappe.call({
                    method:"production_api.production_api.doctype.cutting_plan.cutting_plan.get_cutting_laysheet_details",
                    args: {
                        cutting_plan:frm.doc.cutting_plan,
                    }
                })
            })
        }
	},
    validate(frm){
        let items = frm.cut_plan_items.get_items()
        frm.doc['item_details'] = JSON.stringify(items)

        let cloth_items = frm.cut_plan_cloth_items.get_items()
        frm.doc['item_cloth_details'] = JSON.stringify(cloth_items)
    },
    lot(frm){
        if(frm.doc.lot){
            frappe.call({
                method:"production_api.production_api.doctype.cutting_plan.cutting_plan.get_items",
                args: {
                    lot: frm.doc.lot,
                },
                callback: function(r){
                    frm.cut_plan_items.load_data(r.message)
                }
            })
        }
    },
});
