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
            <div style="padding-top:27px;padding-left:10px;">
                <button class="btn btn-primary" @click="get_list_items()">Paste</button>
            </div>
        </div>
        <multi-process-report ref="multiReport"/>
        <div v-if="items && Object.keys(items).length > 0">
            <div v-for="data in items['lot_data']">
                <h3>{{ data.lot }} - {{ data.style }}</h3>
                <table class="table table-md table-sm-bordered bordered-table">
                    <tr>
                        <th>Size</th>
                        <th v-for="size in data.sizes">{{ size }}</th>
                        <th>Total</th>
                    </tr>
                    <tr v-for="col, val in items['rows']['cut_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(data['cut_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ data['cut_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(data['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ data['total_details'][col+'_total'] }}
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['against_cut_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes" >
                            <div v-if="data['against_cut_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['against_cut_details'][col][size]) 
                                : { background: 'white' }"
                            >
                                {{ data['against_cut_details'][col][size] }}
                            </div>
                        </td>
                        <td>
                            <div v-if="data['against_cut_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['total_details'][col+'_total']) 
                                : { background: 'white' }"
                            >
                                {{ data['total_details'][col+'_total'] }}
                            </div>
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['sew_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(data['sewing_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ data['sewing_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(data['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ data['total_details'][col+'_total'] }}
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['against_sew_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes">
                            <div v-if="data['against_sew_details']?.[col]" 
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['against_sew_details'][col][size]) 
                                : { background: 'white' }"
                            >
                                {{ data['against_sew_details'][col][size] }}
                            </div>
                        </td>
                        <td>
                            <div v-if="data['against_sew_details']?.[col]" 
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['total_details'][col+'_total']) 
                                : { background: 'white' }"
                            >
                                {{ data['total_details'][col+"_total"] }}
                            </div>
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['finishing_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(data['finishing_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ data['finishing_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(data['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ data['total_details'][col+'_total'] }}
                        </td>
                    </tr>
                </table>
            </div>
            <h3 style="text-decoration: underline;"> Style wise Summary</h3>
            <div v-for="data in items['item_data']">
                <h3>{{ data.style }}</h3>
                <table class="table table-md table-sm-bordered bordered-table">
                    <tr>
                        <th>Size</th>
                        <th v-for="size in data.sizes">{{ size }}</th>
                        <th>Total</th>
                    </tr>
                    <tr v-for="col, val in items['rows']['cut_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(data['cut_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ data['cut_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(data['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ data['total_details'][col+'_total'] }}
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['against_cut_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes" >
                            <div v-if="data['against_cut_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['against_cut_details'][col][size]) 
                                : { background: 'white' }"
                            >
                                {{ data['against_cut_details'][col][size] }}
                            </div>
                        </td>
                        <td>
                            <div v-if="data['against_cut_details']?.[col]"
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['total_details'][col+'_total']) 
                                : { background: 'white' }"
                            >
                                {{ data['total_details'][col+'_total'] }}
                            </div>
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['sew_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(data['sewing_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ data['sewing_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(data['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ data['total_details'][col+'_total'] }}
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['against_sew_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes">
                            <div v-if="data['against_sew_details']?.[col]" 
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['against_sew_details'][col][size]) 
                                : { background: 'white' }"
                            >
                                {{ data['against_sew_details'][col][size] }}
                            </div>
                        </td>
                        <td>
                            <div v-if="data['against_sew_details']?.[col]" 
                                :style="items['diff_rows'].includes(col) 
                                ? get_style(data['total_details'][col+'_total']) 
                                : { background: 'white' }"
                            >
                                {{ data['total_details'][col+"_total"] }}
                            </div>
                        </td>
                    </tr>
                    <tr v-for="col, val in items['rows']['finishing_rows']">
                        <td>{{ val }}</td>
                        <td v-for="size in data.sizes"
                            :style="items['diff_rows'].includes(col) 
                            ? get_style(data['finishing_details'][col][size]) 
                            : { background: 'white' }"
                        >
                            {{ data['finishing_details'][col][size] }}
                        </td>
                        <td :style="items['diff_rows'].includes(col) 
                            ? get_style(data['total_details'][col+'_total']) 
                            : { background: 'white' }"
                        >
                            {{ data['total_details'][col+'_total'] }}
                        </td>
                    </tr>
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
import MultiProcessReport from './MultiProcessReport.vue'

let lot_list = null
let item_list = null
let lot_status = null
let product_category = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})
let multiReport = ref(null)
let process_list = ref([])

onMounted(()=> {
    let el = root.value
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
    
    $(el).find(".lot-status-input").html("")
    lot_status = frappe.ui.form.make_control({
        parent: $(el).find(".lot-status-input"),
        df: {
            fieldname: "lot_status",
            fieldtype: "Select",
            label: "Status",
            options: "\nOpen\nClosed",
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

function get_size_wise_stock(){
    let open_status_val = lot_status.get_value()
    let lot_list_val = lot_list.get_value()
    let item_list_val = item_list.get_value()
    let category = product_category.get_value()
    process_list.value = multiReport.value.process_list
    if(lot_list_val.length == 0 && item_list_val.length == 0 && !category){
        frappe.msgprint("Select at least one Item or Lot, or select Category.")
    }
    else{
        frappe.call({
            method: "production_api.utils.get_size_wise_stock_report",
            args: {
                "open_status": open_status_val,
                "lot_list": lot_list_val,
                "item_list": item_list_val,
                "category": category, 
                "process_list": process_list.value,
            },
            freeze: true,
            freeze_message: "Fetching Size wise Report",
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