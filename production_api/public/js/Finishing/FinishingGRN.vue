<template>
    <div ref="root">
        <div style="display:flex;width:100%;gap:20px;">
            <div v-if="grn_list && Object.keys(grn_list).length > 0" style="width:50%;">
                <h3>GRN List</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Goods Received Note</th>
                            <th>Date Time</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="(date, grn) in grn_list">
                            <td style="cursor: pointer;" @click="redirect_to('Goods Received Note', grn)">{{ grn }}</td>
                            <td>{{ date }}</td>
                            <td>
                                <button class="btn btn-primary" @click="cancel_doc('Goods Received Note', grn)">Cancel</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div v-if="se_list && Object.keys(se_list).length > 0" style="width:50%;">
                <h3>Stock Entry List</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Stock Entry</th>
                            <th>Date Time</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="(date, se) in se_list">
                            <td style="cursor: pointer;" @click="redirect_to('Stock Entry', se)">{{ se }}</td>
                            <td>{{ date }}</td>
                            <td>
                                <button class="btn btn-primary" @click="cancel_doc('Stock Entry', se)">Cancel</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>    
        <div style="display:flex;">
            <div style="padding-left: 20px;">
                <button class="btn btn-success" @click="make_grn()">Make GRN</button>
            </div>
            <div style="padding-left: 20px;">
                <button class="btn btn-success" @click="make_dispatch()">Dispatch Box</button>
            </div>
        </div>
        <table class="table table-sm table-sm-bordered bordered-table" >
            <thead class="dark-border">
                <tr>
                    <th>Size</th>
                    <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr>
                    <td>Packed</td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        {{ packed_qty[value]['packed']}}
                    </td>
                    <td>{{ total_packed }}</td>
                </tr>
                <tr>
                    <td>Dispatched</td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        {{ packed_qty[value]['dispatched']}}
                    </td>
                    <td>{{ total_dispatched }}</td>
                </tr>
                <tr>
                    <td>Balance</td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        {{ packed_qty[value]['packed'] - packed_qty[value]['dispatched']}}
                    </td>
                    <td>{{ total_packed - total_dispatched }}</td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import {ref, onMounted, createApp} from 'vue';
import FPDispatch from './FPDispatch.vue';
import FPPopUpGRN from "./FPPopUpGRN.vue"

const root = ref(null);
const primary_values = ref([])
let box_qty = ref({})
let packed_qty = ref({})
let location = cur_frm.doc.delivery_location
let grn_list = JSON.parse(cur_frm.doc.grn_list || "{}")
let se_list = JSON.parse(cur_frm.doc.stock_entry_list || "{}")
let total_packed = ref(0)
let total_dispatched = ref(0)

onMounted(()=> {
    frappe.call({
        method: "production_api.production_api.doctype.goods_received_note.goods_received_note.get_primary_values",
        args: {
            lot: cur_frm.doc.lot
        },
        callback: function(response) {
            primary_values.value = response.message || [];
            primary_values.value.forEach(value => {
                if (!(value in box_qty.value)) {
                    box_qty.value[value] = 0;
                }
            });
        }
    })
})

function redirect_to(doctype, docname){
    frappe.open_in_new_tab = true;
    frappe.set_route("Form", doctype, docname);
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

function get_items(){
    return box_qty.value;
}

function load_data(data){
    let items = JSON.parse(JSON.stringify(data));
    Object.keys(items['sizes']).forEach(key => {
        packed_qty.value[key] = items['sizes'][key];
    });
    total_packed.value = items['total_packed']
    total_dispatched.value = items['total_dispatched']
}

function make_grn(){
    let d = new frappe.ui.Dialog({
        title: 'Create Goods Received Note',
        fields: [
            {
                "fieldname": "delivery_location",
                "fieldtype": "Link",
                "label": "Delivery Location",
                "options": "Supplier",
                "reqd": 1,  
                "default": location
            },
            {
                "fieldname": "popup_grn_html",
                "fieldtype": "HTML"

            }
        ],
        size: "extra-large",
        primary_action_label: 'Create GRN',
        primary_action(values) {
            d.hide();
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_grn",
                args: {
                    work_order: cur_frm.doc.work_order,
                    lot: cur_frm.doc.lot,
                    item_name: cur_frm.doc.item,
                    data: i.box_qty,
                    delivery_location: values.delivery_location
                },
                freeze: true,
                freeze_message: "Creating Goods Received Note...",
                callback: function() {
                    frappe.msgprint("GRN Created Successfully");
                }
            })
        }
    });
    d.fields_dict['popup_grn_html'].$wrapper.html("")
    const el = d.fields_dict["popup_grn_html"].$wrapper.get(0);
    const props = { 
        primary_values: primary_values.value,
        box_qty: box_qty.value,
    };
    const vueApp = createApp(FPPopUpGRN, props);
    i = vueApp.mount(el);
    d.show()
}

function make_dispatch(){
    let d = new frappe.ui.Dialog({
        title: "Dispatch Box",
        fields: [
            {
                "fieldname": "from_location",
                "fieldtype": "Link",
                "label": "From Location",
                "options": "Supplier",
                "reqd": 1,  
                "default": location,
            },
            {
                "fieldname": "to_location",
                "fieldtype": "Link",
                "label": "To Location",
                "options": "Supplier",
                "reqd": 1,
            },
            {
                "fieldname": "goods_value",
                "fieldtype": "Currency",
                "label": "Goods Value",
                "reqd": 1,
            },
            {
                "fieldname": "vehicle_no",
                "fieldtype": "Data",
                "label": "Vehicle No",
                "reqd": 1
            },
            {
                "fieldname": "dispatch_qty_html",
                "fieldtype": "HTML"
            }
        ],
        size: "extra-large",
        primary_action_label: 'Dispatch',
        primary_action(values) {
            d.hide();
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_stock_entry",
                args: {
                    doc_name: cur_frm.doc.name,
                    lot: cur_frm.doc.lot,
                    item_name: cur_frm.doc.item,
                    data: i.packed_qty,
                    from_location: values.from_location,
                    to_location: values.to_location,
                    goods_value: values.goods_value,
                    vehicle_no: values.vehicle_no,
                }, 
                freeze: true,
                freeze_message: "Dispatching Items...",
                callback: function(response) {
                    frappe.msgprint("Stock Dispatched Successfully...")
                } 
            })
        }
    })
    d.fields_dict['dispatch_qty_html'].$wrapper.html("")
    const el = d.fields_dict["dispatch_qty_html"].$wrapper.get(0);
    const props = { 
        packed_qty: packed_qty.value,
        primary_values: primary_values.value,
        packed: total_packed.value,
        dispatched: total_dispatched.value,
    };
    const vueApp = createApp(FPDispatch, props);
    i = vueApp.mount(el);
    d.show()
}

defineExpose({
    get_items,
    load_data,
});

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