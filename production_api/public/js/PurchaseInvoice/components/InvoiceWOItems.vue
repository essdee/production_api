<template>
    <div>
        <div v-if="approved_by" style="text-align:end;">
            <h4>Approved By Merch Manager</h4>
        </div>
        <div v-if="senior_approved" style="text-align:end;">
            <h4>Approved By Senior Merch</h4>
        </div>
        <div class="mb-4">
            <h4>Amount Details</h4>
            <table class="table table-sm table-sm-bordered bordered-table">
                <tr>
                    <th>S.No</th>
                    <th>Item</th>
                    <th>Lot</th>
                    <th>Rate</th>
                    <th>Quantity</th>
                    <th>Amount</th>
                </tr>
                <tr v-for="(cost_data, idx) in cost_value">
                    <td>{{ idx + 1 }}</td>
                    <td>{{ cost_data['item'] }}</td>
                    <td>{{ cost_data['lot'] }}</td>
                    <td>{{ cost_data['rate'] }}</td>
                    <td>{{ cost_data['qty'] }}</td>
                    <th>{{ cost_data['total_amount'] }}</th>
                </tr>
                <tr>
                    <th>Total</th>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <th>{{ total_amount }}</th>
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
        <div style="text-align: end;" v-if="docstatus == 0 && !approved_by">
            <button class="btn btn-success" @click="approve()">Approve</button>
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

onMounted(() => {
    const grouped = {}
    cur_frm.doc.items.forEach(row => {
        const key = `${row.lot}_${row.item}_${row.rate}`
        if (!grouped[key]) {
            grouped[key] = {
                lot: row.lot,
                item: row.item,
                rate: row.rate,
                qty: row.qty || 0
            }
        } else {
            grouped[key].qty += row.qty || 0
        }
    })
    Object.keys(grouped).forEach((key)=> {
        let amt = grouped[key]['rate'] * grouped[key]['qty']
        grouped[key]['total_amount'] = amt
        total_amount.value += amt
    })
    cost_value.value = Object.values(grouped)
    frappe.call({
        method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.get_merch_roles",
        callback: function(r){
            if(r.message){
                user_role.value = r.message
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
                if (!senior_approved) {
                    console.log("YESSSSSSSSSS")
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
                cur_frm.set_value("senior_merch_approved_by", frappe.session.user);
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