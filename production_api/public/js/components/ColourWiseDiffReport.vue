<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Colour Wise Diff Report</h3>
        <div style="display:flex;">
            <div class="lot-input col-md-3"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_size_wise_stock()">Show Report</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0">
            <h3>{{ items.lot }} - {{ items.style }}</h3>
            <table class="table table-md table-sm-bordered bordered-table">
                <tr>
                    <th>S.No</th>
                    <th>Colour</th>
                    <th>Process</th>
                    <th v-for="size in items.sizes">{{ size }}</th>
                    <th>Total</th>
                </tr>
                <template v-for="(colour, idx) in Object.keys(items.values)">
                    <tr>
                        <td rowspan="8">{{ idx + 1 }}</td>
                        <td rowspan="8">
                            {{ colour.split("@")[0] }}
                        </td>
                    </tr>
                    <tr>
                        <td>Order Qty</td>
                        <td v-for="size in items.sizes">{{ items.values[colour]['order_qty'][size] }}</td>
                        <td>{{ items.values[colour]['total_order'] }}</td>
                    </tr>
                    <tr>
                        <td>Cutting Qty</td>
                        <td v-for="size in items.sizes">{{ items.values[colour]['cut_qty'][size] }}</td>
                        <td>{{ items.values[colour]['total_cut'] }}</td>
                    </tr>
                    <tr>
                        <td>Order to Cut Diff</td>
                        <td v-for="size in items.sizes" :style="get_style(get_diff(items.values[colour]['cut_qty'][size], items.values[colour]['order_qty'][size]))">
                            {{ get_diff(items.values[colour]['cut_qty'][size], items.values[colour]['order_qty'][size]) }}
                        </td>
                        <td :style="get_style(get_diff(items.values[colour]['total_cut'],items.values[colour]['total_order']))">
                            {{ get_diff(items.values[colour]['total_cut'],items.values[colour]['total_order']) }}
                        </td>
                    </tr>
                    <tr>
                        <td>Sewing Sent</td>
                        <td v-for="size in items.sizes">{{ items.values[colour]['sewing_sent'][size] }}</td>
                        <td>{{ items.values[colour]['total_sew_sent'] }}</td>
                    </tr>
                    <tr>
                        <td>Cut to Sew Diff</td>
                        <td v-for="size in items.sizes" :style="get_style(get_diff(items.values[colour]['sewing_sent'][size], items.values[colour]['cut_qty'][size]))">
                            {{ get_diff(items.values[colour]['sewing_sent'][size], items.values[colour]['cut_qty'][size]) }}
                        </td>
                        <td :style="get_style(get_diff(items.values[colour]['total_sew_sent'], items.values[colour]['total_cut']))">
                            {{ get_diff(items.values[colour]['total_sew_sent'], items.values[colour]['total_cut']) }}
                        </td>
                    </tr>
                    <tr>
                        <td>Finishing Inward</td>
                        <td v-for="size in items.sizes">{{ items.values[colour]['finishing_inward'][size] }}</td>
                        <td>{{ items.values[colour]['total_finishing_inward'] }}</td>
                    </tr>
                    <tr>
                        <td>In Sew</td>
                        <td v-for="size in items.sizes" :style="get_style(get_diff(items.values[colour]['finishing_inward'][size], items.values[colour]['sewing_sent'][size]))">
                            {{ get_diff(items.values[colour]['finishing_inward'][size], items.values[colour]['sewing_sent'][size]) }}
                        </td>
                        <td :style="get_style(get_diff(items.values[colour]['total_finishing_inward'], items.values[colour]['total_sew_sent']))">
                            {{ get_diff(items.values[colour]['total_finishing_inward'], items.values[colour]['total_sew_sent']) }}
                        </td>
                    </tr>
                </template>
            </table>
        </div>
    </div>
</template>

<script setup>

import {ref, onMounted} from 'vue';

let lot = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})

onMounted(()=> {
    let el = root.value
    $(el).find(".lot-input").html("");
    lot = frappe.ui.form.make_control({
        parent: $(el).find(".lot-input"),
        df: {
            fieldtype: "Link",
            fieldname: "lot",
            label: "Lot",
            options: "Lot",
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
    let lot_val = lot.get_value()
    if(!lot_val){
        frappe.msgprint("Please Set Lot")
    }
    else{
        frappe.call({
            method: "production_api.utils.get_colour_wise_diff_report",
            args: {
                "lot": lot_val,
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