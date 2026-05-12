// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Finishing Plan", {
    refresh(frm) {
        if (frm.doc.__islocal) {
            return
        }
        ensure_dispatch_history_visible(frm);
        apply_p_and_l_tab_visibility(frm);
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
        frm.ocr_detail.load_consumption_data(frm.doc.name);
        frm.ocr_detail.load_stock_balance_data(frm.doc.name);
        $(frm.fields_dict['finishing_pack_return_html'].wrapper).html("")
        frm.pack_return_detail = new frappe.production.ui.FinishingPackReturn(frm.fields_dict["finishing_pack_return_html"].wrapper);
        if (frm.doc.__onload && frm.doc.__onload.pack_return) {
            frm.doc['pack_return'] = JSON.stringify(frm.doc.__onload.pack_return);
            frm.pack_return_detail.load_data(frm.doc.__onload.pack_return);
        }
        $(frm.fields_dict['finishing_rejection_html'].wrapper).html("")
        frm.rejection_detail = new frappe.production.ui.FinishingRejectionDetail(frm.fields_dict['finishing_rejection_html'].wrapper)
        if (frm.doc.__onload && frm.doc.__onload.finishing_rejection_data) {
            frm.rejection_detail.load_data(frm.doc.__onload.finishing_rejection_data)
        }
        $(frm.fields_dict['incomplete_transfer_items_html'].wrapper).html("")
        new frappe.production.ui.FinishingPlanCompleteTransfer(frm.fields_dict['incomplete_transfer_items_html'].wrapper)
        new frappe.production.ui.AlternativeDetail(frm.fields_dict['alternative_html'].wrapper)
        render_p_and_l_section(frm);

        const LOCKED_STATUSES = ["OCR Completed", "P&L Submitted"];
        const is_locked = LOCKED_STATUSES.includes(frm.doc.fp_status);
        if (is_locked) {
            frm.disable_save();
            // freeze all fields (except virtual HTML wrappers — still rendered, but their inner UIs are hidden below via CSS)
            frm.fields.forEach((f) => {
                if (f.df && f.df.fieldtype !== "HTML" && f.df.fieldtype !== "Tab Break" &&
                    f.df.fieldtype !== "Section Break" && f.df.fieldtype !== "Column Break") {
                    frm.set_df_property(f.df.fieldname, "read_only", 1);
                }
            });
            // scope CSS: hide any button inside HTML wrappers, except our P&L tab's controls
            $("#fp-locked-style").remove();
            $("<style id='fp-locked-style'>" +
                ".fp-locked [data-fieldtype='HTML'] button:not(.pl-upload-btn):not(.pl-delete)," +
                ".fp-locked [data-fieldtype='HTML'] .btn:not(.pl-upload-btn):not(.pl-delete)," +
                ".fp-locked [data-fieldtype='HTML'] input[type='file']," +
                ".fp-locked [data-fieldtype='HTML'] a.btn" +
                " { display: none !important; }" +
                ".fp-locked [data-fieldname='p_and_l_html'] button," +
                ".fp-locked [data-fieldname='p_and_l_html'] .btn { display: inline-block !important; }" +
                "</style>").appendTo("head");
            $(frm.wrapper).addClass("fp-locked");
            // notice banner
            frm.dashboard.clear_headline();
            frm.dashboard.set_headline_alert(
                `<b>${frappe.utils.escape_html(frm.doc.fp_status)}</b> — this Finishing Plan is locked. Creating new entries has been disabled.`,
                "orange"
            );
            return;   // skip all button additions below
        } else {
            $(frm.wrapper).removeClass("fp-locked");
        }

        if (frm.doc.fp_status === "OCR Requested" && frappe.user.has_role("System Manager")) {
            frm.add_custom_button("Approve Request", () => {
                frappe.confirm(
                    "Approve the OCR request and mark this Finishing Plan as OCR Completed?",
                    () => {
                        frappe.call({
                            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.approve_ocr_request",
                            args: { doc_name: frm.doc.name },
                            freeze: true,
                            freeze_message: "Approving...",
                            callback: () => {
                                frappe.show_alert({ message: "Status set to <b>OCR Completed</b>.", indicator: "green" });
                                frm.reload_doc();
                            },
                        });
                    }
                );
            });
        }
        if (["Dispatched", "Fully Dispatched"].includes(frm.doc.fp_status)) {
        frm.add_custom_button("Complete OCR", () => {
            frappe.confirm(
                "Complete OCR for this Finishing Plan? Status will be set based on unaccountable pieces.",
                () => {
                    frappe.call({
                        method: "production_api.production_api.doctype.finishing_plan.finishing_plan.complete_ocr",
                        args: { doc_name: frm.doc.name },
                        freeze: true,
                        freeze_message: "Checking unaccountable pieces...",
                        callback: (r) => {
                            if (r.message) {
                                const msg = r.message.fp_status === "OCR Completed"
                                    ? `Unaccountable = 0. Status set to <b>OCR Completed</b>.`
                                    : `Unaccountable = ${r.message.unaccountable}. Status set to <b>OCR Requested</b>.`;
                                frappe.show_alert({
                                    message: msg,
                                    indicator: r.message.fp_status === "OCR Completed" ? "green" : "orange",
                                });
                            }
                            frm.reload_doc();
                        },
                    });
                }
            );
        });
        }
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
                                    "finishing_id": frm.doc.name,
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

function apply_p_and_l_tab_visibility(frm) {
    frappe.db.get_single_value("MRP Settings", "merch_user_role").then((merch_role) => {
        const allowed = merch_role && frappe.user.has_role(merch_role);
        frm.set_df_property("p_and_l_tab", "hidden", allowed ? 0 : 1);
        frm.set_df_property("p_and_l_html", "hidden", allowed ? 0 : 1);
    });
}

function ensure_dispatch_history_visible(frm) {
    if (!frm.fields_dict.dispatch_history_tab || !frm.fields_dict.finishing_plan_dispatch_logs) {
        return;
    }
    frm.set_df_property("dispatch_history_tab", "hidden", 0);
    frm.set_df_property("finishing_plan_dispatch_logs", "hidden", 0);
    frm.set_df_property("finishing_plan_dispatch_logs", "cannot_add_rows", true);
    frm.set_df_property("finishing_plan_dispatch_logs", "cannot_delete_rows", true);
    frm.refresh_field("finishing_plan_dispatch_logs");
}

function render_p_and_l_section(frm) {
    const field = frm.fields_dict && frm.fields_dict['p_and_l_html'];
    if (!field) return;
    const $wrap = $(field.wrapper);
    $wrap.empty();

    if (frm.doc.fp_status !== "OCR Completed") {
        $wrap.html(
            `<div style="padding:16px; color:#64748b; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:8px;">
                P & L uploads are available only when <b>FP Status</b> is <b>OCR Completed</b>.
                Current status: <b>${frappe.utils.escape_html(frm.doc.fp_status || "Planned")}</b>.
            </div>`
        );
        return;
    }

    const $container = $(`
        <div style="display:flex; flex-direction:column; gap:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h4 style="margin:0;">P & L Documents</h4>
                <button class="btn btn-primary btn-sm pl-upload-btn">
                    <i class="fa fa-upload"></i> Upload File
                </button>
            </div>
            <div class="pl-list"></div>
        </div>
    `).appendTo($wrap);

    function refresh_list() {
        const $list = $container.find(".pl-list");
        $list.html(`<div style="color:#64748b;">Loading...</div>`);
        frappe.call({
            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.get_p_and_l_documents",
            args: { doc_name: frm.doc.name },
            callback: (r) => {
                const docs = r.message || [];
                if (!docs.length) {
                    $list.html(`<div style="color:#64748b; padding:12px; background:#f8fafc; border-radius:8px;">No P&L documents uploaded yet.</div>`);
                    return;
                }
                const rows = docs.map((d, i) => {
                    const fname = (d.file || "").split("/").pop();
                    const when = frappe.datetime.str_to_user(d.modified);
                    const cmt = d.comments ? `<div style="color:#64748b; font-size:12px; margin-top:4px;">${frappe.utils.escape_html(d.comments)}</div>` : "";
                    return `
                        <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 12px; border:1px solid #e2e8f0; border-radius:8px; background:#fff; margin-bottom:8px;">
                            <div style="flex:1;">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span style="font-weight:600;">${i + 1}.</span>
                                    <a href="${d.file}" target="_blank" style="font-weight:500;">${frappe.utils.escape_html(fname)}</a>
                                    <span style="color:#94a3b8; font-size:12px;">— ${when} — ${frappe.utils.escape_html(d.owner)}</span>
                                </div>
                                ${cmt}
                            </div>
                            <button class="btn btn-danger btn-xs pl-delete" data-name="${d.name}" title="Delete">
                                <i class="fa fa-trash"></i>
                            </button>
                        </div>
                    `;
                }).join("");
                $list.html(rows);
                $list.find(".pl-delete").on("click", function () {
                    const name = $(this).data("name");
                    frappe.confirm("Delete this P&L document?", () => {
                        frappe.call({
                            method: "production_api.production_api.doctype.finishing_plan.finishing_plan.delete_p_and_l_document",
                            args: { name },
                            freeze: true,
                            callback: () => {
                                frappe.show_alert({ message: "Deleted", indicator: "orange" });
                                refresh_list();
                            },
                        });
                    });
                });
            },
        });
    }

    $container.find(".pl-upload-btn").on("click", () => {
        const d = new frappe.ui.Dialog({
            title: "Upload P & L Document",
            fields: [
                { fieldname: "file", fieldtype: "Attach", label: "File", reqd: 1 },
                { fieldname: "comments", fieldtype: "Small Text", label: "Comments" },
            ],
            primary_action_label: "Save",
            primary_action(values) {
                frappe.call({
                    method: "production_api.production_api.doctype.finishing_plan.finishing_plan.add_p_and_l_document",
                    args: {
                        doc_name: frm.doc.name,
                        file_url: values.file,
                        comments: values.comments || null,
                    },
                    freeze: true,
                    freeze_message: "Saving...",
                    callback: () => {
                        frappe.show_alert({ message: "P & L document saved", indicator: "green" });
                        d.hide();
                        refresh_list();
                    },
                });
            },
        });
        d.show();
    });

    refresh_list();
}
