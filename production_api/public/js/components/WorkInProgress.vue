<template>
    <div ref="root" style="padding:20px;">
        <div style="display:flex;">
            <div class="category-input col-md-2"></div>
            <div class="lot-status-input col-md-2"></div>
            <div class="lot-input col-md-3"></div>
            <div class="item-input col-md-3"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_work_in_progress_report()">Show Report</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0">
            <table class="table table-md table-sm-bordered bordered-table">
                <tr>
                    <th>Style</th>
                    <th>Lot No</th>
                    <th>Order Qty</th>
                    <th>Cut Qty</th>
                    <th>Order to Cut Diff</th>
                    <th>Sewing Sent</th>
                    <th>Cut to Sew Diff</th>
                    <th>Finishing Inward</th>
                    <th>In Sew</th>
                    <th>Dispatch</th>
                    <th>In Packing</th>
                    <th>Cut Last Date</th>
                    <th>Sewing Sent Date</th>
                    <th>Finishing Inward Date</th>
                </tr>
                <tr v-for="row in items">
                    <td>{{ row['style'] }}</td>
                    <td>{{ row['lot'] }}</td>
                    <td>{{ row['order_qty'] }}</td>
                    <td>{{ row['cut_qty'] }}</td>
                    <td :style="get_style(get_diff(row['cut_qty'], row['order_qty']))">
                        {{ get_diff(row['cut_qty'], row['order_qty']) }}
                    </td>
                    <td>{{ row['sewing_sent'] }}</td>
                    <td :style="get_style(get_diff(row['sewing_sent'], row['cut_qty']))">
                        {{ get_diff(row['sewing_sent'], row['cut_qty']) }}
                    </td>
                    <td>{{ row['finishing_inward'] }}</td>
                    <td :style="get_style(get_diff(row['finishing_inward'], row['sewing_sent']))">
                        {{ get_diff(row['finishing_inward'], row['sewing_sent']) }}
                    </td>
                    <td>{{ row['dispatch'] }}</td>
                    <td :style="get_style(get_diff(row['dispatch'], row['finishing_inward']))">
                        {{ get_diff(row['dispatch'], row['finishing_inward']) }}
                    </td>
                    <td>{{ get_date(row['last_cut_date']) }}</td>
                    <td>{{ get_date(row['sew_sent_date']) }}</td>
                    <td>{{ get_date(row['finishing_inward_date']) }}</td>
                </tr>
            </table>
        </div>
    </div>
</template>

<script setup>

import {ref, onMounted} from 'vue';

let category = null
let lot_status = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})
let lot_list = null
let item_list = null

onMounted(()=> {
    let el = root.value
    $(el).find(".category-input").html("");
    category = frappe.ui.form.make_control({
        parent: $(el).find(".category-input"),
        df: {
            fieldname: "category",
            fieldtype: "Link",
            options: "Product Category",
            label: "Product Category",
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".lot-status-input").html("");
    lot_status = frappe.ui.form.make_control({
        parent: $(el).find(".lot-status-input"),
        df: {
            fieldname: "lot_status",
            fieldtype: "Select",
            options: "\nOpen\nClosed",
            label: "Lot Status",
            default: "Open",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    })
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
    
})

function get_work_in_progress_report(){
    let lot_list_val = lot_list.get_value()
    let item_list_val = item_list.get_value()
    if(!category.get_value() && lot_list_val.length == 0 && item_list_val.length == 0){
        frappe.msgprint("Please Set Atleast one filter other than Lot Status")
    }
    else{
        frappe.call({
            method: "production_api.utils.get_work_in_progress_report",
            args: {
                "category": category.get_value(),
                "status": lot_status.get_value(),
                "lot_list_val": lot_list_val,
                "item_list": item_list_val,
            },
            freeze: true,
            freeze_message: "Fetching Data",
            callback: function(r){
                items.value = r.message
            }
        })
    }
}

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

function get_date(date){
    if(date){
        let x = new Date(date)
        return x.getDate() + "-" + (x.getMonth() + 1) + "-" + x.getFullYear()
    }
    return ""
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