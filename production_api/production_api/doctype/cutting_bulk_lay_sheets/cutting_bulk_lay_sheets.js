// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

const bulk_method =
    "production_api.production_api.doctype.cutting_bulk_lay_sheets.cutting_bulk_lay_sheets";

frappe.ui.form.on("Cutting Bulk Lay Sheets", {
    setup(frm) {
        frm.set_query("cutting_plan", "lot_details", (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            return {
                filters: {
                    lot: row.lot || "",
                    docstatus: 1,
                    cp_status: ["!=", "Completed"],
                },
            };
        });
        frm.set_query("cutting_marker", "lot_details", (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            return {
                filters: {
                    cutting_plan: row.cutting_plan || "",
                    docstatus: 1,
                },
            };
        });
        frm.set_query("active_cutting_laysheet", () => ({
            filters: { cutting_bulk_lay_sheet: frm.doc.name },
        }));
    },

    refresh(frm) {
        frm._bulk_editor_dirty = false;
        $(frm.fields_dict.workflow_html.wrapper).empty();
        $(frm.fields_dict.cloths_html.wrapper).siblings(".bulk-editor-note").remove();
        $(frm.fields_dict.cloths_html.wrapper).empty();
        $(frm.fields_dict.accessory_html.wrapper).empty();
        $(frm.fields_dict.bundles_html.wrapper).empty();
        const setup_locked = (frm.doc.lot_details || []).some(row => row.cutting_laysheet);
        ["main_lot", "from_location", "posting_date", "cutting_spreader", "cutter"].forEach(
            fieldname => frm.set_df_property(fieldname, "read_only", setup_locked)
        );
        render_bulk_workflow(frm);
        mount_bulk_editor(frm);
        render_active_bundles(frm);
        add_bulk_actions(frm);
    },

    validate(frm) {
        if (!frm._bulk_editor_dirty || !frm.bulk_laysheet || !frm.bulk_accessory) {
            delete frm.doc.item_details;
            delete frm.doc.item_accessory_details;
            return;
        }
        frm.doc.item_details = JSON.stringify(frm.bulk_laysheet.get_items());
        frm.doc.item_accessory_details = JSON.stringify(frm.bulk_accessory.get_items());
    },
});

frappe.ui.form.on("Cutting Bulk Lay Sheet Detail", {
    lot(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "cutting_plan", "");
        frappe.model.set_value(cdt, cdn, "cutting_marker", "");
    },
    cutting_plan(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "cutting_marker", "");
    },
});

function escape_bulk(value) {
    return frappe.utils.escape_html(String(value || ""));
}

function bulk_route_link(doctype, name, label) {
    if (!name) return '<span class="text-muted">—</span>';
    return `<a href="#" class="bulk-record-link" data-doctype="${escape_bulk(doctype)}" data-name="${escape_bulk(name)}">${escape_bulk(label || name)}</a>`;
}

function status_colour(status) {
    if (status === "Completed") return "green";
    if (status === "Ready to Print") return "blue";
    if (status.includes("Submit") || status.includes("Approval")) return "orange";
    if (status.includes("Cancelled") || status.includes("Missing")) return "red";
    return "gray";
}

function render_bulk_workflow(frm) {
    const rows = frm.doc.lot_details || [];
    const wrapper = $(frm.fields_dict.workflow_html.wrapper);
    if (!rows.length) {
        wrapper.html(`
            <div class="text-muted bulk-empty-state">
                Add the split lots above. Each lot will become a separate work card here.
            </div>
        `);
        return;
    }

    const cards = rows.map((row, index) => {
        const active = row.cutting_laysheet && row.cutting_laysheet === frm.doc.active_cutting_laysheet;
        const status = row.status || "Create Lay Sheet";
        return `
            <div role="button" tabindex="0" class="bulk-lot-card ${active ? "is-active" : ""}"
                 data-laysheet="${escape_bulk(row.cutting_laysheet)}">
                <div class="bulk-card-topline">
                    <span class="bulk-card-index">${index + 1}</span>
                    <strong>${escape_bulk(row.lot)}</strong>
                    <span class="indicator-pill ${status_colour(status)}">${escape_bulk(status)}</span>
                </div>
                <div class="bulk-card-grid">
                    <span>Plan</span><strong>${escape_bulk(row.cutting_plan)}</strong>
                    <span>Marker</span><strong>${escape_bulk(row.cutting_marker)}</strong>
                    <span>Lay Sheet</span><span>${bulk_route_link("Cutting LaySheet", row.cutting_laysheet)}</span>
                    <span>Transfer</span><span>${bulk_route_link("Lot Transfer", row.lot_transfer)}</span>
                    <span>DC</span><span>${bulk_route_link("Delivery Challan", row.delivery_challan)}</span>
                </div>
            </div>
        `;
    }).join("");

    wrapper.html(`
        <style>
            .bulk-lot-card-wrap { display:grid; grid-template-columns:repeat(auto-fit,minmax(285px,1fr)); gap:12px; }
            .bulk-lot-card { text-align:left; border:1px solid var(--border-color); border-radius:10px; padding:14px; background:var(--card-bg); color:var(--text-color); transition:.15s ease; }
            .bulk-lot-card:hover { border-color:var(--primary); box-shadow:0 2px 8px rgba(0,0,0,.08); }
            .bulk-lot-card.is-active { border:2px solid var(--primary); padding:13px; background:var(--control-bg); }
            .bulk-card-topline { display:flex; align-items:center; gap:8px; margin-bottom:12px; }
            .bulk-card-topline .indicator-pill { margin-left:auto; white-space:nowrap; }
            .bulk-card-index { display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:var(--subtle-fg); font-size:12px; }
            .bulk-card-grid { display:grid; grid-template-columns:70px minmax(0,1fr); gap:5px 10px; font-size:12px; }
            .bulk-card-grid > span:nth-child(odd) { color:var(--text-muted); }
            .bulk-card-grid strong, .bulk-card-grid a { overflow-wrap:anywhere; }
            .bulk-empty-state { padding:24px; text-align:center; border:1px dashed var(--border-color); border-radius:8px; }
            .bulk-editor-note { margin:8px 0 16px; padding:10px 12px; border-radius:6px; background:var(--control-bg); }
        </style>
        <div class="bulk-lot-card-wrap">${cards}</div>
    `);

    wrapper.find(".bulk-record-link").on("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        frappe.set_route("Form", $(this).data("doctype"), $(this).data("name"));
    });
    wrapper.find(".bulk-lot-card").on("click", async function () {
        const laysheet = $(this).data("laysheet");
        if (!laysheet || laysheet === frm.doc.active_cutting_laysheet) return;
        await save_bulk_editor(frm);
        await frappe.call({
            method: `${bulk_method}.set_active_laysheet`,
            args: { doc_name: frm.doc.name, cutting_laysheet: laysheet },
            freeze: true,
            freeze_message: __("Opening split lot..."),
        });
        frm.reload_doc();
    });
}

function mount_bulk_editor(frm) {
    const data = frm.doc.__onload && frm.doc.__onload.active_laysheet;
    if (!data) return;
    const row = get_active_bulk_row(frm);
    const locked = data.context.read_only;
    const note = locked
        ? __("Stock processing has started for this lot. Cloth and accessory entries are now locked.")
        : __("Enter the cloth and accessory usage for this split lot, then save before generating bundles.");
    $(frm.fields_dict.cloths_html.wrapper).before(
        `<div class="bulk-editor-note"><strong>${escape_bulk(row ? row.lot : "")}</strong> · ${escape_bulk(data.context.name)}<br><span class="text-muted">${escape_bulk(note)}</span></div>`
    );

    const context = Object.assign({}, data.context, {
        mark_dirty: () => {
            frm._bulk_editor_dirty = true;
            frm.dirty();
        },
    });
    frm.bulk_laysheet = new frappe.production.ui.LaySheetCloths(
        frm.fields_dict.cloths_html.wrapper,
        context
    );
    frm.bulk_laysheet.load_data(data.item_details);
    frm.bulk_accessory = new frappe.production.ui.LaySheetAccessory(
        frm.fields_dict.accessory_html.wrapper,
        context
    );
    frm.bulk_accessory.load_data(data.item_accessories);
}

function get_active_bulk_row(frm) {
    return (frm.doc.lot_details || []).find(
        row => row.cutting_laysheet === frm.doc.active_cutting_laysheet
    );
}

function render_active_bundles(frm) {
    const wrapper = $(frm.fields_dict.bundles_html.wrapper);
    const data = frm.doc.__onload && frm.doc.__onload.active_laysheet;
    if (!data) return;

    const bundles = data.bundles || [];
    const row = get_active_bulk_row(frm);
    const lot = row ? row.lot : "";
    const laysheet = data.context.name || "";
    if (!bundles.length) {
        wrapper.html(`
            <div class="bulk-bundle-empty text-muted">
                ${escape_bulk(__("No bundles have been generated for {0} yet.", [lot || laysheet]))}
            </div>
        `);
        return;
    }

    const totalPieces = bundles.reduce(
        (total, bundle) => total + Number(bundle.quantity || 0),
        0
    );
    const bundleRows = bundles.map((bundle, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escape_bulk(bundle.bundle_no)}</td>
            <td>${escape_bulk(bundle.size)}</td>
            <td>${escape_bulk(bundle.colour)}</td>
            <td>${escape_bulk(bundle.shade)}</td>
            <td>${escape_bulk(bundle.part)}</td>
            <td class="text-right">${escape_bulk(bundle.quantity)}</td>
            <td>${bundle.is_moved ? escape_bulk(__("Yes")) : escape_bulk(__("No"))}</td>
        </tr>
    `).join("");

    wrapper.html(`
        <style>
            .bulk-bundle-summary { display:flex; flex-wrap:wrap; align-items:center; gap:8px 18px; margin-bottom:10px; }
            .bulk-bundle-summary .text-muted { font-size:12px; }
            .bulk-bundle-table-wrap { max-height:420px; overflow:auto; border:1px solid var(--border-color); border-radius:8px; }
            .bulk-bundle-table { margin:0; white-space:nowrap; }
            .bulk-bundle-table thead th { position:sticky; top:0; z-index:1; background:var(--card-bg); }
            .bulk-bundle-empty { padding:20px; text-align:center; border:1px dashed var(--border-color); border-radius:8px; }
        </style>
        <div class="bulk-bundle-summary">
            <strong>${escape_bulk(lot)} · ${escape_bulk(laysheet)}</strong>
            <span class="text-muted">${escape_bulk(__("Bundles"))}: ${bundles.length}</span>
            <span class="text-muted">${escape_bulk(__("Total Pieces"))}: ${escape_bulk(totalPieces)}</span>
        </div>
        <div class="bulk-bundle-table-wrap">
            <table class="table table-sm table-bordered bulk-bundle-table">
                <thead>
                    <tr>
                        <th>${escape_bulk(__("S.No"))}</th>
                        <th>${escape_bulk(__("Bundle No"))}</th>
                        <th>${escape_bulk(__("Size"))}</th>
                        <th>${escape_bulk(__("Colour"))}</th>
                        <th>${escape_bulk(__("Shade"))}</th>
                        <th>${escape_bulk(__("Part"))}</th>
                        <th class="text-right">${escape_bulk(__("Quantity"))}</th>
                        <th>${escape_bulk(__("Moved"))}</th>
                    </tr>
                </thead>
                <tbody>${bundleRows}</tbody>
            </table>
        </div>
    `);
}

async function save_bulk_editor(frm) {
    if (frm.is_dirty()) {
        await frm.save();
        frm._bulk_editor_dirty = false;
        delete frm.doc.item_details;
        delete frm.doc.item_accessory_details;
    }
}

function add_bulk_actions(frm) {
    if (frm.is_new()) return;
    const rows = frm.doc.lot_details || [];
    if (rows.some(row => !row.cutting_laysheet)) {
        frm.add_custom_button(__("Create Lay Sheets"), async () => {
            await save_bulk_editor(frm);
            await frappe.call({
                method: `${bulk_method}.create_laysheets`,
                args: { doc_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Creating lay sheets..."),
            });
            frm.reload_doc();
        }).addClass("btn-primary");
    }

    const row = get_active_bulk_row(frm);
    if (!row) return;
    frm.add_custom_button(__("Open Full Lay Sheet"), () => {
        frappe.set_route("Form", "Cutting LaySheet", row.cutting_laysheet);
    }, __("Active Lot"));

    if (["Ready to Generate", "Create Lot Transfer"].includes(row.status) && !row.lot_transfer) {
        frm.add_custom_button(__("Generate Bundles"), () => generate_bulk_bundles(frm, row), __("Active Lot"));
    }
    if (row.status === "Create Lot Transfer" || row.status === "Lot Transfer Cancelled") {
        frm.add_custom_button(__("Create Lot Transfer"), () => create_bulk_transfer(frm, row), __("Active Lot"));
    }
    if (row.lot_transfer) {
        frm.add_custom_button(__("Open Lot Transfer"), () => {
            frappe.set_route("Form", "Lot Transfer", row.lot_transfer);
        }, __("Active Lot"));
    }
    if (row.status === "Make Delivery Challan" || row.status === "Delivery Challan Cancelled") {
        frm.add_custom_button(__("Make Delivery Challan"), () => make_bulk_dc(frm, row), __("Active Lot"));
    }
    if (row.delivery_challan) {
        frm.add_custom_button(__("Open Delivery Challan"), () => {
            frappe.set_route("Form", "Delivery Challan", row.delivery_challan);
        }, __("Active Lot"));
    }
    if (row.status === "Approval Pending") {
        frm.add_custom_button(__("Approve Grammage"), () => approve_bulk_grammage(frm, row), __("Active Lot"));
    }
    if (row.status === "Ready to Print") {
        frm.add_custom_button(__("Print Labels"), () => start_bulk_label_print(frm, row), __("Active Lot"));
    }
}

async function generate_bulk_bundles(frm, row) {
    await save_bulk_editor(frm);
    const laysheet = await frappe.db.get_doc("Cutting LaySheet", row.cutting_laysheet);
    const response = await frappe.call({
        method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_parts",
        args: { cutting_marker: laysheet.cutting_marker },
    });
    let fields = [
        {
            fieldname: "bundle_generated_date",
            fieldtype: "Date",
            label: __("Bundle Generated Date"),
            default: frappe.datetime.nowdate(),
            reqd: 1,
        },
        {
            fieldname: "parts_table",
            fieldtype: "Table",
            label: __("Bundle Groups"),
            fields: [
                { fieldname: "part", fieldtype: "Data", read_only: 1, label: __("Part"), in_list_view: 1 },
                { fieldname: "value", fieldtype: "Int", label: __("Group"), in_list_view: 1, reqd: 1 },
            ],
            data: response.message,
            cannot_add_rows: true,
            cannot_delete_rows: true,
        },
    ];
    if (!laysheet.is_manual_entry) {
        fields = fields.concat([
            {
                fieldname: "maximum_no_of_plys",
                fieldtype: "Int",
                label: __("Maximum No of Plys"),
                default: laysheet.maximum_no_of_plys,
                reqd: 1,
            },
            {
                fieldname: "maximum_allow_percentage",
                fieldtype: "Int",
                label: __("Maximum Allow Percent"),
                default: laysheet.maximum_allow_percentage,
                reqd: 1,
            },
        ]);
    }
    const dialog = new frappe.ui.Dialog({
        title: __("Generate Bundles for {0}", [row.lot]),
        fields,
        primary_action_label: __("Generate Bundles"),
        primary_action: async values => {
            dialog.hide();
            await frappe.call({
                method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_cut_sheet_data",
                args: {
                    doc_name: laysheet.name,
                    cutting_marker: laysheet.cutting_marker,
                    laysheet_details: laysheet.cutting_laysheet_details,
                    manual_item_details: laysheet.cutting_laysheet_manual_items,
                    items: values.parts_table,
                    max_plys: values.maximum_no_of_plys || 0,
                    maximum_allow: values.maximum_allow_percentage || 0,
                    bundle_generated_date: values.bundle_generated_date,
                },
                freeze: true,
                freeze_message: __("Generating bundles..."),
            });
            frm.reload_doc();
        },
    });
    dialog.show();
}

async function create_bulk_transfer(frm, row) {
    await save_bulk_editor(frm);
    const response = await frappe.call({
        method: `${bulk_method}.create_lot_transfer`,
        args: { doc_name: frm.doc.name, detail_name: row.name },
        freeze: true,
        freeze_message: __("Preparing main-lot stock transfer..."),
    });
    frappe.set_route("Form", "Lot Transfer", response.message);
}

async function make_bulk_dc(frm, row) {
    const response = await frappe.call({
        method: `${bulk_method}.prepare_delivery_challan`,
        args: { doc_name: frm.doc.name, detail_name: row.name },
        freeze: true,
        freeze_message: __("Preparing Delivery Challan..."),
    });
    const data = response.message;
    if (data.existing_delivery_challan) {
        frappe.set_route("Form", "Delivery Challan", data.existing_delivery_challan);
        return;
    }

    sessionStorage.setItem("prefilled_delivery_challan", "1");
    sessionStorage.setItem("delivery_challan_onload_data", JSON.stringify(data.item_details));
    const dc = frappe.model.get_new_doc("Delivery Challan");
    dc.naming_series = "DC-";
    dc.posting_date = frappe.datetime.nowdate();
    dc.posting_time = new Date().toTimeString().split(" ")[0];
    dc.actual_date = frappe.datetime.nowdate();
    [
        "work_order", "lot", "item", "production_detail", "process_name",
        "includes_packing", "is_internal_unit", "from_location", "from_address",
        "from_address_details", "supplier", "supplier_name", "supplier_address",
        "supplier_address_details", "cutting_bulk_lay_sheet",
        "cutting_bulk_lay_sheet_detail", "comments",
    ].forEach(field => dc[field] = data[field]);
    frappe.set_route("Form", dc.doctype, dc.name);
}

async function approve_bulk_grammage(frm, row) {
    await frappe.call({
        method: `${bulk_method}.approve_laysheet_grammage`,
        args: { doc_name: frm.doc.name, detail_name: row.name },
        freeze: true,
        freeze_message: __("Approving grammage..."),
    });
    frm.reload_doc();
}

async function start_bulk_label_print(frm, row) {
    const response = await frappe.call({
        method: `${bulk_method}.get_label_print_context`,
        args: { doc_name: frm.doc.name, detail_name: row.name },
        freeze: true,
        freeze_message: __("Checking transfer and Delivery Challan..."),
    });
    const context = response.message;
    if (context.approval_required) {
        frappe.msgprint({
            title: __("Approval Required"),
            message: __("Weight difference ({0} kg) exceeds tolerance ({1} kg).", [
                Number(context.difference).toFixed(4),
                Number(context.tolerance).toFixed(4),
            ]),
            indicator: "orange",
        });
        frm.reload_doc();
        return;
    }

    try {
        await frappe.ui.form.qz_connect();
        const printers = await frappe.ui.form.qz_get_printer_list();
        show_bulk_printer_dialog(frm, row, context, printers);
    } catch (error) {
        frappe.ui.form.qz_fail(error);
    }
}

function show_bulk_printer_dialog(frm, row, context, printers) {
    const dialog = new frappe.ui.Dialog({
        title: __("Print Labels for {0}", [row.lot]),
        size: "small",
        fields: [
            { fieldname: "printer_list_html", fieldtype: "HTML" },
            {
                fieldname: "print_order",
                fieldtype: "Select",
                options: ["Panel", "Bundle No"],
                label: __("Print Order By"),
                default: "Panel",
            },
        ],
        primary_action_label: __("Print"),
        primary_action: values => {
            const checked = dialog.$wrapper.find(".bulk-printer:checked");
            if (checked.length !== 1) {
                frappe.throw(checked.length ? __("Select only one printer.") : __("Select a printer."));
            }
            const printer = checked.first().data("printer");
            dialog.hide();
            print_bulk_labels(frm, row, context, printer, values.print_order);
        },
    });
    const html = printers.map(printer => `
        <label style="display:flex;gap:10px;align-items:center;padding:8px;border-bottom:1px solid var(--border-color);">
            <input type="radio" name="bulk-printer" class="bulk-printer" data-printer="${escape_bulk(printer)}">
            <span>${escape_bulk(printer)}</span>
        </label>
    `).join("");
    dialog.fields_dict.printer_list_html.$wrapper.html(html);
    dialog.show();
}

async function print_bulk_labels(frm, row, context, printer, print_order) {
    await frappe.call({
        method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.update_cutting_plan",
        args: { cutting_laysheet: context.cutting_laysheet, check_cp: true },
    });
    const response = await frappe.call({
        method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.print_labels",
        args: {
            print_items: context.print_items,
            lay_no: context.lay_no,
            doc_name: context.cutting_laysheet,
            print_order,
            cutting_plan: context.cutting_plan,
        },
        freeze: true,
        freeze_message: __("Preparing labels..."),
    });
    const result = response.message;
    const config = qz.configs.create(printer);
    await qz.print(config, [result.zpl]);
    await frappe.call({
        method: `${bulk_method}.mark_labels_printed`,
        args: {
            doc_name: frm.doc.name,
            detail_name: row.name,
            goods_received_note: result.grn,
        },
        freeze: true,
        freeze_message: __("Completing label print..."),
    });
    frm.reload_doc();
}
