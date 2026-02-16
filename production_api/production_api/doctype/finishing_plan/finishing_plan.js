// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Finishing Plan", {
    refresh(frm) {
        if (frm.doc.__islocal) {
            return
        }
        $(".layout-side-section").css("display", "None")
        $(frm.fields_dict['finishing_item_html'].wrapper).html("")
        frm.finishing = new frappe.production.ui.FinishingDetail(frm.fields_dict['finishing_item_html'].wrapper)
        if (frm.doc.__onload && frm.doc.__onload.finishing_plan_data) {
            frm.doc['finishing_plan_data'] = JSON.stringify(frm.doc.__onload.finishing_plan_data)
            frm.finishing.load_data(frm.doc.__onload.finishing_plan_data)
        }
        $(frm.fields_dict['finishing_quantity_html'].wrapper).html("")
        frm.finishing = new frappe.production.ui.FinishingQtyDetail(frm.fields_dict['finishing_quantity_html'].wrapper)
        if (frm.doc.__onload && frm.doc.__onload.finishing_qty_data) {
            frm.doc['finishing_qty_data'] = JSON.stringify(frm.doc.__onload.finishing_qty_data)
            frm.finishing.load_data(frm.doc.__onload.finishing_qty_data)
        }
        $(frm.fields_dict['finishing_plan_grn_html'].wrapper).html("")
        frm.packed_item = new frappe.production.ui.FinishingGRN(frm.fields_dict["finishing_plan_grn_html"].wrapper);
        if (frm.doc.__onload && frm.doc.__onload.pack_items) {
            frm.doc['pack_items'] = JSON.stringify(frm.doc.__onload.pack_items);
            frm.packed_item.load_data(frm.doc.__onload.pack_items);
        }
        $(frm.fields_dict['inward_report_html'].wrapper).html("")
        frm.inward_detail = new frappe.production.ui.FinishingInward(frm.fields_dict["inward_report_html"].wrapper);
        if (frm.doc.__onload && frm.doc.__onload.inward_details) {
            frm.doc['inward_details'] = JSON.stringify(frm.doc.__onload.inward_details);
            frm.inward_detail.load_data(frm.doc.__onload.inward_details);
        }
        $(frm.fields_dict['finishing_old_lot_html'].wrapper).html("")
        frm.old_lot = new frappe.production.ui.FinishingOldLotTransfer(frm.fields_dict["finishing_old_lot_html"].wrapper);

        $(frm.fields_dict['finishing_plan_ironing_excess_html'].wrapper).html("")
        frm.ironing_detail = new frappe.production.ui.FinishingIroningExcess(frm.fields_dict["finishing_plan_ironing_excess_html"].wrapper);
        if (frm.doc.__onload && frm.doc.__onload.finishing_ironing) {
            frm.doc['finishing_ironing'] = JSON.stringify(frm.doc.__onload.finishing_ironing);
            frm.ironing_detail.load_data(frm.doc.__onload.finishing_ironing);
        }
        $(frm.fields_dict['finishing_plan_ocr_html'].wrapper).html("")
        frm.ocr_detail = new frappe.production.ui.FinishingOCR(frm.fields_dict["finishing_plan_ocr_html"].wrapper);
        if (frm.doc.__onload && frm.doc.__onload.ocr_details) {
            frm.doc['ocr_details'] = JSON.stringify(frm.doc.__onload.ocr_details);
            frm.ocr_detail.load_data(frm.doc.__onload.ocr_details);
        }
        $(frm.fields_dict['finishing_pack_return_html'].wrapper).html("")
        frm.pack_return_detail = new frappe.production.ui.FinishingPackReturn(frm.fields_dict["finishing_pack_return_html"].wrapper);
        if (frm.doc.__onload && frm.doc.__onload.pack_return) {
            frm.doc['pack_return'] = JSON.stringify(frm.doc.__onload.pack_return);
            frm.pack_return_detail.load_data(frm.doc.__onload.pack_return);
        }
        $(frm.fields_dict['incomplete_transfer_items_html'].wrapper).html("")
        new frappe.production.ui.FinishingPlanCompleteTransfer(frm.fields_dict['incomplete_transfer_items_html'].wrapper)
        new frappe.production.ui.AlternativeDetail(frm.fields_dict['alternative_html'].wrapper)
        frm.add_custom_button("Fetch Rejected Quantity", () => {
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.fetch_rejected_quantity",
                args: {
                    doc_name: frm.doc.name,
                },
                freeze: true,
                freeze_message: "Fetching Quantity",
                callback: function () {
                    frm.reload_doc();
                }
            })
        })
        frm.add_custom_button("Print Finishing Inward", () => {
            frappe.call({
                method: "production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_ipd_primary_values",
                args: {
                    "production_detail": frm.doc.production_detail,
                },
                callback: function (r) {
                    let d = new frappe.ui.Dialog({
                        title: "Select Size to Print Finishing Inward",
                        fields: [
                            {
                                "fieldname": "size",
                                "fieldtype": "Select",
                                "options": r.message,
                                "reqd": 1,
                                "label": "Size",
                            }
                        ],
                        primary_action(values) {
                            frappe.call({
                                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.cache_selected_size",
                                args: {
                                    "key": "inward_pf_size",
                                    "size": values.size,
                                },
                                callback: function (r) {
                                    window.open(
                                        frappe.urllib.get_full_url(
                                            "/printview?" + "doctype=" + encodeURIComponent(frm.doc.doctype) + "&name=" +
                                            encodeURIComponent(frm.doc.name) + "&trigger_print=1" + "&format=" +
                                            encodeURIComponent("Finishing Plan Inward Report") + "&no_letterhead=1"
                                        )
                                    );
                                }
                            })
                        }
                    })
                    d.show()
                }
            })
        })
        frappe.call({
            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.check_is_alternative_item",
            args: {
                "item": frm.doc.item,
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    frm.add_custom_button("Create Alternative Plan", () => {
                        let items = r.message;
                        if (items.length === 0) {
                            frappe.msgprint(__("No alternative items found for {0}", [frm.doc.item]));
                            return;
                        }
                        let d = new frappe.ui.Dialog({
                            title: __("Select Alternative Item and IPD"),
                            fields: [
                                {
                                    label: "Lot Name",
                                    fieldname: "lot_name",
                                    fieldtype: "Data",
                                    reqd: 1,
                                    default: frm.doc.lot,
                                },
                                {
                                    label: __("Alternative Item"),
                                    fieldname: "alternative_item",
                                    fieldtype: "Link",
                                    options: "Item",
                                    reqd: 1,
                                    get_query: () => {
                                        return {
                                            filters: {
                                                name: ["in", items]
                                            }
                                        }
                                    }
                                },
                                {
                                    label: __("Item Production Detail"),
                                    fieldname: "production_detail",
                                    fieldtype: "Link",
                                    options: "Item Production Detail",
                                    reqd: 1,
                                    get_query: () => {
                                        let alternative_item = d.get_value("alternative_item");
                                        if (!alternative_item) {
                                            frappe.msgprint(__("Please select an Alternative Item first."));
                                        }
                                        return {
                                            filters: {
                                                item: alternative_item || ""
                                            }
                                        }
                                    }
                                },
                                {
                                    fieldtype: "HTML",
                                    fieldname: "item_qty_html",
                                }
                            ],
                            size: "extra-large",
                            primary_action_label: __("Next"),
                            primary_action(values) {
                                let qty_details = frm.alternative_item.get_data();
                                frappe.call({
                                    method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_alternative_fp",
                                    args: {
                                        "doc_name": frm.doc.name,
                                        "alternative_item": values.alternative_item,
                                        "production_detail": values.production_detail,
                                        "lot_name": values.lot_name,
                                        "qty_details": qty_details
                                    },
                                    freeze: true,
                                    freeze_message: "Creating Alternative FP",
                                    callback: function (r) {
                                        frappe.set_route("Form", "Work Order", r.message)
                                        d.hide();
                                    }
                                })
                            }
                        });
                        frm.alternative_item = new frappe.production.ui.AlternativeItem(d.fields_dict['item_qty_html'].$wrapper, frm.doc.__onload.finishing_qty_data);
                        d.show();
                    })
                }
            }
        })
    },
    fetch_incomplete_items(frm) {
        frappe.call({
            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.get_incomplete_transfer_docs",
            args: {
                lot: frm.doc.lot,
                doc_name: frm.doc.name
            },
        })
    },
    fetch_quantity(frm) {
        frappe.call({
            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.fetch_quantity",
            args: {
                "doc_name": frm.doc.name
            },
            freeze: true,
            freeze_message: "Reupdating Finishing Plan"
        })
    }
});
