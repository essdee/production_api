<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Multi CCR Report</h3>
        <div style="display:flex;">
            <div class="lot-input col-md-3"></div>
            <div class="item-input col-md-3"></div>
            <div class="lot-status-input col-md-2"></div>
            <div class="product-category-input col-md-2"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_multiccr()">Show Report</button>
            </div>
            <div style="padding-top:27px;padding-left:10px;">
                <button class="btn btn-primary" @click="get_list_items()">Paste</button>
            </div>
        </div>
        <div style="display: flex; width: 100%;">
            <div v-if="selected_lots && lot_count > 0" style="width: 50%;">
                <h3> Selected Lots: {{ selected_lots.length }}</h3>
                <p style="padding: 10px;">{{ selected_lots.join(', ') }}</p>
            </div>
            <div v-if="output_lots && output_lots.length > 0" style="width: 50%;">
                <h3> Output Lots: {{ output_lots.length }}</h3>
                <p style="padding: 10px;">{{ output_lots.join(', ') }}</p>
            </div>
        </div>
        <div style="display: flex; width: 100%;">
            <div v-if="selected_items && item_count > 0" style="width: 50%;">
                <h3>Selected Items: {{ selected_items.length }}</h3>
                <p style="padding: 10px;">{{ selected_items.join(', ') }}</p>
            </div>
            <div v-if="output_items && output_items.length > 0" style="width: 50%;">
                <h3> Output Items: {{ output_items.length }}</h3>
                <p style="padding: 10px;">{{ output_items.join(', ') }}</p>
            </div>
        </div>
        <div v-if="item_data && Object.keys(item_data).length > 0">
            <h3>Style Wise Summary</h3>
            <div v-for="item_name in Object.keys(item_data)">
                <h3>{{ item_name }}</h3>
                <table class="table table-sm table-bordered">
                    <tr v-for="(i, item_index) in item_data[item_name]['completed_json']" :key="item_index">
                        <template v-if="!i.is_set_item">
                            <td>
                                <strong>Panels:</strong>
                                <span v-for="(panel,index) in i[i.stiching_attr]" :key="panel" class="panel-column">
                                    {{ panel }}<span v-if="index < i[i.stiching_attr].length - 1">,</span>
                                </span>
                            </td>
                        </template>
                    </tr>
                    <tr v-for="(i, item_index) in item_data[item_name]['completed_json']" :key="item_index">
                        <td>
                            <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                                <tr>
                                    <th>S.No.</th>
                                    <th v-for="(j, idx) in i.attributes" :key="idx">{{ j }}</th>
                                    <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                        {{ j }}
                                    </th>
                                    <th>Total</th>
                                    <th>Average Piece Weight</th>
                                    <th v-if="i.is_set_item">Panels</th>
                                </tr>
                                <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <td>{{item1_index + 1}}</td>
                                    <td v-for="(k, idx) in i.attributes" :key="idx">
                                        {{j.attributes[k]}}
                                    </td>
                                    <td v-for="(k, idx) in i.primary_attribute_values" :key="idx">
                                        <div v-if="j.values[k] ? j.values[k] > 0 : false">
                                            {{ j.values[k] ? j.values[k] : 0 }}
                                        </div>
                                        <div v-else>--</div>
                                    </td>
                                    <th>{{ j.total_qty }}</th>
                                    <th>{{ get_colour_piece_weight(item_name, j) }}</th>
                                    <th v-if='i.is_set_item'>
                                        <div v-for="panel in i[i.stiching_attr][j.attributes[i.set_item_attr]]" :key="panel">
                                            {{panel}}
                                        </div>
                                    </th>
                                </tr>
                                <tr>
                                    <th>Total</th>
                                    <th v-for="(j, idx) in i.attributes" :key="idx"></th>
                                    <th v-for="(k, idx) in i.primary_attribute_values" :key="idx">{{ i.total_qty[k] ? i.total_qty[k] : 0 }}</th>
                                    <th>{{ item_data[item_name]['total_qty'] }}</th>
                                    <th></th>
                                    <th v-if="i.is_set_item"></th>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
                <table class="table table-sm table-bordered">
                    <tr>
                        <th>S.No.</th>
                        <th>Cloth</th>
                        <th>Cloth Type</th>
                        <th>Colour</th>
                        <th>Dia</th>
                        <th>Required Weight</th>
                        <th>Received Weight</th>
                        <th>Used Weight</th>
                        <th>Balance Weight</th>
                    </tr>
                    <tr v-for="(i, item_index) in item_data[item_name]['cloth_details']" :key="item_index">
                        <td>{{ item_index + 1 }}</td>
                        <td>{{ i.cloth_item_variant }}</td>
                        <td>{{ i.cloth_type }}</td>
                        <td>{{ i.colour }}</td>
                        <td>{{ i.dia }}</td>
                        <td>{{ get_round(i.required_weight, 3) }}</td>
                        <td>{{ get_round(i.weight, 3) }}</td>
                        <td>{{ get_round(i.used_weight, 3) }}</td>
                        <td>{{ get_round(i.balance_weight, 3) }}</td>
                    </tr>
                    <tr v-if="item_data[item_name]['cloth_total']">
                        <td>Total</td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td>{{get_round(item_data[item_name]['cloth_total']['required'], 3)}}</td>
                        <td>{{get_round(item_data[item_name]['cloth_total']['received'], 3)}}</td>
                        <td>{{get_round(item_data[item_name]['cloth_total']['used'], 3)}}</td>
                        <td>{{get_round(item_data[item_name]['cloth_total']['balance'], 3)}}</td>
                    </tr>
                </table>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0">
            <div v-for="lot in Object.keys(items)">
                <h3>{{ lot }} - {{ items[lot]['item'] }}</h3>
                <div v-for="(group, group_index) in items[lot]['panel_groups']" :key="`${group.cutting_plan}-${group.panels}-${group_index}`" class="panel-group">
                    <h4>{{ group.panels }}</h4>
                    <div class="table-responsive">
                        <table class="table table-sm table-bordered">
                            <thead>
                                <tr>
                                    <th>S.No.</th>
                                    <th>Colour</th>
                                    <th>Cloth Type</th>
                                    <th>Received Weight</th>
                                    <th>Used Weight</th>
                                    <th>Balance Weight</th>
                                    <th v-for="size in group.sizes" :key="size">{{ size }}</th>
                                    <th>Total</th>
                                    <th>Piece Weight</th>
                                    <th>Required Weight</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(row, row_index) in group.rows" :key="`${row.colour}-${row.cloth_type}-${row_index}`">
                                    <td>{{ row_index + 1 }}</td>
                                    <td>{{ row.colour }}</td>
                                    <td>{{ row.cloth_type }}</td>
                                    <td>{{ get_round(row.received_weight, 3) }}</td>
                                    <td>{{ get_round(row.used_weight, 3) }}</td>
                                    <td>{{ get_round(row.balance_weight, 3) }}</td>
                                    <td v-for="size in group.sizes" :key="size">{{ get_quantity(row.sizes[size]) }}</td>
                                    <td>{{ get_quantity(row.total_pieces) }}</td>
                                    <td>{{ get_round(row.piece_weight, 4) }}</td>
                                    <td>{{ get_round(row.required_weight, 4) }}</td>
                                </tr>
                                <tr class="font-weight-bold">
                                    <th></th>
                                    <th>Total</th>
                                    <th></th>
                                    <th>{{ get_round(group.totals.received_weight, 3) }}</th>
                                    <th>{{ get_round(group.totals.used_weight, 3) }}</th>
                                    <th>{{ get_round(group.totals.balance_weight, 3) }}</th>
                                    <th v-for="size in group.sizes" :key="size">{{ get_quantity(group.totals.sizes[size]) }}</th>
                                    <th>{{ get_quantity(group.totals.total_pieces) }}</th>
                                    <th>{{ get_round(group.totals.piece_weight, 4) }}</th>
                                    <th>{{ get_round(group.totals.required_weight, 4) }}</th>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                <div v-if="items[lot]['recut_summary'] && items[lot]['recut_summary'].rows.length" class="panel-group">
                    <h4>Recut Summary</h4>
                    <div class="table-responsive">
                        <table class="table table-sm table-bordered">
                            <thead>
                                <tr>
                                    <th>S.No.</th>
                                    <th>Cloth Type</th>
                                    <th>Colour</th>
                                    <th>Dia</th>
                                    <th>Shade</th>
                                    <th>Weight in Kg's</th>
                                    <th>No. of Rolls</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(row, row_index) in items[lot]['recut_summary'].rows" :key="`${row.cloth_type}-${row.colour}-${row.dia}-${row.shade}-${row_index}`">
                                    <td>{{ row_index + 1 }}</td>
                                    <td>{{ row.cloth_type }}</td>
                                    <td>{{ row.colour }}</td>
                                    <td>{{ row.dia }}</td>
                                    <td>{{ row.shade }}</td>
                                    <td>{{ get_round(row.weight, 3) }}</td>
                                    <td>{{ get_quantity(row.no_of_rolls) }}</td>
                                </tr>
                                <tr class="font-weight-bold">
                                    <th></th>
                                    <th>Total</th>
                                    <th></th>
                                    <th></th>
                                    <th></th>
                                    <th>{{ get_round(items[lot]['recut_summary'].totals.weight, 3) }}</th>
                                    <th>{{ get_quantity(items[lot]['recut_summary'].totals.no_of_rolls) }}</th>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                <table class="table table-sm table-bordered">
                    <tr v-for="(i, item_index) in items[lot]['completed_json']" :key="item_index">
                        <template v-if="!i.is_set_item">
                            <td>
                                <strong>Panels:</strong>
                                <span v-for="(panel,index) in i[i.stiching_attr]" :key="panel" class="panel-column">
                                    {{ panel }}<span v-if="index < i[i.stiching_attr].length - 1">,</span>
                                </span>
                            </td>
                        </template>
                    </tr>
                    <tr v-for="(i, item_index) in items[lot]['completed_json']" :key="item_index">
                        <td>
                            <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                                <tr>
                                    <th>S.No.</th>
                                    <th v-for="(j, idx) in i.attributes" :key="idx">{{ j }}</th>
                                    <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                        {{ j }}
                                    </th>
                                    <th>Total</th>
                                    <th v-if="i.is_set_item">Panels</th>
                                </tr>
                                <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <td>{{item1_index + 1}}</td>
                                    <td v-for="(k, idx) in i.attributes" :key="idx">
                                        {{j.attributes[k]}}
                                        <span v-if="items[lot]['version'] == 'V2' || items[lot]['version'] == 'V3'">
                                            <span v-if="k == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                            <span v-else-if="k == 'Colour' && !j.is_set_item && j.attributes[k] != j.item_keys['major_colour'] && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                        </span>
                                    </td>
                                    <td v-for="(k, idx) in i.primary_attribute_values" :key="idx">
                                        <div v-if="j.values[k] ? j.values[k] > 0 : false">
                                            {{ j.values[k] ? j.values[k] : 0 }}
                                        </div>
                                        <div v-else>--</div>
                                    </td>
                                    <th>{{ j.total_qty }}</th>
                                    <th v-if='i.is_set_item'>
                                        <div v-for="panel in i[i.stiching_attr][j.attributes[i.set_item_attr]]" :key="panel">
                                            {{panel}}
                                        </div>
                                    </th>
                                </tr>
                                <tr>
                                    <th>Total</th>
                                    <th v-for="(j, idx) in i.attributes" :key="idx"></th>
                                    <th v-for="(k, idx) in i.primary_attribute_values" :key="idx">{{ i.total_qty[k] ? i.total_qty[k] : 0 }}</th>
                                    <th>{{ items[lot]['total_qty'] }}</th>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
                <table v-if="items[lot]['cloth_details'] && items[lot]['cloth_details'].length > 0" class="table table-sm table-bordered">
                    <tr>
                        <th>S.No.</th>
                        <th>Cloth</th>
                        <th>Cloth Type</th>
                        <th>Colour</th>
                        <th>Dia</th>
                        <th>Required Weight</th>
                        <th>Received Weight</th>
                        <th>Used Weight</th>
                        <th>Balance Weight</th>
                    </tr>
                    <tr v-for="(i, item1_index) in items[lot]['cloth_details']" :key="item1_index">
                        <td>{{item1_index + 1}}</td>
                        <td>{{ i.cloth_item_variant }}</td>
                        <td>{{ i.cloth_type }}</td>
                        <td>{{ i.colour }}</td>
                        <td>{{ i.dia }}</td>
                        <td>{{ get_round(i.required_weight, 3) }}</td>
                        <td>{{ get_round(i.weight, 3) }}</td>
                        <td>{{ get_round(i.used_weight, 3) }}</td>
                        <td>{{ get_round(i.balance_weight, 3) }}</td>
                    </tr>
                    <tr v-if="items[lot]['cloth_total']">
                        <td>Total</td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td>{{get_round(items[lot]['cloth_total']['required'], 3)}}</td>
                        <td>{{get_round(items[lot]['cloth_total']['received'], 3)}}</td>
                        <td>{{get_round(items[lot]['cloth_total']['used'], 3)}}</td>
                        <td>{{get_round(items[lot]['cloth_total']['balance'], 3)}}</td>
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
import MultiSelectListConverter from '../../components/MultiSelectListConverter.vue';

let lot_list = null
let item_list = null
let lot_status = null
let product_category = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})
let selected_lots = ref(null)
let lot_count = ref(0)
let selected_items = ref(null)
let item_count = ref(0)
let output_lots = ref([])
let output_items = ref([])
let item_data = ref({})

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

function get_round(value, precision){
    let number = parseFloat(value)
    return Number.isFinite(number) ? number.toFixed(precision) : (0).toFixed(precision)
}

function get_quantity(value){
    let number = parseFloat(value)
    if(!Number.isFinite(number) || number === 0){
        return "--"
    }
    return Number.isInteger(number) ? number : number.toFixed(2)
}

function get_colour_piece_weight(item_name, row){
    let colour = row.attributes?.Colour || row.item_keys?.major_colour
    let value = item_data.value[item_name]?.average_piece_weight_by_colour?.[colour]
    return value == null ? "--" : get_round(value, 4)
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

function get_multiccr(){
    let open_status_val = lot_status.get_value()
    let lot_list_val = lot_list.get_value()
    let item_list_val = item_list.get_value()
    let category = product_category.get_value()
    if(lot_list_val.length == 0 && item_list_val.length == 0 && !category){
        frappe.msgprint("Select at least one Item or Lot, or select Category.")
    }
    else{
        selected_lots.value = lot_list_val
        selected_items.value = item_list_val
        lot_count.value = lot_list_val.length
        item_count.value = item_list_val.length
        frappe.call({
            method: "production_api.utils.get_multiccr",
            args: {
                "open_status": open_status_val,
                "lot_list": lot_list_val,
                "item_list": item_list_val,
                "category": category, 
            },
            freeze: true,
            freeze_message: "Fetching Multi CCR Report",
            callback: function(r){
                items.value = r.message.data
                output_lots.value = r.message.output_lots
                output_items.value = r.message.output_items
                item_data.value = r.message.item_data
            }
        })
    }
}
</script>

<style scoped>
.panel-column {
    display: inline;
}

.panel-group {
    margin-bottom: 20px;
}
</style>
