<template>
    <div>
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
                    <td :rowspan="3">
                        {{ idx + 1 }}
                        <input type="checkbox" v-model="items['data']['data'][colour]['check_value']" />
                    </td>
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
                        <div v-if="items['data']['data'][colour]['check_value'] == 1">
                            <input type="number" class="form-control" v-model="items['data']['data'][colour]['values'][size]['balance_dc']" />
                        </div>
                        <div v-else>
                            {{
                                items['data']['data'][colour]["values"][size]['balance'] ?? 0
                            }}
                        </div>
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

let items = ref(null)

function load_data(data){
    items.value = data
}

function create_dc(){
    let selected_data = {
        "work_order": cur_frm.doc.work_order,
        "lot": cur_frm.doc.lot,
        "items": {}
    }

    for(let colour of Object.keys(items.value['data']['data'])){
        if(items.value['data']['data'][colour]['check_value'] == 1){
            selected_data['items'][colour] = items.value['data']['data'][colour]['values']
        }
    }

    if(Object.keys(selected_data['items']).length == 0){
        frappe.msgprint("Please select at least one colour to create DC.")
        return
    }
    let d = new frappe.ui.Dialog({
        title: 'Enter the Details to Create Delivery Challan',
        fields: [
            {
                "fieldname": "from_location",
                "fieldtype": "Link",
                "options": "Supplier",
                "label": "From Location",
                "reqd": 1,
            },
            {
                "fieldname": "vehicle_no",
                "fieldtype": "Data",
                "label": "Vehicle No",
                "reqd": 1,
            }
        ],
        primary_action_label: 'Create',
        primary_action(values) {
            d.hide();
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_delivery_challan",
                args: {
                    data: items.value,
                    item_name: cur_frm.doc.item,
                    work_order: cur_frm.doc.work_order,
                    lot: cur_frm.doc.lot,
                    from_location: values.from_location,
                    vehicle_no: values.vehicle_no
                },
                freeze: true,
                freeze_message: "Creating Delivery Challan...",
                callback: function(r) {
                    frappe.msgprint("Delivery Challan Created");
                }
            });
        }
    });
    d.show()
}

function return_item() {
    let d = new frappe.ui.Dialog({
        title: __("Return Items"),
        fields: [
            {
                "fieldname": "from_location",
                "fieldtype": "Link",
                "options": "Supplier",
                "label": "From Location",
                "reqd": 1,
            },
            {
                "fieldname": "delivery_location",
                "fieldtype": "Link",
                "options": "Supplier",
                "label": "Delivery Location",
                "reqd": 1,
            },
            {
                "fieldname": "vehicle_no",
                "fieldtype": "Data",
                "label": "Vehicle No",
                "reqd": 1,
            },
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
            console.log(returned_items)
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.return_items",
                args: {
                    "data": returned_items,
                    "work_order": cur_frm.doc.work_order,
                    "lot": cur_frm.doc.lot,
                    "item_name": cur_frm.doc.item,
                    "popup_values": {
                        "from_location": d.get_value("from_location"),
                        "delivery_location": d.get_value("delivery_location"),
                        "vehicle_no": d.get_value("vehicle_no"),
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