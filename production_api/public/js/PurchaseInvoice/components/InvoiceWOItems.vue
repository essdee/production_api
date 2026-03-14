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
            <template v-if="user_role === 'merch_manager' && !all_wo_closed && !override_pi_approve">
                <div class="text-danger" style="font-weight: 500; margin-bottom: 10px;">
                    Cannot approve: The following Work Orders are not closed
                </div>
                <div v-for="wo in open_work_orders" :key="wo" style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span>{{ wo }}</span>
                    <button class="btn btn-xs btn-danger" @click="closeWorkOrder(wo)">Close</button>
                </div>
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
                if (r.message === 'merch_manager' && cur_frm.doc.against === 'Work Order') {
                    frappe.db.get_single_value("MRP Settings", "override_pi_approve").then(val => {
                        override_pi_approve.value = !!val
                        if (!val) {
                            frappe.call({
                                method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.check_all_wo_closed",
                                args: { purchase_invoice: cur_frm.doc.name },
                                callback: function(res){
                                    if(res.message){
                                        all_wo_closed.value = res.message.all_closed
                                        open_work_orders.value = res.message.open_work_orders || []
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
    frappe.db.get_value("Work Order", wo, "production_detail").then(r => {
        let production_detail = r.message.production_detail;
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
                                {
                                    fieldtype: "Select", fieldname: "close_reason", label: "Close Reason",
                                    options: "\nCutting Shortage\nPrinting Shortage\nSewing Shortage\nSewing Missing\nOthers",
                                    reqd: 1,
                                },
                                {
                                    fieldtype: "Data", fieldname: "close_other_reason", label: "Other Reason",
                                    depends_on: "eval: doc.close_reason == 'Others'",
                                    mandatory_depends_on: "eval: doc.close_reason == 'Others'",
                                },
                                { fieldtype: "Small Text", fieldname: "close_remarks", label: "Close Remarks" },
                            ],
                            primary_action_label: "Close Work Order",
                            size: "extra-large",
                            primary_action() {
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
                                                if (open_work_orders.value.length === 0) {
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