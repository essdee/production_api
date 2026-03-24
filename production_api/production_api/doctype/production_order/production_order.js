// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order", {
    setup(frm){
        frm.set_query("production_term", (doc)=> {
            return {
                filters : {
                    "docstatus": 1
                }
            }
        })
    },
    refresh(frm) {
        frm.fields_dict["details_html"].$wrapper.html("")
        if (!frm.is_new()) {
            frm.packed_item = new frappe.production.ui.ProductionOrder(frm.fields_dict["details_html"].wrapper);
            if (frm.doc.__onload && frm.doc.__onload.ordered_details) {
                frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.ordered_details);
                frm.packed_item.load_data(frm.doc.__onload.ordered_details);
            }
        }
        if (frm.doc.docstatus == 1) {
            let pending_request = frm.doc.__onload && frm.doc.__onload.pending_price_request;
            let is_pending = frm.doc.price_approval_status === "Pending Approval" || !!pending_request;
            let is_system_manager = frappe.user_roles.includes("System Manager");

            if (is_pending) {
                frm.dashboard.set_headline(
                    '<span style="color: orange; font-weight: bold;">⏳ Price Change Pending Approval</span>'
                );

                if (is_system_manager) {
                    frm.add_custom_button(__("Approve Price Change"), () => {
                        show_approve_dialog(frm);
                    });
                    frm.change_custom_button_type(__("Approve Price Change"), null, "success");

                    frm.add_custom_button(__("Reject Price Change"), () => {
                        let pending = frm.doc.__onload && frm.doc.__onload.pending_price_request;
                        if (!pending) {
                            frappe.msgprint(__("No pending request found"));
                            return;
                        }
                        frappe.confirm(__("Reject this price change request?"), () => {
                            frappe.call({
                                method: "production_api.production_api.doctype.ppo_price_request.ppo_price_request.reject_ppo_price_request",
                                args: { name: pending.name },
                                callback: function () {
                                    frappe.show_alert({ message: __("Price change rejected"), indicator: "red" });
                                    frm.reload_doc();
                                }
                            });
                        });
                    });
                    frm.change_custom_button_type(__("Reject Price Change"), null, "danger");
                }
            } else {
                frm.add_custom_button("Update Price", () => {
                    let d = new frappe.ui.Dialog({
                        title: "Update Price",
                        size: 'extra-large',
                        fields: [
                            {
                                fieldname: "price_html",
                                fieldtype: "HTML",
                            }
                        ],
                        primary_action: function () {
                            let res = frm.pop_up.get_data()
                            frappe.call({
                                method: "production_api.production_api.doctype.production_order.production_order.update_price",
                                args: {
                                    production_order: frm.doc.name,
                                    item_details: res
                                },
                                callback: function (response) {
                                    if (response.message) {
                                        let status = response.message.status;
                                        if (status === "approved") {
                                            frappe.show_alert({message: __("Price updated successfully"), indicator: "green"});
                                        } else if (status === "pending_approval") {
                                            frappe.show_alert({message: __("Price change sent for System Manager approval"), indicator: "orange"});
                                        } else if (status === "no_change") {
                                            frappe.show_alert({message: __("No price changes detected"), indicator: "blue"});
                                        }
                                    }
                                    frm.reload_doc();
                                }
                            })
                            d.hide();
                        }
                    })
                    frm.pop_up = new frappe.production.ui.UpdatePrice(d.fields_dict.price_html.$wrapper)
                    if (frm.doc.__onload && frm.doc.__onload.items) {
                        frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.items);
                        frm.pop_up.load_data(frm.doc.__onload.items);
                    }
                    d.show();
                })
            }

            frm.add_custom_button("Create Lot", () => {
                let d = new frappe.ui.Dialog({
                    title: "Create Lot",
                    fields: [
                        {
                            fieldname: "lot_name",
                            fieldtype: "Data",
                            label: "Lot Name",
                            reqd: 1,
                        },
                    ],
                    primary_action: function () {
                        let values = d.get_values();
                        if (!values) return;

                        frappe.call({
                            method: "production_api.production_api.doctype.production_order.production_order.create_lot",
                            args: {
                                production_order: frm.doc.name,
                                lot_name: values.lot_name
                            },
                            callback: function (response) {
                                d.hide();
                                frappe.open_in_new_tab = true
                                frappe.set_route("Form", "Lot", response.message);
                            }
                        });
                    }
                });
                d.show();
            })
            if (!frappe.perm.has_perm("Production Order", 0, "submit")) {
                frm.set_df_property("delivery_date", "read_only", true)
                frm.set_df_property("dont_deliver_after", "read_only", true)
                frm.set_df_property("comments", "read_only", true)
                frm.refresh_field("dont_deliver_after")
                frm.refresh_field("comments")
                frm.refresh_field("delivery_date")
            }
            frm.add_custom_button("Print", () => {
                window.open(
                    frappe.urllib.get_full_url(
                        "/printview?doctype=Production Order"
                        + "&name=" + encodeURIComponent(frm.doc.name)
                        + "&format=Production Order"
                        + "&trigger_print=1"
                    ),
                    "_blank"
                );
            })
            frm.add_custom_button("Link Lot", () => {
                let d = new frappe.ui.Dialog({
                    title: "Link Lot",
                    fields: [
                        {
                            fieldname: "lot_name",
                            fieldtype: "Link",
                            label: "Lot Name",
                            reqd: 1,
                            options: "Lot"
                        },
                    ],
                    primary_action: function () {
                        let values = d.get_values();
                        if (!values) return;

                        frappe.call({
                            method: "production_api.production_api.doctype.production_order.production_order.link_lot",
                            args: {
                                production_order: frm.doc.name,
                                lot_name: values.lot_name
                            },
                            callback: function (response) {
                                d.hide();
                                frappe.open_in_new_tab = true
                                frappe.set_route("Form", "Lot", values.lot_name);
                            }
                        });
                    }
                });
                d.show();
            })

            render_price_requests(frm);
        }
    },
    validate(frm) {
        if (!frm.is_new()) {
            if (frm.packed_item) {
                let items = frm.packed_item.get_data();
                frm.doc['item_details'] = JSON.stringify(items);
            }
            else {
                frappe.throw(__('Please refresh and try again.'));
            }
        }
        frappe.call({
            method: "production_api.production_api.doctype.production_order.production_order.get_primary_values",
            args: {
                item: cur_frm.doc.item
            },
            callback: function (response) {
                if (cur_frm.doc.docstatus != 0) {
                    disables.value = true
                }
                primary_values.value = response.message || [];
                primary_values.value.forEach(value => {
                    if (!(value in box_qty.value)) {
                        box_qty.value[value] = 0;
                    }
                });
            }
        })
    },
});

function show_approve_dialog(frm) {
    let pending = frm.doc.__onload && frm.doc.__onload.pending_price_request;
    if (!pending) {
        frappe.msgprint(__("No pending request found"));
        return;
    }

    let details = pending.details || [];
    let html = '<table class="table table-bordered table-sm">';
    html += '<thead><tr><th>Size</th>';
    html += '<th>Old MRP</th><th>New MRP</th>';
    html += '<th>Old Wholesale</th><th>New Wholesale</th>';
    html += '<th>Old Retail</th><th>New Retail</th>';
    html += '</tr></thead><tbody>';

    details.forEach(d => {
        let mrp_changed = d.old_mrp !== d.new_mrp;
        let ws_changed = d.old_wholesale_price !== d.new_wholesale_price;
        let rt_changed = d.old_retail_price !== d.new_retail_price;

        html += '<tr>';
        html += `<td><strong>${d.size}</strong></td>`;
        html += `<td>${d.old_mrp}</td>`;
        html += `<td style="${mrp_changed ? 'background:#fff3cd;font-weight:bold;' : ''}">${d.new_mrp}</td>`;
        html += `<td>${d.old_wholesale_price}</td>`;
        html += `<td style="${ws_changed ? 'background:#fff3cd;font-weight:bold;' : ''}">${d.new_wholesale_price}</td>`;
        html += `<td>${d.old_retail_price}</td>`;
        html += `<td style="${rt_changed ? 'background:#fff3cd;font-weight:bold;' : ''}">${d.new_retail_price}</td>`;
        html += '</tr>';
    });
    html += '</tbody></table>';
    html += `<p class="text-muted">Requested by <strong>${pending.requested_by}</strong> on ${frappe.datetime.str_to_user(pending.requested_at)}</p>`;

    let d = new frappe.ui.Dialog({
        title: __("Approve Price Change - {0}", [pending.name]),
        size: "large",
        fields: [
            {
                fieldname: "price_comparison",
                fieldtype: "HTML",
                options: html
            }
        ],
        primary_action_label: __("Approve"),
        primary_action: function () {
            frappe.call({
                method: "production_api.production_api.doctype.ppo_price_request.ppo_price_request.approve_ppo_price_request",
                args: { name: pending.name },
                callback: function () {
                    frappe.show_alert({ message: __("Price change approved"), indicator: "green" });
                    d.hide();
                    frm.reload_doc();
                }
            });
        },
        secondary_action_label: __("Reject"),
        secondary_action: function () {
            frappe.call({
                method: "production_api.production_api.doctype.ppo_price_request.ppo_price_request.reject_ppo_price_request",
                args: { name: pending.name },
                callback: function () {
                    frappe.show_alert({ message: __("Price change rejected"), indicator: "red" });
                    d.hide();
                    frm.reload_doc();
                }
            });
        }
    });
    d.show();
}

function render_price_requests(frm) {
    let wrapper = frm.fields_dict.ppo_price_request_html;
    if (!wrapper) return;
    let $wrapper = wrapper.$wrapper;
    $wrapper.html("");

    let requests = (frm.doc.__onload && frm.doc.__onload.price_requests) || [];
    if (requests.length === 0) {
        $wrapper.html('<div class="text-muted" style="padding:15px;">No price change requests</div>');
        return;
    }

    let html = '<div style="padding:10px 0;">';
    html += '<table class="table table-bordered table-sm">';
    html += '<thead><tr>';
    html += '<th>Request</th><th>Status</th><th>Requested By</th><th>Requested At</th>';
    html += '<th>Approved/Rejected By</th><th>Approved/Rejected At</th>';
    html += '</tr></thead><tbody>';

    requests.forEach(r => {
        let status_color = r.status === "Approved" ? "green" : r.status === "Rejected" ? "red" : "orange";

        html += '<tr>';
        html += `<td><a href="/app/ppo-price-request/${r.name}">${r.name}</a></td>`;
        html += `<td><span class="indicator-pill ${status_color}">${r.status}</span></td>`;
        html += `<td>${frappe.user.full_name(r.requested_by)}</td>`;
        html += `<td>${frappe.datetime.str_to_user(r.requested_at) || ""}</td>`;
        html += `<td>${r.approved_by ? frappe.user.full_name(r.approved_by) : ""}</td>`;
        html += `<td>${r.approved_at ? frappe.datetime.str_to_user(r.approved_at) : ""}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    $wrapper.html(html);
}
