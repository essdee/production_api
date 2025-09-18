<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Inward Quantity Report</h3>
        <div style="display:flex;">
            <div class="lot-input col-md-3"></div>
            <div class="process-input col-md-3"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_inward_qty_report()">Show Report</button>
            </div>
            <div style="padding-top: 27px;padding-left:10px;">
                <button class="btn btn-success" @click="take_screenshot()">Take Screenshot</button>
            </div>
        </div>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:20px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th style="width:150px;">Types</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border" v-for="(colour, idx) in Object.keys(items.data)" :key="colour">
                <tr v-for="(type, typeIdx) in items.types" :key="type + '-' + colour">
                    <td v-if="typeIdx === 0" :rowspan="items.types.length + 1">{{ idx + 1 }}</td>
                    <td v-if="typeIdx === 0" :rowspan="items.types.length + 1">{{ colour.split("@")[0] }}</td>
                    <td v-if="typeIdx === 0 && items.is_set_item" :rowspan="items.types.length + 1">{{ items.data[colour]['part'] }}</td>
                    <td>{{ type }}</td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items.data[colour]["values"][size]?.[type] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items.data[colour]['type_wise_total']?.[type] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td><strong>Total</strong></td>
                    <td v-for="size in items.primary_values" :key="size">
                        <strong>{{ items.data[colour]['size_wise_total']?.[size] ?? 0 }}</strong>
                    </td>
                    <td><strong>{{ items.data[colour]['colour_total']['total'] }}</strong></td>
                </tr>
            </tbody>
        </table>
    </div>  
</template>

<script setup>

import {ref, onMounted} from 'vue';

let lot = null
let process = null
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
            reqd: true,
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

function get_inward_qty_report(){
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
        method: "production_api.utils.get_inward_qty",
        args: {
            "lot": lot.get_value(),
            "process": process.get_value(),
        },
        freeze: true,
        freeze_message: "Fetching Inward Quantity",
        callback: function(r){
            items.value = r.message
        }
    })
}

async function take_screenshot(){
    frappe.require("https://cdn.jsdelivr.net/npm/html2canvas-pro@1.5.8/dist/html2canvas-pro.min.js", async () => {
        let sourceDiv = document.getElementById("page-inward-quantity-repo");
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

