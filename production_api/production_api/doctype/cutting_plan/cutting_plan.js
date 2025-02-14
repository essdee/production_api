// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Plan", {
	refresh(frm) {
        frm.cut_plan_items = new frappe.production.ui.CutPlanItems(frm.fields_dict['items_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_details){
            frm.cut_plan_items.load_data(frm.doc.__onload.item_details,0)
        }
        else{
            frm.cut_plan_items.load_data([],0)
        }
        if(!frm.is_new()){
            frm.completed_items = new frappe.production.ui.CuttingCompletionDetail(frm.fields_dict['completed_items_html'].wrapper)
            frm.completed_items.load_data(frm.doc.completed_items_json)

            frm.incompleted_items = new frappe.production.ui.CuttingIncompletionDetail(frm.fields_dict['incompleted_items_html'].wrapper)
            frm.incompleted_items.load_data(frm.doc.incomplete_items_json)

            frm.cut_plan_cloth_items = new frappe.production.ui.CutPlanClothItems(frm.fields_dict['cloths_html'].wrapper)

            if(frm.doc.__onload && frm.doc.__onload.item_cloth_details){
                frm.cut_plan_cloth_items.load_data(frm.doc.__onload.item_cloth_details,"cloth")
            }
            else{
                frm.cut_plan_cloth_items.load_data([],null)
            }

            frm.cut_plan_accessory_items = new frappe.production.ui.CutPlanClothItems(frm.fields_dict['accessory_html'].wrapper)
            if(frm.doc.__onload && frm.doc.__onload.item_accessory_details){
                frm.cut_plan_accessory_items.load_data(frm.doc.__onload.item_accessory_details,"accessory")
            }
            else{
                frm.cut_plan_accessory_items.load_data([],null)
            }
        }
        

        if(!frm.is_new()){
            frm.add_custom_button("Generate",function(){
                if (frm.is_dirty()) {
                    return;
                }
                frappe.call({
                    method:"production_api.production_api.doctype.cutting_plan.cutting_plan.get_cloth1",
                    args: {
                        cutting_plan: frm.doc.name,
                    },
                    freeze:true,
                    freeze_message:"Generating Cloths",
                    callback:function(){
                        frm.reload_doc()
                    }
                })
            })
            frm.add_custom_button("Calculate LaySheets",function(){
                if (frm.is_dirty()) {
                    return;
                }
                frappe.call({
                    method:"production_api.production_api.doctype.cutting_plan.cutting_plan.calculate_laysheets",
                    args: {
                        cutting_plan: frm.doc.name,
                    },
                })
            })
        }
	},
    validate(frm){
        let items = frm.cut_plan_items.get_items()
        frm.doc['item_details'] = JSON.stringify(items)
        
        if (frm.cut_plan_cloth_items){
            let cloth_items = frm.cut_plan_cloth_items.get_items()
            frm.doc['item_cloth_details'] = JSON.stringify(cloth_items)
        }
        if(frm.cut_plan_accessory_items){
            let accessory_items = frm.cut_plan_accessory_items.get_items()
            frm.doc['item_accessory_details'] = JSON.stringify(accessory_items)
        }

        
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
    generate_report(frm){
        frappe.call({
            method:"production_api.production_api.doctype.cutting_plan.cutting_plan.get_cutting_laysheet_report",
            args: {
                cutting_plan:frm.doc.name,
                production_detail:frm.doc.production_detail,
            }
        })
    }
});
