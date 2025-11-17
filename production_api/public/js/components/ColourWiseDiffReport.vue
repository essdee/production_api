<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Colour Wise Diff Report</h3>
        <div style="display:flex;">
            <div class="lot-input col-md-3"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_size_wise_stock()">Show Report</button>
            </div>
        </div>
        <multi-process-report ref="multiReport"/>
        <div v-if="items && Object.keys(items).length > 0">
            <h3>{{ items.lot }} - {{ items.style }}</h3>
            <table class="table table-md table-sm-bordered bordered-table">
                <tr>
                    <th style="width:50px;">S.No</th>
                    <th style="width:250px;">Colour</th>
                    <th style="width:250px;">Supplier</th>
                    <th style="width:150px;">Process</th>
                    <th v-for="size in items.sizes">{{ size }}</th>
                    <th style="width:100px;">Total</th>
                </tr>
                <template v-for="(colour, idx) in Object.keys(items.values)">
                    <tr>
                        <td :rowspan="8+Object.keys(items['rows']['against_cut_rows']).length+Object.keys(items['rows']['against_sew_rows']).length">{{ idx + 1 }}</td>
                        <td :rowspan="8+Object.keys(items['rows']['against_cut_rows']).length+Object.keys(items['rows']['against_sew_rows']).length">{{ colour.split("@")[0] }}</td>
                    </tr>
                    <tr v-for="(col, val) in items['rows']['cut_rows']">
                        <td>
                            <div v-if="items['values'][colour]['supplier_details']?.[col]">
                                {{ items['values'][colour]['supplier_details'][col].join(",") }}
                            </div>
                        </td>
                        <td>{{ val }}</td>
                        <td v-for="size in items.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(items['values'][colour]['cut_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ items['values'][colour]['cut_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(items['values'][colour]['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ items['values'][colour]['total_details'][col+'_total'] }}
                        </td>
                    </tr>
                    <tr v-for="(col, val) in items['rows']['against_cut_rows']">
                        <td>
                            <div v-if="items['values'][colour]['supplier_details']?.[col]">
                                {{ items['values'][colour]['supplier_details'][col].join(",") }}
                            </div>
                        </td>
                        <td>{{ val }}</td>
                        <td v-for="size in items.sizes">
                            <div v-if="items['values'][colour]['against_cut_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(items['values'][colour]['against_cut_details'][col][size]) 
                                : { background: 'white' }"
                            >
                                {{ items['values'][colour]['against_cut_details'][col][size] }}
                            </div>
                        </td>
                        <td>
                            <div v-if="items['values'][colour]['against_cut_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(items['values'][colour]['total_details'][col+'_total']) 
                                : { background: 'white' }"
                            >
                                {{ items['values'][colour]['total_details'][col+'_total'] }}
                            </div>
                        </td>    
                    </tr>
                    <tr v-for="(col, val) in items['rows']['sew_rows']">
                        <td>
                            <div v-if="items['values'][colour]['supplier_details']?.[col]">
                                {{ items['values'][colour]['supplier_details'][col].join(",") }}
                            </div>
                        </td>
                        <td>{{ val }}</td>
                        <td v-for="size in items.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(items['values'][colour]['sewing_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ items['values'][colour]['sewing_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(items['values'][colour]['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ items['values'][colour]['total_details'][col+'_total'] }}
                        </td>
                    </tr>
                    <tr v-for="(col, val) in items['rows']['against_sew_rows']">
                        <td>
                            <div v-if="items['values'][colour]['supplier_details']?.[col]">
                                {{ items['values'][colour]['supplier_details'][col].join(",") }}
                            </div>
                        </td>
                        <td>{{ val }}</td>
                        <td v-for="size in items.sizes">
                            <div v-if="items['values'][colour]['against_sew_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(items['values'][colour]['against_sew_details'][col+'_total']) 
                                : { background: 'white' }"
                            >
                                {{ items['values'][colour]['against_sew_details'][col][size] }}
                            </div>
                        </td>
                        <td>
                            <div v-if="items['values'][colour]['against_sew_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(items['values'][colour]['total_details'][col+'_total']) 
                                : { background: 'white' }"
                            >
                                {{ items['values'][colour]['total_details'][col+'_total'] }}
                            </div>
                        </td>
                    </tr>
                </template>
            </table>    
        </div>
        <div v-else>
            <div class="flex justify-center align-center text-muted" style="height: 50vh;">
                <div>
                    <div class="msg-box no-border">
                        <div>
                            <img src="/assets/frappe/images/ui-states/list-empty-state.svg" alt="Generic Empty State" class="null-state">
                            <p>Nothing to show</p>
                        </div>
                    </div>
                </div>
            </div>    
        </div>
    </div>
</template>

<script setup>

import {ref, onMounted} from 'vue';
import MultiProcessReport from './MultiProcessReport.vue'

let lot = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})
let multiReport = ref(null)
let process_list = ref([])

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
    process_list.value = multiReport.value.process_list
    if(!lot_val){
        frappe.msgprint("Please Set Lot")
    }
    else{
        frappe.call({
            method: "production_api.utils.get_colour_wise_diff_report",
            args: {
                "lot": lot_val,
                "process_list": process_list.value
            },
            freeze: true,
            freeze_message: "Fetching Report",
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
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}
.table td{
    padding: 0px !important;
    line-height: 2 !important;
}
</style>