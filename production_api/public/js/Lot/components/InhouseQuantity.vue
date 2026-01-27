<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Inhouse Quantity Report</h3>
        <div style="display:flex;">
            <div class="lot-input col-md-3"></div>
            <div class="process-input col-md-3"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_inhouse_qty_report()">Show Report</button>
            </div>
            <div style="padding-top: 27px;padding-left:10px;">
                <button class="btn btn-success" @click="take_screenshot()">Take Screenshot</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0">
            <h3 style="padding-top:20px;">Item: {{ item_name }}</h3>
            <div style="display: flex; gap: 20px; margin-bottom: 15px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 30px; height: 20px; background-color: #ccffda; border: 1px solid #ccc;"></div>
                    <span style="font-weight: 500;">Pass</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 30px; height: 20px; background-color: #ffa1a7; border: 1px solid #ccc;"></div>
                    <span style="font-weight: 500;">Fail</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 30px; height: 20px; background-color: #ffe7a6; border: 1px solid #ccc;"></div>
                    <span style="font-weight: 500;">Hold</span>
                </div>
            </div>
            
            <table class="table table-sm table-sm-bordered bordered-table">
                <thead class="dark-border">
                    <tr>
                        <th style="width:20px;">S.No</th>
                        <th style="width:20px;">Colour</th>
                        <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                        <th style="width:20px;">Supplier</th>
                        <th style="width:150px;">Type</th>
                        <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    <template class="dark-border" v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                        <template v-for="supplier in Object.keys(items['data']['data'][colour])">
                            <tr>
                                <td :rowspan="3">{{ idx + 1 }}</td>
                                <td :rowspan="3">{{ colour }}</td>
                                <td :rowspan="3" v-if="items.is_set_item">{{ items['data']['data'][colour][supplier]['part'] }}</td>
                                <td :rowspan="3">{{ supplier }}</td>
                                <td>Delivered</td>
                                <td v-for="size in items.primary_values" :key="size">
                                    {{
                                        items['data']['data'][colour][supplier]["values"][size]['delivered'] ?? 0
                                    }}
                                </td>
                                <td><strong>{{ items['data']['data'][colour][supplier]['colour_total']['delivered'] ?? 0 }}</strong></td>
                            </tr>
                            <tr>
                                <td>Received</td>
                                <td v-for="size in items.primary_values" :key="size"
                                    :style="get_quality_style(items['data']['data'][colour][supplier]['quality']?.[size])"
                                    >
                                    {{
                                        items['data']['data'][colour][supplier]["values"][size]['received'] ?? 0
                                    }}
                                </td>
                                <td><strong>{{ items['data']['data'][colour][supplier]['colour_total']['received'] ?? 0 }}</strong></td>
                            </tr>
                            <tr>
                                <td>Difference</td>
                                <td v-for="size in items.primary_values" :key="size"
                                    :style="get_style(items.data.data[colour][supplier].values[size].received ?? 0,items.data.data[colour][supplier].values[size].delivered ?? 0)">
                                        {{
                                            get_difference(items.data.data[colour][supplier].values[size].received ?? 0,items.data.data[colour][supplier].values[size].delivered ?? 0)
                                        }}
                                </td>
                                <td :style="get_style(items['data']['data'][colour][supplier]['colour_total']['received'] ?? 0, items['data']['data'][colour][supplier]['colour_total']['delivered'] ?? 0)">
                                <strong>{{ 
                                    get_difference(items['data']['data'][colour][supplier]['colour_total']['received'] ?? 0, items['data']['data'][colour][supplier]['colour_total']['delivered'] ?? 0)
                                }}</strong></td>
                            </tr>
                        </template>    
                    </template>
                    <template v-for="(row,key) in items.data['total']" :key="row">
                        <tr style="background-color: bisque;">
                            <td :rowspan="3"></td>
                            <td :rowspan="3">Total</td>
                            <td :rowspan="3" v-if="items.is_set_item">{{ key }}</td>
                            <td :rowspan="3"></td>
                            <td>Delivered</td>
                            <td v-for="size in items.primary_values" :key="size">
                                {{
                                    row[size]['delivered'] ?? 0
                                }}
                            </td>
                            <td>{{ items.data['over_all'][key]['delivered']  ?? 0 }}</td>
                        </tr>
                        <tr style="background-color: bisque;">
                            <td>Received</td>
                            <td v-for="size in items.primary_values" :key="size">
                                {{
                                    row[size]['received'] ?? 0
                                }}
                            </td>
                            <td>{{ items.data['over_all'][key]['received']  ?? 0}}</td>
                        </tr>
                        <tr style="background-color: bisque;">
                            <td>Difference</td>
                            <td v-for="size in items.primary_values" :key="size"
                            :style="get_style(row[size]['received'] ?? 0 , row[size]['delivered'] ?? 0)">
                                {{
                                    get_difference(row[size]['received'] ?? 0 , row[size]['delivered'] ?? 0)
                                }}
                            </td>
                            <td :style="get_style(items.data['over_all'][key]['received'] ?? 0 , items.data['over_all'][key]['delivered'] ?? 0)">
                                {{ get_difference(items.data['over_all'][key]['received'] ?? 0 , items.data['over_all'][key]['delivered'] ?? 0) }}
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>
        </div>    
    </div>  
</template>

<script setup>

import {ref, onMounted} from 'vue';

let lot = null
let process = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})
let item_name = ref(null)

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
            reqd: true,
            async onchange(){
                let x = await frappe.db.get_value("Lot", lot.get_value(), "item")
                item_name.value = x.message.item
            }
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".process-input").html("");
    process = frappe.ui.form.make_control({
        parent: $(el).find(".process-input"),
        df: {
            fieldname: "process",
            fieldtype: "Link",
            options: "Process",
            label: "Process",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

function get_inhouse_qty_report(){
    if(!lot.get_value()){
        frappe.msgprint("Select a Lot")
        return
    }
    if(!process.get_value()){
        frappe.msgprint("Select a Process")
        return
    }
    items.value = {}
    frappe.call({
        method: "production_api.utils.get_inhouse_qty",
        args: {
            "lot": lot.get_value(),
            "process": process.get_value(),
        },
        freeze: true,
        freeze_message: "Fetching Data",
        callback: function(r){
            console.log(r.message)
            items.value = r.message
        }
    })
}

function get_difference(qty1, qty2){
    return qty1 - qty2
}

async function take_screenshot(){
    frappe.require("https://cdn.jsdelivr.net/npm/html2canvas-pro@1.5.8/dist/html2canvas-pro.min.js", async () => {
        let sourceDiv = document.getElementById("page-inhouse-quantity-rep");
        html2canvas(sourceDiv, { 
            scale: 1, 
            useCORS: true, 
            backgroundColor: null, 
            logging: false, // turn off debug logs
            removeContainer: true // cleans up temp nodes faster
        }).then((canvas) => {
            let link = document.createElement("a");
            link.href = canvas.toDataURL("image/png");
            link.download = "screenshot.png";
            link.click();
        });
    });
}

function get_style(val1, val2){
    if(val1 - val2 < 0){
        return {"background":"#f57f87"};
    }
    else if(val1 - val2 > 0){
        return {"background":"#98ebae"}
    }
    return {"background":"#ebc96e"};
}

function get_quality_style(val){
    if(!val){
        return {"background":"white"}
    }
    else if(val == 'Pass'){
        return {"background":"#ccffda"};
    }
    else if(val == 'Fail'){
        return {"background":"#ffa1a7"};
    }
    return {"background":"#ffe7a6"};
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

.dark-border{
    border: 2px solid black;
}
</style>

