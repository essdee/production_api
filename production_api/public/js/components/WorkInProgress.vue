<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Work In Progress Report</h3>
        <div style="display:flex;">
            <div class="category-input col-md-2"></div>
            <div class="lot-status-input col-md-2"></div>
            <div class="lot-input col-md-3"></div>
            <div class="item-input col-md-3"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_work_in_progress_report()">Show Report</button>
            </div>
            <div style="padding-top:27px;padding-left:10px;">
                <button class="btn btn-primary" @click="get_list_items()">Paste</button>
            </div>
        </div>
        <multi-process-report ref="multiReport"/>
        <div v-if="items && Object.keys(items).length > 0" class="table-container">
            <table class="table table-md table-sm-bordered bordered-table">
                <tr>
                    <th>Style</th>
                    <th>Lot No</th>
                    <th v-for="col in Object.keys(items['columns']['cut_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['against_cut_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['sew_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['against_sew_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['finishing_columns'])">{{ col }}</th>
                    <th>Cut Last Date</th>
                    <th>Sewing Sent Date</th>
                    <th>Finishing Inward Date</th>
                </tr>

                <tr v-for="row in items['lot_data']">
                    <td>{{ row['style'] }}</td>
                    <td>{{ row['lot'] }}</td>
                    <td v-for="col in items['columns']['cut_columns']"
                        :style="items['diff_columns'].includes(col) 
                            ? get_style(row['cut_details'][col]) 
                            : { background: 'white' }"
                        >
                        {{ row['cut_details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['against_cut_columns']"
                        :style="items['diff_columns'].includes(col) 
                            ? get_style(row['against_cut_details'][col]) 
                            : { background: 'white' }"
                        >
                        {{ row['against_cut_details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['sew_columns']"
                        :style="items['diff_columns'].includes(col) 
                            ? get_style(row['sewing_details'][col]) 
                            : { background: 'white' }"
                        >
                        {{ row['sewing_details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['against_sew_columns']"
                        :style="items['diff_columns'].includes(col) 
                            ? get_style(row['against_sew__details'][col]) 
                            : { background: 'white' }"
                        >
                        {{ row['against_sew__details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['finishing_columns']"
                        :style="items['diff_columns'].includes(col) 
                            ? get_style(row['finishing_details'][col]) 
                            : { background: 'white' }"
                        >
                        {{ row['finishing_details'][col] }}
                    </td>
                    <td>{{ get_date(row['last_cut_date']) }}</td>
                    <td>{{ get_date(row['sew_sent_date']) }}</td>
                    <td>{{ get_date(row['finishing_inward_date']) }}</td>
                </tr>
                <tr>
                    <th></th>
                    <th></th>
                    <th v-for="col in items['columns']['cut_columns']">
                        {{ items['total_data']['cut_details'][col] }}
                    </th>
                    <th v-for="col in items['columns']['against_cut_columns']">
                        {{ items['total_data']['against_cut_details'][col] }}
                    </th>
                    <th v-for="col in items['columns']['sew_columns']">
                        {{ items['total_data']['sewing_details'][col] }}
                    </th>
                    <th v-for="col in items['columns']['against_sew_columns']">
                        {{ items['total_data']['against_sew_details'][col] }}
                    </th>
                    <th v-for="col in items['columns']['finishing_columns']">
                        {{ items['total_data']['finishing_details'][col] }}
                    </th>
                    <th></th>
                    <th></th>
                    <th></th>
                </tr>
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

import {ref, onMounted, createApp} from 'vue';
import MultiProcessReport from './MultiProcessReport.vue'
import MultiSelectListConverter from './MultiSelectListConverter.vue'

let category = null
let lot_status = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})
let lot_list = null
let item_list = null
const multiReport = ref(null)
let process_list = ref([])

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
    $(el).find(".lot-input").html("");
    lot_list = frappe.ui.form.make_control({
        parent: $(el).find(".lot-input"),
        df: {
            fieldtype: "MultiSelectList",
            fieldname: "lot",
            label: "Lot",
            options: "Lot",
            get_data: function (txt) {
                return frappe.db.get_link_options("Lot", txt);
            },
        },
        doc: sample_doc.value,
        render_input: true,
    })
    
    $(el).find(".item-input").html("");
    item_list = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: {
            fieldtype: "MultiSelectList",
            fieldname: "item",
            label: "Item",
            options: "Item",
            get_data: function(txt){
                return frappe.db.get_link_options("Item", txt)
            }
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

function get_work_in_progress_report(){
    let lot_list_val = lot_list.get_value()
    let item_list_val = item_list.get_value()
    process_list.value = multiReport.value.process_list
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
                "process_list": process_list.value
            },
            freeze: true,
            freeze_message: "Fetching Data",
            callback: function(r){
                items.value = r.message
            }
        })
    }
}

function get_list_items(){
    let d = new frappe.ui.Dialog({
        fields: [
            {
                "fieldname": "pop_up_html",
                "fieldtype": "HTML"
            }
        ],
        primary_action(){
            if (i.select_value == 'Item'){
                let updated_list = item_list.get_value().concat(i.list)
                item_list.set_value(updated_list)
            }
            else if(i.select_value == 'Lot'){
                let updated_list = lot_list.get_value().concat(i.list)
                console.log(updated_list)
                lot_list.set_value(updated_list)
            }
            d.hide()
        }
    })
    d.fields_dict['pop_up_html'].$wrapper.html("")
    let el = d.fields_dict['pop_up_html'].$wrapper.get(0)
    let vue = createApp(MultiSelectListConverter, {
        "items_list": ['Lot', 'Item']
    })
    i = vue.mount(el)
    d.show()
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
.table-container {
    width: 100%;
    overflow: auto;
    max-height: 70vh;
    -webkit-overflow-scrolling: touch;
    border: 2px solid #000;
    border-radius: 6px;
    background: #fff;
}

.bordered-table {
    width: 100%;
    min-width: 1200px; /* ensures scrollable area */
    border-collapse: collapse;
    text-align: center;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    white-space: nowrap; /* prevents columns from wrapping */
}

.bordered-table th {
    background-color: #f8f9fa;
    position: sticky;
    top: 0;
    z-index: 1;
    font-weight: 600;
}
.table-container::-webkit-scrollbar {
    height: 8px;
}
.table-container::-webkit-scrollbar-thumb {
    background-color: #ccc;
    border-radius: 4px;
}
.table-container::-webkit-scrollbar-thumb:hover {
    background-color: #999;
}

</style>