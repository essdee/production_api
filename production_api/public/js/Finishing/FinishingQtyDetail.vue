<template>
    <div>
        <div style="display:flex;width:100%;gap:20px;">
            <div v-if="dc_list && Object.keys(dc_list).length > 0" style="width:50%;">
                <h3>DC List</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Delivery Challan</th>
                            <th>Date Time</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="(date, dc) in dc_list">
                            <td style="cursor: pointer;" @click="redirect_to('Delivery Challan', dc)">{{ dc }}</td>
                            <td>{{ date }}</td>
                            <td>
                                <button class="btn btn-primary" @click="cancel_doc('Delivery Challan', dc)">Cancel</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div v-if="return_list && Object.keys(return_list).length > 0" style="width:50%;">
                <h3>Return Item List</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Return Items</th>
                            <th>Date Time</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="(date, rl) in return_list">
                            <td style="cursor: pointer;" @click="redirect_to('Goods Received Note', rl)">{{ rl }}</td>
                            <td>{{ date }}</td>
                            <td>
                                <button class="btn btn-primary" @click="cancel_doc('Goods Received Note', rl)">Cancel</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>    
        <h3>Inward Details</h3>
        <div style="margin-bottom: 10px;width:100%;display: flex;">
            <div>
                <button class="btn btn-success" @click="return_item()">Return Item</button>
            </div>
            <div style="padding-left: 20px;">
                <button class="btn btn-success" @click="create_dc()">Create DC</button>
            </div>
        </div>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:20px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th style="width:150px;">Type</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border" v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                <tr>
                    <td :rowspan="3">{{ idx + 1 }}</td>
                    <td :rowspan="3">{{ colour.split("@")[0] }}</td>
                    <td :rowspan="3" v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                    <td>Accepted</td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size]['accepted'] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total']['accepted'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Delivered</td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size]['dc_qty'] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total']['dc_qty'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Balance</td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size]['balance'] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total']['balance'] ?? 0 }}</strong></td>
                </tr>
            </tbody>
        </table>
        <h3>Rework Details</h3>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:20px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th style="width:150px;">Type</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border" v-for="(colour, idx) in Object.keys(items['rework_details']['data'])" :key="colour">
                <tr>
                    <td :rowspan="4">{{ idx + 1 }}</td>
                    <td :rowspan="4">{{ colour.split("@")[0] }}</td>
                    <td :rowspan="4" v-if="items.is_set_item">{{ items['rework_details']['data'][colour]['part'] }}</td>
                    <td>Rework Quantity</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <div v-if="items['rework_details']['data'][colour]['values'][size]">
                            {{
                                items['rework_details']['data'][colour]["values"][size]['rework_qty'] ?? 0
                            }}
                        </div>
                        <div v-else>
                            0
                        </div>
                    </td>
                    <td><strong>{{ items['rework_details']['data'][colour]['colour_total']['rework_qty'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Reworked</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <div v-if="items['rework_details']['data'][colour]['values'][size]">
                            {{
                                items['rework_details']['data'][colour]["values"][size]['reworked'] ?? 0
                            }}
                        </div>
                        <div v-else>
                            0
                        </div>
                    </td>
                    <td><strong>{{ items['rework_details']['data'][colour]['colour_total']['reworked'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Pending</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <div v-if="items['rework_details']['data'][colour]['values'][size]">
                            {{
                                items['rework_details']['data'][colour]["values"][size]['pending'] ?? 0
                            }}
                        </div>
                        <div v-else>
                            0
                        </div>
                    </td>
                    <td><strong>{{ items['rework_details']['data'][colour]['colour_total']['pending'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Rejected</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <div v-if="items['rework_details']['data'][colour]['values'][size]">
                            {{
                                items['rework_details']['data'][colour]["values"][size]['rejected'] ?? 0
                            }}
                        </div>
                        <div v-else>
                            0
                        </div>
                    </td>
                    <td><strong>{{ items['rework_details']['data'][colour]['colour_total']['rejected'] ?? 0 }}</strong></td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>

import { ref, createApp } from 'vue';
import ReturnPopUp from "./FinishingReturnPopup.vue";
import FinishingDC from './FinishingDC.vue';

let items = ref(null)
let location = cur_frm.doc.delivery_location
let dc_list = JSON.parse(cur_frm.doc.dc_list || "{}");
let return_list = JSON.parse(cur_frm.doc.return_grn_list || "{}")

function load_data(data){
    items.value = data
}

function cancel_doc(doctype, docname){
    let d = new frappe.ui.Dialog({
        title: `Are you sure want to cancel this ${doctype}`,
        primary_action_label: 'Yes',
        secondary_action_label: "No",
        primary_action(){
            d.hide()
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.cancel_document",
                args: {
                    "doctype": doctype,
                    "docname": docname,
                },
                freeze: true,
                freeze_message: `Cancelling ${doctype}`,
                callback: function(){
                    frappe.show_alert("Cancelled Successfully")
                }
            })
        },
        secondary_action(){
            d.hide()
        }
    })
    d.show()
}

function redirect_to(doctype, docname){
    frappe.open_in_new_tab = true;
    frappe.set_route("Form", doctype, docname);
}

function create_dc(){
    let d = new frappe.ui.Dialog({
        title: __("Enter Quantity to Create DC"),
        fields: [
            {
                "fieldname": "from_location",
                "fieldtype": "Link",
                "options": "Supplier",
                "label": "From Location",
                "reqd": 1,
                "default": location
            },
            {
                "fieldname": 'dc_pop_up_html',
                "fieldtype": 'HTML',
            },
        ],
        size: "extra-large",
        primary_action_label: __("Create DC"),
        primary_action: function(values){
            let dc_items = i.getData();  
            d.hide();
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_delivery_challan",
                args: {
                    data: dc_items,
                    item_name: cur_frm.doc.item,
                    work_order: cur_frm.doc.work_order,
                    lot: cur_frm.doc.lot,
                    from_location: values.from_location,
                    vehicle_no: "NA"
                },
                freeze: true,
                freeze_message: "Creating Delivery Challan...",
                callback: function(r) {
                    frappe.msgprint("Delivery Challan Created");
                }
            });
        }
    });
    d.fields_dict['dc_pop_up_html'].$wrapper.html("");
    const el = d.fields_dict["dc_pop_up_html"].$wrapper.get(0);
    const props = { data: items.value,};
    const vueApp = createApp(FinishingDC, props);
    i = vueApp.mount(el);
    d.show();
}

function return_item() {
    let d = new frappe.ui.Dialog({
        title: __("Return Items"),
        fields: [
            {
                "fieldname": "received_type",
                "fieldtype": "Link",
                "options": "GRN Item Type",
                "label": "Received Type",
                "reqd": 1,
            },
            {
                "fieldname": 'return_pop_up_html',
                "fieldtype": 'HTML',
            },
        ],
        size: "extra-large",
        primary_action_label: __("Return"),
        primary_action: function(){
            let returned_items = i.getData();  
            d.hide();
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.return_items",
                args: {
                    "data": returned_items,
                    "work_order": cur_frm.doc.work_order,
                    "lot": cur_frm.doc.lot,
                    "item_name": cur_frm.doc.item,
                    "popup_values": {
                        "from_location": location,
                        "delivery_location": location,
                        "vehicle_no": "NA",
                        "received_type": d.get_value("received_type"),
                    }
                },
                freeze: true,
                freeze_message: "Returning Items...",
                callback: function(r) {
                    frappe.msgprint("Items Returned Successfully");
                }
            })
        }
    });
    d.fields_dict['return_pop_up_html'].$wrapper.html("");
    const el = d.fields_dict["return_pop_up_html"].$wrapper.get(0);
    const props = { data: items.value,};
    const vueApp = createApp(ReturnPopUp, props);
    i = vueApp.mount(el);
    d.show();
}


defineExpose({
    load_data
})

</script>

<style scoped>
.bordered-table {
    width: 100%;
    border: 1px solid #ccc;
    border-collapse: collapse;
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