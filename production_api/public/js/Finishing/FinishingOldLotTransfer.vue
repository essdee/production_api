<template>
    <div>
        <div v-if="lt_list && Object.keys(lt_list).length > 0" style="width:40%;">
            <h3>Lot Transfer List</h3>
            <table class="table table-sm table-sm-bordered bordered-table">
                <thead class="dark-border">
                    <tr>
                        <th>Lot Transfer</th>
                        <th>Date Time</th>
                        <th>Cancel</th>
                    </tr>
                </thead>
                <tbody class="dark-border">
                    <tr v-for="(date, lt) in lt_list">
                        <td style="cursor: pointer;" @click="redirect_to('Lot Transfer', lt)">{{ lt }}</td>
                        <td>{{ date }}</td>
                        <td>
                            <button class="btn btn-primary" @click="cancel_doc('Lot Transfer', lt)">Cancel</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div style="display:flex;">
            <div>
                <button class="btn btn-success" @click="fetch_items()">Fetch Items</button>
            </div>
            <div style="padding-left:20px;">
                <button class="btn btn-success" @click="lot_transfer()">Lot Transfer</button>
            </div>
        </div>
        <div style="margin-top:20px;"></div>
        <div v-for="row in items">
            <h3>{{ row.lot }} - {{ row.warehouse_name }}</h3>
            <table class="table table-sm table-sm-bordered bordered-table">
                <thead class="dark-border">
                    <tr>
                        <th style="width:20px;">S.No</th>
                        <th style="width:20px;">Colour</th>
                        <th style="width: 150px;">Set Colour</th>
                        <th style="width:20px;" v-if="items.is_set_item">{{ row['set_attr'] }}</th>
                        <th style="width:150px;">Type</th>
                        <th v-for="size in row.primary_values" :key="size">{{ size }}</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody class="dark-border" v-for="(colour, idx) in Object.keys(row['old_lot_inward']['data'])" :key="colour">
                    <tr>
                        <td :rowspan="2">{{ idx + 1 }}</td>
                        <td :rowspan="2">{{ colour }}</td>
                        <td :rowspan="2">
                            <select v-model="row['old_lot_inward']['data'][colour]['set_combination']" class="form-control">
                                <option v-for="opt in colours" :key="opt" :value="opt">
                                    {{ opt }}
                                </option>
                            </select>
                        </td>
                        <td :rowspan="2" v-if="row.is_set_item">{{ row['old_lot_inward']['data'][colour]['part'] }}</td>
                        <td>Quantity</td>
                        <td v-for="size in row.primary_values" :key="size">
                            {{
                                row['old_lot_inward']['data'][colour]["values"][size]['balance'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ row['old_lot_inward']['data'][colour]['colour_total']['balance'] ?? 0 }}</strong></td>
                    </tr>
                    <tr>
                        <td>Transfer</td>
                        <td v-for="size in row.primary_values" :key="size">
                            <input type="number" class="form-control" v-model="row['old_lot_inward']['data'][colour]['values'][size]['transfer']"/>
                        </td>
                        <td><strong>{{ row['old_lot_inward']['data'][colour]['colour_total']['transfer'] ?? 0 }}</strong></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';

let items = ref([])
let colours = ref([])
let lt_list = JSON.parse(cur_frm.doc.lot_transfer_list || "{}");

function fetch_items(){
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan.finishing_plan.fetch_from_old_lot",
        args: {
            "lot": cur_frm.doc.lot,
            "item": cur_frm.doc.item,
            "location": cur_frm.doc.delivery_location,
        },
        freeze: true,
        freeze_message: "Fetching Old Lot Items",
        callback: function(r){
            items.value = r.message.data;
            colours.value = r.message.colours
        }
    })
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

function lot_transfer() {
    let check = check_set_colour()
    if (check) {
        let d = new frappe.ui.Dialog({
            title: "Are you sure want to transfer the items",
            primary_action_label: "Yes",
            secondary_action_label: "No",
            primary_action(){
                d.hide()
                frappe.call({
                    method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_lot_transfer",
                    args: {
                        "data": items.value,
                        "item_name": cur_frm.doc.item,
                        "ipd": cur_frm.doc.production_detail,
                        "lot": cur_frm.doc.lot,
                        "doc_name": cur_frm.doc.name
                    },
                    freeze: true,
                    freeze_message: "Transferring Items....",
                    callback: function(){
                        frappe.msgprint("Items Transferred")
                    }
                })
            },
            secondary_action(){
                d.hide()
            }   
        })
        d.show()
    }
}

function check_set_colour() {
    for (let i = 0; i < items.value.length; i++) {
        let row = items.value[i]
        for (let colour of Object.keys(row['old_lot_inward']['data'])) {
            let check = false

            for (let size of Object.keys(row['old_lot_inward']['data'][colour]['values'])) {
                if (row['old_lot_inward']['data'][colour]['values'][size]['transfer'] > 0) {
                    check = true
                    break
                }
            }
            if (check && !row['old_lot_inward']['data'][colour]['set_combination']) {
                frappe.msgprint("Please mention Set Colour")
                return false 
            }
        }
    }
    return true
}


</script>

<style scoped>
.small-width {
    width: 40%;
}

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