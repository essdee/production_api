// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Finishing Plan", {
	refresh(frm) {
        if(frm.doc.__islocal){
            return
        }
        $(".layout-side-section").css("display", "None")
        $(frm.fields_dict['finishing_item_html'].wrapper).html("")
        frm.finishing = new frappe.production.ui.FinishingDetail(frm.fields_dict['finishing_item_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.finishing_plan_data){
            frm.doc['finishing_plan_data'] = JSON.stringify(frm.doc.__onload.finishing_plan_data)
            frm.finishing.load_data(frm.doc.__onload.finishing_plan_data)
        }
        $(frm.fields_dict['finishing_quantity_html'].wrapper).html("")
        frm.finishing = new frappe.production.ui.FinishingQtyDetail(frm.fields_dict['finishing_quantity_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.finishing_qty_data){
            frm.doc['finishing_qty_data'] = JSON.stringify(frm.doc.__onload.finishing_qty_data)
            frm.finishing.load_data(frm.doc.__onload.finishing_qty_data)
        }
        $(frm.fields_dict['finishing_plan_grn_html'].wrapper).html("")
        frm.packed_item = new frappe.production.ui.FinishingGRN(frm.fields_dict["finishing_plan_grn_html"].wrapper);
        if(frm.doc.__onload && frm.doc.__onload.pack_items) {
            frm.doc['pack_items'] = JSON.stringify(frm.doc.__onload.pack_items);
            frm.packed_item.load_data(frm.doc.__onload.pack_items);
        }
        $(frm.fields_dict['inward_report_html'].wrapper).html("")
        frm.inward_detail = new frappe.production.ui.FinishingInward(frm.fields_dict["inward_report_html"].wrapper);
        if(frm.doc.__onload && frm.doc.__onload.inward_details) {
            frm.doc['inward_details'] = JSON.stringify(frm.doc.__onload.inward_details);
            frm.inward_detail.load_data(frm.doc.__onload.inward_details);
        }
        $(frm.fields_dict['finishing_old_lot_html'].wrapper).html("")
        frm.old_lot = new frappe.production.ui.FinishingOldLotTransfer(frm.fields_dict["finishing_old_lot_html"].wrapper);
        
        $(frm.fields_dict['finishing_plan_ironing_excess_html'].wrapper).html("")
        frm.ironing_detail = new frappe.production.ui.FinishingIroningExcess(frm.fields_dict["finishing_plan_ironing_excess_html"].wrapper);
        if(frm.doc.__onload && frm.doc.__onload.finishing_ironing) {
            frm.doc['finishing_ironing'] = JSON.stringify(frm.doc.__onload.finishing_ironing);
            frm.ironing_detail.load_data(frm.doc.__onload.finishing_ironing);
        }
        $(frm.fields_dict['finishing_plan_ocr_html'].wrapper).html("")
        frm.ocr_detail = new frappe.production.ui.FinishingOCR(frm.fields_dict["finishing_plan_ocr_html"].wrapper);
        if(frm.doc.__onload && frm.doc.__onload.ocr_details) {
            frm.doc['ocr_details'] = JSON.stringify(frm.doc.__onload.ocr_details);
            frm.ocr_detail.load_data(frm.doc.__onload.ocr_details);
        }
        $(frm.fields_dict['finishing_pack_return_html'].wrapper).html("")
        frm.pack_return_detail = new frappe.production.ui.FinishingPackReturn(frm.fields_dict["finishing_pack_return_html"].wrapper);
        if(frm.doc.__onload && frm.doc.__onload.pack_return) {
            frm.doc['pack_return'] = JSON.stringify(frm.doc.__onload.pack_return);
            frm.pack_return_detail.load_data(frm.doc.__onload.pack_return);
        }
        $(frm.fields_dict['incomplete_transfer_items_html'].wrapper).html("")
        new frappe.production.ui.FinishingPlanCompleteTransfer(frm.fields_dict['incomplete_transfer_items_html'].wrapper)
    },
    fetch_quantity(frm){
        frappe.call({
            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.fetch_quantity",
            args: {
                doc_name: frm.doc.name,
                work_order: frm.doc.work_order
            },
            freeze: true,
            freeze_message: "Fetching Quantity",
        })
    },
    fetch_incomplete_items(frm){
        frappe.call({
            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.get_incomplete_transfer_docs",
            args: {
                lot: frm.doc.lot,
                doc_name: frm.doc.name
            },
        })
    }
});
