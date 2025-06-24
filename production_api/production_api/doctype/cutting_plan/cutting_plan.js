// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Plan", {
    setup(frm){
        frm.set_query('work_order', (doc)=> {
            return {
                filters: {
                    "lot": doc.lot,
                    "docstatus": 1,
                }
            }
        })
    },
	refresh(frm) {
        frappe.require("https://cdn.jsdelivr.net/npm/html2canvas-pro@1.5.8/dist/html2canvas-pro.min.js");
        frm.cut_plan_items = new frappe.production.ui.CutPlanItems(frm.fields_dict['items_html'].wrapper)
        if(frm.is_new()){
            ["items_html", "completed_items_html", "incompleted_items_html", "accessory_html", "cloths_html"]
            .forEach(field => $(frm.fields_dict[field].wrapper).html(""));
        }
        else{
            if(frm.doc.__onload && frm.doc.__onload.item_details){
                frm.cut_plan_items.load_data(frm.doc.__onload.item_details,0)
            }
            else{
                frm.cut_plan_items.load_data([],0)
            }
            frm.completed_items = new frappe.production.ui.CuttingCompletionDetail(frm.fields_dict['completed_items_html'].wrapper)
            frm.completed_items.load_data(frm.doc.completed_items_json, 1)

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
            
            frm.add_custom_button("Get Completed", () => {
                let d = new frappe.ui.Dialog({
                    size: "large",
                    fields: [
                        { fieldname: "pop_up_html", fieldtype: "HTML" },
                        { fieldname: "output_html", fieldtype: "HTML" },
                    ],
                    primary_action_label: "Copy to Clipboard",
                    secondary_action_label: "Take Screenshot",
                    async primary_action() {
                        let sourceDiv = d.fields_dict.pop_up_html.wrapper;
                        let canvas = await html2canvas(sourceDiv, { scale: 1, useCORS: true });
                        canvas.toBlob(async (blob) => {
                            await navigator.clipboard.write([
                                new ClipboardItem({ "image/png": blob }),
                            ]);
                            frappe.show_alert("Image Copied to Clipboard");
                        });
                    },
                    secondary_action() {
                        let sourceDiv = d.fields_dict.pop_up_html.wrapper;
                        html2canvas(sourceDiv, { scale: 1, useCORS: true }).then((canvas) => {
                            let link = document.createElement("a");
                            link.href = canvas.toDataURL("image/png");
                            link.download = "screenshot.png";
                            link.click();
                        });
                    },
                });
                d.$wrapper.find(".btn-modal-secondary").css({
                    "background-color": "cadetblue",
                    color: "white",
                });
                frm.completed_popup = new frappe.production.ui.CuttingCompletionDetail(d.fields_dict.pop_up_html.wrapper);
                frm.completed_popup.load_data(frm.doc.completed_items_json, 3);
                d.show();
            });

            frm.add_custom_button("Update Completed", ()=> {
                let d = new frappe.ui.Dialog({
                    size:"extra-large",
                    fields: [
                        {
                            "fieldname":"update_pop_up_html",
                            "fieldtype":"HTML",
                        }
                    ],
                    primary_action_label:"Submit",
                    primary_action(){
                        frm.dirty()
                        let items = frm.update_completed.get_items()
                        frm.set_value("completed_items_json",JSON.parse(JSON.stringify(items[0])))
                        frm.save()   
                        d.hide()
                    }
                })
                frm.update_completed = new frappe.production.ui.CuttingCompletionDetail(d.fields_dict.update_pop_up_html.wrapper)
                frm.update_completed.load_data(frm.doc.completed_items_json, 2)
                d.show()
            })
            if(frm.doc.work_order){
                frappe.call({
                    method: "production_api.production_api.doctype.work_order.work_order.fetch_summary_details",
                    args : {
                        doc_name: frm.doc.work_order,
                        production_detail: frm.doc.production_detail,
                    },
                    callback: function(r){
                        $(frm.fields_dict['planned_details_html'].wrapper).html("")
                        frm.summary = new frappe.production.ui.WOSummary(frm.fields_dict["planned_details_html"].wrapper);
                        frm.summary.load_data(r.message.item_detail, r.message.deliverables)
                    }
                })
            }
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
