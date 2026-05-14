<template>
    <div>
        <div class="mb-4">
            <h4>Amount Details</h4>
            <table class="table table-sm table-sm-bordered bordered-table">
                <tr>
                    <th>S.No</th>
                    <th>Item</th>
                    <th>Lot</th>
                    <th>Rate</th>
                    <th>Quantity</th>
                    <template v-if="gst_state && gst_state == 'In-State'">
                        <th>CGST</th>
                        <th>SGST</th>
                    </template>
                    <template v-if="gst_state == 'Out-State'">
                        <th>IGST</th>
                    </template>
                    <th>Amount</th>
                    <th v-if="gst_state">Total</th>
                </tr>
                <tr v-for="(cost_data, idx) in cost_value">
                    <td>{{ idx + 1 }}</td>
                    <td>{{ cost_data['item'] }}</td>
                    <td>{{ cost_data['lot'] }}</td>
                    <td>{{ cost_data['rate'] }}</td>
                    <td>{{ cost_data['qty'] }}</td>
                    <template v-if="gst_state && gst_state == 'In-State'">
                        <td>{{ (cost_data['igst']/2).toFixed(2) }}</td>
                        <td>{{ (cost_data['igst']/2).toFixed(2) }}</td>
                    </template>
                    <template v-if="gst_state == 'Out-State'">
                        <td>{{ cost_data['igst'] }}</td>
                    </template>
                    <th>{{ cost_data['total_amount'] }}</th>
                    <th v-if="gst_state">{{ parseInt(cost_data['total_amount']) + parseInt(cost_data['igst']) }}</th>
                </tr>
                <tr>
                    <th>Total</th>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <template v-if="gst_state && gst_state == 'In-State'">
                        <th>{{ (total_tax/2).toFixed(2) }}</th>
                        <th>{{ (total_tax/2).toFixed(2) }}</th>
                    </template>
                    <template v-if="gst_state == 'Out-State'">
                        <th>{{ total_tax }}</th>
                    </template>
                    <th>{{ total_amount }}</th>
                    <th  v-if="gst_state">{{ parseInt(total_amount) + parseInt(total_tax) }}</th>
                </tr>
            </table>
        </div>
        <div v-if="items && items.length > 0">
            <div v-for="item in items">
                <h4>{{ item['work_order'] }}</h4>
                <div v-if="item['bills'].length > 0">
                    <h5>Purchase Invoice List</h5>
                    <table class="table table-sm table-sm-bordered bordered-table small-width">
                        <tr>
                            <th>S.No</th>
                            <th>Purchase Invoice</th>
                        </tr>
                        <tr v-for="(pi, idx) in item['bills']">
                            <td>{{ idx + 1 }}</td>
                            <td style="cursor: pointer;" @click="redirect_to(pi['pi_name'])">{{ pi['pi_name'] }}</td>
                        </tr>
                    </table>
                </div>
                <h5>{{ item['lot'] }} - {{ item['item_name'] }}</h5>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>S.No</th>
                            <th>{{item['packing_attr']}}</th>
                            <th v-if="item['is_set_item']">{{ item['set_attr'] }}</th>
                            <th>Type</th>
                            <th v-for="size in item['sizes']">{{ size }}</th>
                            <th>Total</th>
                        </tr>
                    </thead>    
                    <tbody class="dark-border">
                        <template v-for="(colour, idx) in Object.keys(item['colours'])">
                            <tr>
                                <td :rowspan="6">{{ idx + 1 }}</td>
                                <td :rowspan="6">{{ colour.split("@")[0] }}</td>
                                <td :rowspan="6" v-if="item['is_set_item']">{{ item['colours'][colour]['part'] }}</td>
                                <td>Total Delivered</td>
                                <td v-for="size in item['sizes']">{{ item['colours'][colour]['data'][size]['total_delivered'] }}</td>
                                <th>{{ item['total_qty'][colour]['total_delivered'] }}</th>
                            </tr>
                            <tr>
                                <td>Total Received</td>
                                <td v-for="size in item['sizes']">{{ item['colours'][colour]['data'][size]['total_received'] }}</td>
                                <th>{{ item['total_qty'][colour]['total_received'] }}</th>
                            </tr>
                            <tr>
                               <td>Difference</td>
                               <td v-for="size in item['sizes']">
                                    {{ item['colours'][colour]['data'][size]['total_delivered'] - item['colours'][colour]['data'][size]['total_received'] }}
                                </td>
                               <th>{{ item['total_qty'][colour]['total_delivered'] - item['total_qty'][colour]['total_received'] }}</th>
                            </tr>
                            <tr>
                                <td>Total Billed</td>
                                <td v-for="size in item['sizes']">{{ item['colours'][colour]['data'][size]['billed'] }}</td>
                                <th>{{ item['total_qty'][colour]['total_billed'] }}</th>
                            </tr>
                            <tr>
                                <td>Pending For Bill</td>
                                <td v-for="size in item['sizes']">{{ item['colours'][colour]['data'][size]['total_received'] - item['colours'][colour]['data'][size]['billed'] }}</td>
                                <th>{{ item['total_qty'][colour]['total_received'] - item['total_qty'][colour]['total_billed'] }}</th>
                            </tr>
                            <tr>
                                <td>GRN Quantity</td>
                                <td v-for="size in item['sizes']">{{ item['colours'][colour]['data'][size]['quantity'] }}</td>
                                <th>{{ item['total_qty'][colour]['total_quantity'] }}</th>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
        </div>
        <div style="text-align: end;" v-if="docstatus == 0 && !approved_by && user_role">
            <!-- merch_manager + open WOs + no override: block approve, show Close/Approve Close buttons -->
            <template v-if="user_role === 'merch_manager' && !all_wo_closed && !override_pi_approve">
                <div class="text-danger" style="font-weight: 500; margin-bottom: 10px;">
                    Cannot approve: The following Work Orders are not closed
                </div>
                <div v-for="wo in open_work_orders" :key="wo" style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span>{{ wo }}</span>
                    <button class="btn btn-xs btn-danger" @click="closeWorkOrder(wo)">Close</button>
                </div>
                <div v-for="wo in close_request_wos" :key="'cr-'+wo" style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span>{{ wo }}</span>
                    <span class="text-warning" style="font-size: 12px; font-weight: 500;">Close Requested</span>
                    <button class="btn btn-xs btn-warning" @click="closeWorkOrder(wo)">Approve Close</button>
                </div>
            </template>
            <!-- non-merch-manager + open WOs: show Request Close buttons (only for truly open), don't block approve -->
            <template v-else-if="user_role !== 'merch_manager' && !all_wo_closed && !override_pi_approve">
                <div class="text-warning" style="font-weight: 500; margin-bottom: 10px;">
                    The following Work Orders are not closed
                </div>
                <div v-for="wo in open_work_orders" :key="wo" style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span>{{ wo }}</span>
                    <button class="btn btn-xs btn-warning" @click="closeWorkOrder(wo)">Request Close</button>
                </div>
                <div v-for="wo in close_request_wos" :key="'cr-'+wo" style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span>{{ wo }}</span>
                    <span class="text-muted" style="font-size: 12px;">Close Requested</span>
                </div>
                <button class="btn btn-success" style="margin-top: 10px;" @click="approve()">Approve</button>
            </template>
            <button v-else class="btn btn-success" @click="approve()">Approve</button>
        </div>
    </div>
</template>
<script setup>

import { ref, onMounted } from 'vue';

let items = ref([])
let cost_value = ref([])
let total_amount = ref(0)
let docstatus = cur_frm.doc.docstatus
let user_role = ref(null)
let approved_by = cur_frm.doc.approved_by
let senior_approved = cur_frm.doc.senior_merch_approved_by
let gst_state = cur_frm.doc.gst_state
let total_tax = ref(0)
let all_wo_closed = ref(true)
let open_work_orders = ref([])
let close_request_wos = ref([])
let override_pi_approve = ref(false)

onMounted(() => {
    const grouped = {}
    cur_frm.doc.items.forEach(row => {
        const key = `${row.lot}_${row.item}_${row.rate}_${row.tax}`
        if (!grouped[key]) {
            grouped[key] = {
                lot: row.lot,
                item: row.item,
                rate: row.rate,
                qty: row.qty || 0,
                tax: row.tax,
            }
        } else {
            grouped[key].qty += row.qty || 0
        }
    })
    Object.keys(grouped).forEach((key)=> {
        let amt = grouped[key]['rate'] * grouped[key]['qty']
        grouped[key]['total_amount'] = amt
        if(gst_state){
            let tax_amt = (amt/100) * grouped[key]['tax']
            grouped[key]['igst'] = tax_amt
            total_tax.value += tax_amt
        }
        total_amount.value += amt
    })
    cost_value.value = Object.values(grouped)
    frappe.call({
        method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.get_merch_roles",
        callback: function(r){
            if(r.message){
                user_role.value = r.message
                if (cur_frm.doc.against === 'Work Order') {
                    frappe.db.get_single_value("MRP Settings", "override_pi_approve").then(val => {
                        override_pi_approve.value = val
                        if (!val) {
                            frappe.call({
                                method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.check_all_wo_closed",
                                args: { purchase_invoice: cur_frm.doc.name },
                                callback: function(res){
                                    if(res.message){
                                        all_wo_closed.value = res.message.all_closed
                                        open_work_orders.value = res.message.open_work_orders || []
                                        close_request_wos.value = res.message.close_request_wos || []
                                    }
                                }
                            })
                        }
                    })
                }
            }
        }
    })
})

function load_data(data){
    items.value = data
}

function approve(){
    let d = new frappe.ui.Dialog({
        title: "Are you sure want to Approve this Invoice",
        fields: [
            {
                "fieldname": "comments",
                "fieldtype": "Small Text",
                "label": "Comments",
            }
        ],
        primary_action_label: "Yes",
        secondary_action_label: "No",
        primary_action(values){
            cur_frm.dirty()
            d.hide()
            console.log(user_role)
            if (user_role.value === 'merch_manager') {
                cur_frm.set_value("status", "Approved")
                if (!senior_approved) {
                    cur_frm.doc.approved_by = frappe.session.user
                    cur_frm.set_value("approved_by", frappe.session.user);
                    cur_frm.set_value("senior_merch_approved_by", frappe.session.user);
                } 
                else {
                    console.log("YESS")
                    cur_frm.set_value("approved_by", frappe.session.user);
                }
            } 
            else if (user_role.value === 'senior_merch') {
                cur_frm.set_value("status", "Approval Pending")
                cur_frm.set_value("senior_merch_approved_by", frappe.session.user);
            }
            else if(cur_frm.doc.status == 'Draft'){
                cur_frm.set_value("status", "Approval Initiated")
            }
            cur_frm.refresh_field("approved_by")
            cur_frm.refresh_field("senior_merch_approved_by")
            cur_frm.add_child("purchase_invoice_wo_approval_details", {
                user: frappe.session.user,
                approved_time: frappe.datetime.now_datetime(),
                comments: values.comments
            });

            cur_frm.refresh_field("purchase_invoice_wo_approval_details");
            cur_frm.save()
        },
        secondary_action(){
            d.hide()
        }
    })
    d.show()
}

function redirect_to(docname) {
    frappe.open_in_new_tab = true;
    frappe.set_route("Form", "Purchase Invoice", docname);
}

function closeWorkOrder(wo) {
    frappe.db.get_value("Work Order", wo, ["production_detail", "close_reason", "close_other_reason", "close_remarks"]).then(r => {
        let production_detail = r.message.production_detail;
        let wo_close_reason = r.message.close_reason || "";
        let wo_close_other_reason = r.message.close_other_reason || "";
        let wo_close_remarks = r.message.close_remarks || "";
        frappe.call({
            method: "production_api.production_api.doctype.work_order.work_order.fetch_summary_details",
            args: { doc_name: wo, production_detail: production_detail },
            callback: function(r) {
                let item_detail = JSON.parse(JSON.stringify(r.message.item_detail));

                let has_pending = false;
                for (let group of item_detail) {
                    if (!group.items) continue;
                    group.items = group.items.filter(item => {
                        return (item.total_delivered || 0) - (item.total_received || 0) > 0;
                    });
                    if (group.items.length > 0) {
                        has_pending = true;
                        let total_details = {};
                        let overall_planned = 0, overall_delivered = 0, overall_received = 0;
                        for (let item of group.items) {
                            for (let attr of Object.keys(item.values)) {
                                if (!total_details[attr]) {
                                    total_details[attr] = { planned: 0, delivered: 0, received: 0 };
                                }
                                total_details[attr].planned += item.values[attr]?.qty || 0;
                                total_details[attr].delivered += item.values[attr]?.delivered || 0;
                                total_details[attr].received += item.values[attr]?.received || 0;
                            }
                            overall_planned += item.total_qty || 0;
                            overall_delivered += item.total_delivered || 0;
                            overall_received += item.total_received || 0;
                        }
                        group.total_details = total_details;
                        group.overall_planned = overall_planned;
                        group.overall_delivered = overall_delivered;
                        group.overall_received = overall_received;
                    }
                }
                item_detail = item_detail.filter(group => group.items && group.items.length > 0);

                frappe.call({
                    method: "production_api.production_api.doctype.work_order.work_order.get_wo_recut_details",
                    args: { work_order: wo },
                    callback: function(recut_r) {
                        let recut_data = recut_r.message || [];

                        let d = new frappe.ui.Dialog({
                            title: "Pending Items - Close Work Order " + wo,
                            fields: [
                                { fieldtype: "HTML", fieldname: "summary_html" },
                                { fieldtype: "HTML", fieldname: "recut_html" },
                                { fieldtype: "HTML", fieldname: "debit_list_html" },
                                {
                                    fieldtype: "Select", fieldname: "with_debit", label: "Debit",
                                    options: "Without Debit\nWith Debit", default: "Without Debit",
                                },
                                {
                                    fieldtype: "Button", fieldname: "create_debit_btn", label: "Create Debit",
                                    depends_on: "eval: doc.with_debit == 'With Debit' && !doc.wo_debit",
                                },
                                {
                                    fieldtype: "Link", fieldname: "wo_debit", label: "WO Debit",
                                    options: "WO Debit", read_only: 1,
                                    depends_on: "eval: doc.with_debit == 'With Debit'",
                                    mandatory_depends_on: "eval: doc.with_debit == 'With Debit'",
                                },
                                {
                                    fieldtype: "Data", fieldname: "debit_type", label: "Debit Type",
                                    read_only: 1, depends_on: "eval: doc.wo_debit",
                                },
                                {
                                    fieldtype: "Currency", fieldname: "debit_value", label: "Debit Value",
                                    read_only: 1, depends_on: "eval: doc.wo_debit",
                                },
                                { fieldtype: "Section Break", label: "Close Details" },
                                {
                                    fieldtype: "Select", fieldname: "close_reason", label: "Close Reason",
                                    options: "\nCutting Shortage\nPrinting Shortage\nSewing Shortage\nSewing Missing\nOthers",
                                    reqd: 1,
                                    default: wo_close_reason,
                                },
                                {
                                    fieldtype: "Data", fieldname: "close_other_reason", label: "Other Reason",
                                    depends_on: "eval: doc.close_reason == 'Others'",
                                    mandatory_depends_on: "eval: doc.close_reason == 'Others'",
                                    default: wo_close_other_reason,
                                },
                                { fieldtype: "Small Text", fieldname: "close_remarks", label: "Close Remarks", default: wo_close_remarks },
                            ],
                            primary_action_label: "Close Work Order",
                            size: "extra-large",
                            primary_action() {
                                // Gate: merch_manager blocked if unapproved debits
                                if (user_role.value === 'merch_manager' && d.wo_debits && d.wo_debits.some(db => db.status !== "Approved")) {
                                    frappe.msgprint(__("All WO Debits must be approved before closing."));
                                    return;
                                }
                                let values = d.get_values();
                                if (!values) return;
                                d.hide();
                                let x = new frappe.ui.Dialog({
                                    title: "Are you sure want to close this work order",
                                    primary_action_label: "Yes",
                                    secondary_action_label: "No",
                                    primary_action: () => {
                                        x.hide();
                                        frappe.call({
                                            method: "production_api.production_api.doctype.work_order.work_order.update_stock",
                                            args: {
                                                work_order: wo,
                                                close_reason: values.close_reason,
                                                close_other_reason: values.close_other_reason || "",
                                                close_remarks: values.close_remarks || "",
                                            },
                                            callback: function() {
                                                open_work_orders.value = open_work_orders.value.filter(w => w !== wo);
                                                close_request_wos.value = close_request_wos.value.filter(w => w !== wo);
                                                if (open_work_orders.value.length === 0 && close_request_wos.value.length === 0) {
                                                    all_wo_closed.value = true;
                                                }
                                                frappe.show_alert({ message: wo + " closed successfully", indicator: "green" });
                                            },
                                        });
                                    },
                                    secondary_action: () => { x.hide(); },
                                });
                                x.show();
                            },
                        });
                        d.show();

                        // Create Debit button click handler
                        d.fields_dict.create_debit_btn.input.onclick = function() {
                            let debit_d = new frappe.ui.Dialog({
                                title: "Create WO Debit",
                                fields: [
                                    { fieldtype: "Select", fieldname: "debit_type", label: "Debit Type", options: "Permanent", default: "Permanent", reqd: 1, hidden: 1 },
                                    { fieldtype: "Data", fieldname: "debit_no", label: "Debit No", reqd: 1 },
                                    { fieldtype: "Currency", fieldname: "debit_value", label: "Debit Value", reqd: 1 },
                                    { fieldtype: "Small Text", fieldname: "reason", label: "Reason", reqd: 1 },
                                ],
                                primary_action_label: "Create",
                                primary_action(values) {
                                    frappe.call({
                                        method: "frappe.client.insert",
                                        args: {
                                            doc: {
                                                doctype: "WO Debit",
                                                work_order: wo,
                                                debit_type: values.debit_type,
                                                debit_no: values.debit_no,
                                                debit_value: values.debit_value,
                                                reason: values.reason,
                                                on_close: 1,
                                                docstatus: 1,
                                            },
                                        },
                                        callback(r) {
                                            if (r.message) {
                                                frappe.show_alert({ message: __("WO Debit {0} created and submitted", [r.message.name]), indicator: "green" });
                                                debit_d.hide();
                                                d.set_value("wo_debit", r.message.name);
                                                d.set_value("debit_type", r.message.debit_type);
                                                d.set_value("debit_value", r.message.debit_value);
                                                // Re-fetch debit list
                                                _fetch_debit_list(wo, d, user_role.value === 'merch_manager');
                                            }
                                        },
                                    });
                                },
                            });
                            debit_d.show();
                        };

                        // Fetch and render debit list
                        _fetch_debit_list(wo, d, user_role.value === 'merch_manager');

                        let wrapper = d.fields_dict.summary_html.wrapper;
                        if (has_pending) {
                            let summary = new frappe.production.ui.WOSummary(wrapper);
                            summary.load_data(item_detail, [], { show_pending: true, doctype: 'Work Order' });
                        } else {
                            $(wrapper).html('<p class="text-muted text-center" style="padding: 20px;">All items fully received</p>');
                        }

                        let recut_wrapper = $(d.fields_dict.recut_html.wrapper);
                        if (recut_data.length > 0) {
                            let html = '<hr><h4>WO Recut Details</h4>';
                            for (let recut of recut_data) {
                                html += '<div style="margin-bottom: 15px;">'
                                    + '<strong><a href="/app/wo-recut/' + recut.name + '" target="_blank">' + recut.name + '</a></strong>';
                                for (let group of recut.items) {
                                    html += '<table class="table table-sm table-bordered" style="margin-top: 8px;">';
                                    html += '<thead><tr><th>S.No.</th><th>Item</th>';
                                    for (let attr of (group.attributes || [])) { html += '<th>' + attr + '</th>'; }
                                    if (group.primary_attribute) {
                                        for (let pv of (group.primary_attribute_values || [])) { html += '<th>' + pv + '</th>'; }
                                    } else { html += '<th>Quantity</th>'; }
                                    html += '<th>Total</th></tr></thead><tbody>';
                                    for (let idx = 0; idx < group.items.length; idx++) {
                                        let item = group.items[idx];
                                        html += '<tr><td>' + (idx + 1) + '</td><td>' + (item.name || '') + '</td>';
                                        for (let attr of (group.attributes || [])) { html += '<td>' + (item.attributes?.[attr] || '') + '</td>'; }
                                        let total = 0;
                                        if (group.primary_attribute) {
                                            for (let pv of (group.primary_attribute_values || [])) {
                                                let qty = item.values?.[pv]?.qty || 0; total += qty;
                                                html += '<td>' + (qty > 0 ? qty : '--') + '</td>';
                                            }
                                        } else {
                                            let qty = item.values?.['default']?.qty || 0; total = qty;
                                            html += '<td>' + (qty > 0 ? qty : '--') + '</td>';
                                        }
                                        html += '<td><strong>' + total + '</strong></td></tr>';
                                    }
                                    html += '</tbody></table>';
                                }
                                html += '</div>';
                            }
                            recut_wrapper.html(html);
                        }
                    },
                });
            },
        });
    });
}

function _fetch_debit_list(wo, dialog, is_merch_manager) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "WO Debit",
            filters: { work_order: wo, docstatus: 1 },
            fields: ["name", "debit_type", "debit_no", "debit_value", "inspection", "status", "on_close"],
            order_by: "creation asc",
            limit_page_length: 0,
        },
        callback: function(r) {
            let debits = r.message || [];
            dialog.wo_debits = debits;
            let debit_wrapper = $(dialog.fields_dict.debit_list_html.wrapper);

            if (debits.length === 0) {
                debit_wrapper.html('');
                return;
            }

            let has_unapproved = debits.some(db => db.status !== "Approved");
            let show_action = is_merch_manager && has_unapproved;

            let html = '<hr><h4>WO Debit List</h4>';
            html += '<table class="table table-sm table-bordered" style="margin-top: 8px;">';
            html += '<thead><tr><th>S.No.</th><th>Name</th><th>Debit Type</th><th>Debit No</th><th>Debit Value</th><th>Inspection</th><th>Status</th>';
            if (show_action) html += '<th>Action</th>';
            html += '</tr></thead><tbody>';

            let total_value = 0;
            for (let i = 0; i < debits.length; i++) {
                let db = debits[i];
                total_value += flt(db.debit_value);
                let status_color = db.status === "Approved" ? "green" : "orange";
                html += '<tr data-debit="' + db.name + '">';
                html += '<td>' + (i + 1) + '</td>';
                html += '<td><a href="/app/wo-debit/' + db.name + '" target="_blank">' + db.name + '</a></td>';
                html += '<td>' + (db.debit_type || '') + '</td>';
                html += '<td>' + (db.debit_no || '') + '</td>';
                html += '<td>' + format_currency(db.debit_value) + '</td>';
                html += '<td style="text-align: center;"><input type="checkbox" disabled ' + (db.inspection ? 'checked' : '') + '></td>';
                html += '<td class="debit-status"><span style="color: ' + status_color + '; font-weight: bold;">' + db.status + '</span></td>';
                if (show_action) {
                    if (db.status !== "Approved") {
                        html += '<td><button class="btn btn-xs btn-success approve-debit-btn" data-name="' + db.name + '">Approve</button></td>';
                    } else {
                        html += '<td></td>';
                    }
                }
                html += '</tr>';

                // Pre-populate on_close debit into fields
                if (db.on_close) {
                    dialog.set_value("with_debit", "With Debit");
                    dialog.set_value("wo_debit", db.name);
                    dialog.set_value("debit_type", db.debit_type);
                    dialog.set_value("debit_value", db.debit_value);
                }
            }

            // Total row
            html += '<tr><th colspan="4" style="text-align: right;">Total</th>';
            html += '<th>' + format_currency(total_value) + '</th>';
            html += '<th></th>';
            html += '<th></th>';
            if (show_action) html += '<th></th>';
            html += '</tr>';

            html += '</tbody></table>';
            debit_wrapper.html(html);

            // Bind approve button clicks
            if (show_action) {
                debit_wrapper.find('.approve-debit-btn').on('click', function() {
                    let btn = $(this);
                    let debit_name = btn.data('name');
                    frappe.call({
                        method: "production_api.production_api.doctype.wo_debit.wo_debit.approve_debit",
                        args: { name: debit_name },
                        callback: function() {
                            let db = debits.find(d => d.name === debit_name);
                            if (db) db.status = "Approved";
                            dialog.wo_debits = debits;
                            let row = debit_wrapper.find('tr[data-debit="' + debit_name + '"]');
                            row.find('.debit-status').html('<span style="color: green; font-weight: bold;">Approved</span>');
                            btn.closest('td').html('');
                            frappe.show_alert({ message: __("Debit {0} approved", [debit_name]), indicator: "green" });
                        },
                    });
                });
            }
        },
    });
}

defineExpose({
    load_data
})

</script>

<style scoped>
.bordered-table{
    width: 100%;
    border: 1px solid #ccc;
    border-collapse: collapse;
}

.small-width {
    width:50%;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}

.dark-border{
    border: 2px solid black;
}
</style>
