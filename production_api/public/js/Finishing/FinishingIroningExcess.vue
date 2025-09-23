<template>
    <div>
        <div v-if="ie_list && Object.keys(ie_list).length > 0" style="width: 40%;">
            <h3>Ironing Excess List</h3>
            <table class="table table-sm table-sm-bordered bordered-table small-width">
                <thead class="dark-border">
                    <tr>
                        <th>Stock Entry</th>
                        <th>Date Time</th>
                        <th>Cancel</th>
                    </tr>
                </thead>
                <tbody class="dark-border">
                    <tr v-for="(date, ie) in ie_list">
                        <td style="cursor: pointer;" @click="redirect_to('Stock Entry', ie)">{{ ie }}</td>
                        <td>{{ date }}</td>
                        <td>
                            <button class="btn btn-primary" @click="cancel_doc('Stock Entry', ie)">Cancel</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <button class="btn btn-success" @click="add_ironing()">Add Ironing Excess Qty</button>
        <h3 style="text-align: center;">Ironing Excess Quantity</h3>
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
                                items['data']['data'][colour]["values"][size]['ironing'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['data'][colour]['colour_total']['ironing'] ?? 0 }}</strong></td>
                    </tr>
                </template>
                <tr>
                    <th></th>
                    <th>Total</th>
                    <th v-if="items.is_set_item"></th>
                    <th v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['total'][size]['ironing'] ?? 0
                        }}
                    </th>
                    <th>{{ items['data']['total_qty']['ironing'] }}</th>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>

import { ref, createApp } from 'vue';
import FinishingIroningDC from "./FinishingIroningDC.vue"

let items = ref(null)

function load_data(data){
    items.value = data
}

let ie_list = JSON.parse(cur_frm.doc.ironing_excess_list || "{}");

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

function add_ironing(){
    let d = new frappe.ui.Dialog({
        title: "Add Ironing Excess Pieces",
        fields: [
            {
                "fieldname": "ironing_excess_html",
                "fieldtype": "HTML"
            },
        ],
        size: "extra-large",
        primary_action_label: "Create",
        primary_action(){
            let ironing_items = i.getData()
            d.hide();
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_material_receipt",
                args: {
                    data: ironing_items,
                    item_name: cur_frm.doc.item,
                    lot: cur_frm.doc.lot,
                    ipd: cur_frm.doc.production_detail,
                    doc_name: cur_frm.doc.name,
                    location: cur_frm.doc.delivery_location
                },
                freeze: true,
                freeze_message: "Adding Ironing Excess Pieces...",
                callback: function(r) {
                    frappe.msgprint("Ironing Excess Added");
                }
            });
        }
    })
    d.fields_dict['ironing_excess_html'].$wrapper.html("")
    let el = d.fields_dict['ironing_excess_html'].$wrapper.get(0)
    let props = {"data": items.value}
    let vue = createApp(FinishingIroningDC, props)
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