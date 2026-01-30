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
            <div style="padding-top:27px;padding-left:10px;">
                <button class="btn btn-primary" @click="get_list_items()">Paste</button>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0">
            <div v-for="item_name in Object.keys(items)">
                <h3>{{ item_name }}</h3>
                <table class="table table-md table-sm-bordered bordered-table">
                    <tr>
                        <th>Month</th>
                        <th>Cut Qty</th>
                        <th>Sewing Sent</th>
                        <th>Finishing Inward</th>
                        <th>Dispatch</th>
                    </tr>
                    <template v-for="month in Object.keys(items[item_name])">
                        <tr>
                            <td>{{ month }}</td>
                            <td>{{ items[item_name][month]['cut_qty'] }}</td>
                            <td>{{ items[item_name][month]['sewing_sent'] }}</td>
                            <td>{{ items[item_name][month]['finishing_inward'] }}</td>
                            <td>{{ items[item_name][month]['dispatch'] }}</td>
                        </tr>    
                    </template>
                </table>
            </div>  
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
import MultiSelectListConverter from './MultiSelectListConverter.vue'

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
            fieldtype: "MultiSelectList",
            options: "Lot",
            label: "Lot",
            get_data: function (txt) {
                return frappe.db.get_link_options("Lot", txt);
            },
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".item-input").html("");
    item = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: {
            fieldname: "item",
            fieldtype: "MultiSelectList",
            options: "Item",
            label: "Item",
            get_data: function(txt){
                return frappe.db.get_link_options("Item", txt)
            }
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

function get_list_items(){
    let i = null
    let d = new frappe.ui.Dialog({
        fields: [
            {
                "fieldname": "pop_up_html",
                "fieldtype": "HTML"
            }
        ],
        primary_action(){
            if (i.select_value == 'Item'){
                let updated_list = item.get_value().concat(i.list)
                item.set_value(updated_list)
            }
            else if(i.select_value == 'Lot'){
                let updated_list = lot.get_value().concat(i.list)
                lot.set_value(updated_list)
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

function get_month_wise_report(){
    if(lot.get_value().length == 0 && item.get_value().length == 0){
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