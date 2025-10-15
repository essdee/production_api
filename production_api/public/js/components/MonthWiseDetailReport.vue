<template>
    <div ref="root" style="padding:20px;">
        <div style="display:flex;">
            <div class="lot-input col-md-2"></div>
            <div class="item-input col-md-2"></div>
            <div class="start-date-input col-md-2"></div>
            <div class="end-date-input col-md-2"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_month_wise_report()">Show Report</button>
            </div>
            <!-- <div style="padding-top: 27px;padding-left:10px;">
                <button class="btn btn-success" @click="take_screenshot()">Take Screenshot</button>
            </div> -->
        </div>
        <!-- <div v-if="items && Object.keys(items).length > 0">
            <table class="table table-md table-sm-bordered bordered-table">
                <tr>
                    <th>Style</th>
                    <th>Lot No</th>
                    <th>Order Qty</th>
                    <th>Cut Qty</th>
                    <th>Sewing Sent</th>
                    <th>Cut to Sew Diff</th>
                    <th>Finishing Inward</th>
                    <th>In Sew</th>
                    <th>Dispatch</th>
                    <th>In Packing</th>
                </tr>
                <tr v-for="row in items">
                    <td>{{ row['style'] }}</td>
                    <td>{{ row['lot'] }}</td>
                    <td>{{ row['order_qty'] }}</td>
                    <td>{{ row['cut_qty'] }}</td>
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
                </tr>
            </table>
        </div> -->
    </div>
</template>

<script setup>

import {ref, onMounted} from 'vue';

let lot = null
let item = null
let start_date = null
let end_date = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})

onMounted(()=> {
    let el = root.value
    $(el).find(".lot-input").html("");
    lot = frappe.ui.form.make_control({
        parent: $(el).find(".lot-input"),
        df: {
            fieldname: "lot",
            fieldtype: "Link",
            options: "Lot",
            label: "Lot",
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".item-input").html("");
    item = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: {
            fieldname: "item",
            fieldtype: "Link",
            options: "Item",
            label: "Item",
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".start-date-input").html("")
    start_date = frappe.ui.form.make_control({
        parent: $(el).find(".start-date-input"),
        df: {
            fieldname: "start_date",
            fieldtype: "Date",
            label: "Start Date",
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".end-date-input").html("")
    end_date = frappe.ui.form.make_control({
        parent: $(el).find(".end-date-input"),
        df: {
            fieldname: "end_date",
            fieldtype: "Date",
            label: "End Date",
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

function get_month_wise_report(){
    if(!lot.get_value() && !item.get_value()){
        frappe.msgprint("Please Set Item or Lot to Generate Report")
        return
    }
    else if((start_date.get_value() && !end_date.get_value()) || (!start_date.get_value() && end_date.get_value()) ){
        frappe.msgprint("Please Set Both Start and End Date")
        return
    }
    else{
        frappe.call({
            method: "production_api.utils.get_month_wise_report",
            args: {
                "lot": lot.get_value(),
                "item": item.get_value(),
                "start_date": start_date.get_value(),
                "end_date": end_date.get_value(),
            },
            freeze: true,
            freeze_message: "Fetching Data",
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