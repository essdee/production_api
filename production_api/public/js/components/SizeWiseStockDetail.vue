<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Size Wise Stock Report</h3>
        <div style="display:flex;">
            <div class="lot-input col-md-3"></div>
            <div class="item-input col-md-3"></div>
            <div class="lot-status-input col-md-2"></div>
            <div class="product-category-input col-md-2"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_size_wise_stock()">Show Report</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0">
            <div v-for="data in items">
                <h3>{{ data.lot }} - {{ data.style }}</h3>
                <table class="table table-md table-sm-bordered bordered-table">
                    <tr>
                        <th>Size</th>
                        <th v-for="(qty, size) in data.order_qty">{{ size }}</th>
                        <th>Total</th>
                    </tr>
                    <tr>
                        <td>Order Qty</td>
                        <td v-for="qty in data.order_qty">{{ qty }}</td>
                        <td>{{ data.total_order }}</td>
                    </tr>
                    <tr>
                        <td>Cut Qty</td>
                        <td v-for="qty in data.cut_qty">{{ qty }}</td>
                        <td>{{ data.total_cut }}</td>
                    </tr>
                    <tr>
                        <td>Order to Cut Diff</td>
                        <td v-for="(qty, size) in data.order_qty" :style="get_style(get_diff(data.cut_qty[size], data.order_qty[size]))">
                            {{ get_diff(data.cut_qty[size], data.order_qty[size]) }}
                        </td>
                        <td :style="get_style(get_diff(data.total_cut, data.total_order))">
                            {{ get_diff(data.total_cut, data.total_order) }}
                        </td>
                    </tr>
                    <tr>
                        <td>Sewing Sent</td>
                        <td v-for="qty in data.sewing_sent">{{ qty }}</td>
                        <td>{{ data.total_sew_sent }}</td>
                    </tr>
                    <tr>
                        <td>Cut to Sew Diff</td>
                        <td v-for="(qty, size) in data.order_qty" :style="get_style(get_diff(data.sewing_sent[size], data.cut_qty[size]))">
                            {{ get_diff(data.sewing_sent[size], data.cut_qty[size])  }}
                        </td>
                        <td :style="get_style(get_diff(data.total_sew_sent, data.total_cut))">
                            {{ get_diff(data.total_sew_sent, data.total_cut) }}
                        </td>
                    </tr>
                    <tr>
                        <td>Finishing Inward</td>
                        <td v-for="qty in data.finishing_inward">{{ qty }}</td>
                        <td>{{ data.total_finishing_inward }}</td>
                    </tr>
                    <tr>
                        <td>In Sew</td>
                        <td v-for="(qty, size) in data.order_qty" :style="get_style(get_diff(data.finishing_inward[size], data.sewing_sent[size]))">
                            {{ get_diff(data.finishing_inward[size], data.sewing_sent[size]) }}
                        </td>
                        <td :style="get_style(get_diff(data.total_finishing_inward, data.total_sew_sent))">
                            {{ get_diff(data.total_finishing_inward, data.total_sew_sent) }}
                        </td>
                    </tr>
                    <tr>
                        <td>Dispatch</td>
                        <td v-for="qty in data.dispatch">{{ qty }}</td>
                        <td>{{ data.total_dispatch }}</td>
                    </tr>
                    <tr>
                        <td>In Packing</td>
                        <td v-for="(qty, size) in data.order_qty" :style="get_style(get_diff(data.dispatch[size], data.finishing_inward[size]))">
                            {{ get_diff(data.dispatch[size], data.finishing_inward[size]) }}
                        </td>
                        <td :style="get_style(get_diff(data.total_dispatch, data.total_finishing_inward))">
                            {{ get_diff(data.total_dispatch, data.total_finishing_inward) }}
                        </td>
                    </tr>
                    <tr>
                        <td>Work In Progress</td>
                        <td v-for="(qty, size) in data.order_qty">
                            <div v-if="data.total_cut > 0">
                                {{ get_diff(data.cut_qty[size], data.dispatch[size]) }}
                            </div>
                            <div v-else>
                                {{ get_diff(data.order_qty[size], data.dispatch[size]) }}
                            </div>
                        </td>
                        <td>
                            <div v-if="data.total_cut > 0">
                                {{ get_diff(data.total_cut, data.total_dispatch) }}
                            </div>
                            <div v-else>
                                {{ get_diff(data.total_order, data.total_dispatch) }}
                            </div>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup>

import {ref, onMounted} from 'vue';

let lot_list = null
let item_list = null
let lot_status = null
let product_category = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})

onMounted(()=> {
    let el = root.value
    frappe.model.with_doctype("Lot MultiSelect", () => {
        $(el).find(".lot-input").html("");
        lot_list = frappe.ui.form.make_control({
            parent: $(el).find(".lot-input"),
            df: {
                fieldtype: "Table MultiSelect",
                fieldname: "lot",
                label: "Lot",
                options: "Lot MultiSelect",
            },
            doc: sample_doc.value,
            render_input: true,
        })
    })
    
    $(el).find(".item-input").html("");
    frappe.model.with_doctype("Item MultiSelect", () => {
        item_list = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: {
            fieldtype: "Table MultiSelect",
            fieldname: "item",
            label: "Item",
            options: "Item MultiSelect",
        },
        doc: sample_doc.value,
        render_input: true,
    })
    })
    
    $(el).find(".lot-status-input").html("")
    lot_status = frappe.ui.form.make_control({
        parent: $(el).find(".lot-status-input"),
        df: {
            fieldname: "lot_status",
            fieldtype: "Select",
            label: "Status",
            options: ['Open', 'Closed'],
            default: "Open",
        },
        doc: sample_doc.value,
        render_input: true,
    })

    $(el).find(".product-category-input").html("")
    product_category = frappe.ui.form.make_control({
        parent: $(el).find(".product-category-input"),
        df: {
            fieldname: "product_category",
            fieldtype: "Link",
            label: "Product Category",
            options: "Product Category",
            default: 'Inner'
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

function get_diff(val1, val2){
    return val1 - val2
}

function get_style(val){
    if(val < 0){
        return {"background":"#f57f87"};
    }
    else if(val > 0){
        return {"background":"#98ebae"}
    }
    return {"background": "none"};
}

function get_size_wise_stock(){
    let open_status_val = lot_status.get_value()
    let lot_list_val = lot_list.get_value()
    let item_list_val = item_list.get_value()
    let category = product_category.get_value()
    if(!category){
        frappe.msgprint("Please Set Category")
    }
    else if(lot_list_val.length == 0 && item_list_val.length == 0 && !open_status_val){
        frappe.msgprint("Select at least one Item or Lot, or select Open Status.")
    }
    else{
        frappe.call({
            method: "production_api.utils.get_size_wise_stock_report",
            args: {
                "open_status": open_status_val,
                "lot_list": lot_list_val,
                "item_list": item_list_val,
                "category": category, 
            },
            callback: function(r){
                items.value = r.message
            }
        })
    }
}
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
</style>