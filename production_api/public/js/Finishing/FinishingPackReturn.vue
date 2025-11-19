<template>
    <div>
        <div v-if="pr_list && Object.keys(pr_list).length > 0" style="width: 40%;">
            <h3>Pack Return List</h3>
            <table class="table table-sm table-sm-bordered bordered-table small-width">
                <thead class="dark-border">
                    <tr>
                        <th>Pack Return</th>
                        <th>Date Time</th>
                        <th>Cancel</th>
                    </tr>
                </thead>
                <tbody class="dark-border">
                    <tr v-for="(date, pr) in pr_list">
                        <td style="cursor: pointer;" @click="redirect_to('Goods Received Note', pr)">{{ pr }}</td>
                        <td>{{ date }}</td>
                        <td>
                            <button class="btn btn-primary" @click="cancel_doc('Goods Received Note', pr)">Cancel</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <button class="btn btn-success" @click="return_pack_items()">Return Pack</button>
        <h3 style="text-align: center;">Pack Returned Items</h3>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:40px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <template v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                    <tr>
                        <td>{{ idx + 1 }}</td>
                        <td>{{ colour.split("@")[0] }}</td>
                        <td v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['data'][colour]["values"][size]['pack_returned_qty'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['data'][colour]['colour_total'] ?? 0 }}</strong></td>
                    </tr>
                </template>
                <tr>
                    <th></th>
                    <th>Total</th>
                    <th v-if="items.is_set_item"></th>
                    <th v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['total'][size] ?? 0
                        }}
                    </th>
                    <th>{{ items['data']['total_qty'] }}</th>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>

import { ref, createApp } from 'vue';
import FinishingPackreturnPopUp from "./FinishingPackReturnPopUp.vue"

let items = ref(null)
let location = cur_frm.doc.delivery_location
function load_data(data){
    items.value = data
}

let pr_list = JSON.parse(cur_frm.doc.pack_return_list || "{}");

function cancel_doc(doctype, docname){
    console.log(doctype)
    console.log(docname)
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

function return_pack_items(){
    let d = new frappe.ui.Dialog({
        title: "Add Pack Return Pieces",
        fields: [
            {
                "fieldname": "pack_return_html",
                "fieldtype": "HTML"
            },
        ],
        size: "extra-large",
        primary_action_label: "Create",
        primary_action(){
            let pack_items = i.getData()
            d.hide();
            console.log(pack_items)
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.return_items",
                args: {
                    "data": pack_items,
                    "work_order": cur_frm.doc.work_order,
                    "lot": cur_frm.doc.lot,
                    "item_name": cur_frm.doc.item,
                    "popup_values": {
                        "from_location": location,
                        "delivery_location": location,
                        "vehicle_no": "NA",
                        "received_type": "Accepted",
                    },
                    "is_pack": true
                },
                freeze: true,
                freeze_message: "Returning Packed Pieces...",
                callback: function(r) {
                    frappe.msgprint("Packed Pieces Returned");
                }
            });
        }
    })
    d.fields_dict['pack_return_html'].$wrapper.html("")
    let el = d.fields_dict['pack_return_html'].$wrapper.get(0)
    let props = {"data": items.value}
    let vue = createApp(FinishingPackreturnPopUp, props)
    i = vue.mount(el)
    d.show()
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