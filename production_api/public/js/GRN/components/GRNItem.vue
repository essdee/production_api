<template>
    <div ref="root" class="frappe-control">
        <table v-if="docstatus!==0" class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td v-if="i.primary_attribute">
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-for="attr in j.values" :key="attr">
                                <div v-if="against == 'Purchase Order'">
                                    <div v-if="attr.received">
                                        {{ attr.received }}<span v-if="j.default_uom">{{ ' ' + j.default_uom }}</span>
                                        <span v-if="attr.secondary_qty">
                                                ({{ attr.secondary_received }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                        </span>
                                    </div>
                                    <div v-else class="text-center">
                                    ---
                                    </div>
                                </div>
                                <div v-else>
                                    {{ attr.qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom }}</span>
                                </div>    
                                
                            </td>
                            <td>{{ j.comments }}</td>
                        </tr>
                    </table>
                </td>
                <td v-else>
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th>Received Quantity</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-if="against == 'Purchase Order'">
                                {{ j.values['default'].received }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="j.values['default'].secondary_received">
                                    <br>
                                    ({{ j.values['default'].secondary_received }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <td v-else>
                                {{ j.values['default'].qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                            </td>
                            <td>{{ j.comments }}</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <table v-else-if="against_id" class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td v-if="i.primary_attribute">
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                            <th>Comments</th>
                            <th>Edit</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-for="attr in j.values" :key="attr">
                                <div v-if="attr.qty">
                                    {{ attr.qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom }}</span>
                                    <span v-if="attr.secondary_qty">
                                            ({{ attr.secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                    </span>

                                    <form v-if="against == 'Purchase Order'">
                                        <input class="form-control" type="number" v-model.number="attr.received" @blur="update_received_qty(attr, 'received')" min="0" step="0.001"/>
                                        <input class="form-control" v-if="attr.secondary_qty" type="number" v-model.number="attr.secondary_received" @blur="update_received_qty(attr, 'secondary_received')" min="0" step="0.001"/>
                                    </form>
                                </div>

                                <div v-else class="text-center">
                                    ---
                                </div>
                            </td>
                            <td>
                                <input class="form-control" type="text" v-model="j.comments"/>
                            </td>
                            <td v-if="against == 'Work Order'">
                                <div @click='edit_item(item_index,item1_index)'>Edit</div> 
                                 <!--<div class="pull-right cursor-pointer"  v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>-->
                          </td>
                        </tr>
                    </table>
                </td>
                <td v-else>
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th>Pending Quantity</th>
                            <th v-if="against == 'Purchase Order'">Received Quantity</th>
                            <th>Comments</th>
                            <th v-if="against == 'Work Order'">Edit</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-if="against == 'Purchase Order'">
                                {{ j.values['default'].pending_qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="j.values['default'].secondary_qty">
                                    <br>
                                    ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <td v-else>
                                {{ j.values['default'].qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="j.values['default'].secondary_qty">
                                    <br>
                                    ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <td v-if="against == 'Purchase Order'">
                                <form>
                                    <input class="form-control" type="number" v-model.number="j.values['default'].received" step="0.001" @blur="update_received_qty(j.values['default'], 'received')" min="0" />
                                    <input class="form-control" v-if="j.values['default'].secondary_qty" type="number" min="0" step="0.001" v-model.number="j.values['default'].secondary_received" @blur="update_received_qty(j.values['default'], 'secondary_received')"/>
                                </form>
                            </td>
                            <td>
                                <input class="form-control" type="text" v-model="j.comments"/>
                            </td>
                            <td v-if="against == 'Work Order'">
                                <div @click='edit_item(item_index,item1_index)'>Edit</div>
                                <!-- <div class="pull-right cursor-pointer"  v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div> -->
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <table class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td v-if="i.primary_attribute && i.created === 1">
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <thead>
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th>{{ i.primary_attribute }}</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th>Accepted</th>
                            <th>Rejected</th>
                            <th>Rework Details</th>
                            <th>Comments</th>
                        </tr>
                        </thead>
                        <tbody>
                            <template v-for="(j, item1_index) in i.items">
                                <template v-if="i.created && j.created">
                                    <tr v-for="(k, item2_index) in i.primary_attribute_values" :key="item2_index">
                                        <td>{{ item2_index + 1 }}</td>
                                        <td>{{ j.name }}</td>
                                        <td>{{ j.lot }}</td>
                                        <td>{{ k }}</td>
                                        <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                                        <td>{{ get_accepted(item_index,item1_index, k) }}</td>
                                        <td>{{ get_rejected(item_index,item1_index, k) }}</td>
                                        <td>{{ get_rework_details(item_index, item1_index, k)}}</td>
                                        <td>{{ j.comments }}</td>
                                    </tr>
                                </template>
                            </template>
                        </tbody>
                    </table>
                </td>
                <td v-else>
                     <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0 && i.created === 1">
                        <thead>
                            <tr>
                                <th>S.No.</th>
                                <th>Item</th>
                                <th>Lot</th>
                                <th>Accepted </th>
                                <th>Rejected </th>
                                <th>Rework Details</th>
                                <th>Comments</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template v-for="(j, item1_index) in i.items" :key="item1_index">
                                <template v-if="i.created && j.created">
                                    <tr>
                                        <td>{{ item1_index + 1 }}</td>
                                        <td>{{ j.name }}</td>
                                        <td>{{ j.created }}</td>
                                        <td>{{ get_accepted(item_index,item1_index, null)}}</td>
                                        <td>{{ get_rejected(item_index,item1_index, null)}}</td>
                                        <td>{{ get_rework_details(item_index,item1_index, null)}}</td>
                                        <td>{{ j.comments }}</td>
                                    </tr>
                                </template>
                            </template>    
                        </tbody>
                    </table>
                </td>
            </tr>
        </table>
        <div >
            <div class="row">
                <div class="lot-name col-md-5"></div>
                <div class="item-name col-md-5"></div>
            </div>
            <div>
                <div class='attributes col-md-5'></div>
                <div class='attributes-right col-md-5'></div>
            </div>
            <div>
                <div class='qty-parameters col-md-5'></div>
            </div>
            <div v-if="show_button">
                <button @click=call()>Add Item</button>
            </div>
        </div>    
    </div>
</template>

<script setup>
import EventBus  from '../../bus';

import { ref, onMounted, computed, watch } from 'vue'

const docstatus = ref(0);
const items = ref([]);
const supplier = ref(null);
const against = ref(null);
const against_id = ref(null);
let _skip_watch = false;
const attribute_values = ref([])
const data_qty = ref([])
const edit_index = ref(-1)
const edit_index1 = ref(-1)
const cur_item = ref(null)
const cur_lot = ref(null)
let lot_input = null
let item_input = null
const sample_doc = ref({})
const controlRefs = ref({
    quantities: [],
});
const show_button = ref(false)

function get_accepted(ind, ind1, attr){
    if(attr){
        return items.value[ind].items[ind1].values[attr.toString()]['accepted_qty'] 
    }
    else{
        return items.value[ind].items[ind1].values['default']['accepted_qty']

    }
}
function get_rejected(ind, ind1, attr){
    if(attr){
        return items.value[ind].items[ind1].values[attr.toString()]['rejected_qty']
    }
    else{
        return items.value[ind].items[ind1].values['default']['rejected_qty']
    }
}
function get_rework_details(ind, ind1, attr){
    if(attr){
        return items.value[ind].items[ind1].values[attr.toString()]['rework_details']
    }
    else{
        return items.value[ind].items[ind1].values['default']['rework_details']
    }
}


function edit_item(index,index1){
    let el = root.value;
    $(el).find('.lot-name').html("");
    $(el).find('.item-name').html("");
    $(el).find('.attributes').html("");
    $(el).find('.qty-parameters').html("");
    controlRefs.value.quantities = []
    edit_index.value = index
    edit_index1.value = index1
    attribute_values.value = []
    data_qty.value = []
    cur_item.value = null
    cur_lot.value = null
    show_button.value = true
    let row = items.value[index].items[index1]
    let data1 = row.values
    let data2 = row.attributes
    cur_item.value = row.name
    cur_lot.value = row.lot
    Object.keys(data1).forEach(key => {
        const qty = data1[key].qty;
        data_qty.value.push({ [key]: qty });
    });
    Object.keys(data2).forEach(key => {
        const attr = data2[key]
        attribute_values.value.push({[key] : attr})
    })
    create_attributes(attribute_values.value, data_qty.value, cur_item.value,cur_lot.value ,index, index1)
}


function getControlValues(refs) {
    const values = []
    refs.forEach(control => {
        const value = control.get_value();
        control.set_value(0)
        values.push(value);
    });
    return values;
}

function call(){
    let result = getControlValues(controlRefs.value.quantities)
    add_item(result)
}

function create_attributes(attributes, quantities, item, lot, idx, idx1) {
    let el = root.value;
    $(el).find('.lot-name').html("");
    let lot_input = frappe.ui.form.make_control({
        parent: $(el).find('.lot-name'),
        df: {
            fieldtype: 'Data',
            fieldname: 'lot',
            label: 'Lot',
            default: lot,
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    lot_input.set_value(lot)
    lot_input.df.read_only = 1;
    $(el).find('.item-name').html("");
    let item_input = frappe.ui.form.make_control({
        parent: $(el).find('.item-name'),
        df: {
            fieldtype: 'Data',
            fieldname: 'item',
            label: 'Item',
            default: item,
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    item_input.set_value(item)
    item_input.df.read_only = 1
    $(el).find('.attributes').html("");
    let attribute_parameters = []
    attributes.forEach(row => {
        let classname = ""
        Object.keys(row).forEach((key,index) => {
            if(index%2 == 0){
                classname += '.attributes';
            }
            else{
                classname += '.attributes-right';
            }
            attribute_parameters[index] = frappe.ui.form.make_control({
                parent: $(el).find(classname),
                df: {
                    fieldtype: 'Data',
                    fieldname: key + '_parameter',
                    label: key,
                    reqd: true,
                },
                doc: sample_doc.value,
                render_input: true,
            });
            attribute_parameters[index].set_value(row[key])
            attribute_parameters[index].df.read_only = 1
        });
    });    
    $(el).find('.qty-parameters').html("");
   
    let qty_parameters = []
    quantities.forEach(row => {
        let classname = ".qty-parameters"
        Object.keys(row).forEach((key,index) => {
            let x = key
            if (key == 'default'){
                key = ""
            }
            qty_parameters[index] = frappe.ui.form.make_control({
                parent: $(el).find(classname),
                df: {
                    fieldtype: 'Float',
                    fieldname: key + '_parameter',
                    label: key + ' Received',
                    reqd:true,
                },
                doc: sample_doc.value,
                render_input: true,
            });
            qty_parameters[index].set_value(row[x])
            qty_parameters[index].df.read_only = 1
            qty_parameters[index][0] = frappe.ui.form.make_control({
                parent: $(el).find('.qty-parameters'),
                df: {
                    fieldtype: 'Float',
                    fieldname: key + '_accepted',
                    label: key + ' Accepted',
                    reqd:true,
                },
                doc: sample_doc.value,
                render_input: true,
            });
            controlRefs.value.quantities.push(qty_parameters[index][0])
            qty_parameters[index][1] = frappe.ui.form.make_control({
                parent: $(el).find('.qty-parameters'),
                df: {
                    fieldtype: 'Float',
                    fieldname: key + '_rejected',
                    label: key + ' Rejected',
                    reqd:true,
                },
                doc: sample_doc.value,
                render_input: true,
            });
            controlRefs.value.quantities.push(qty_parameters[index][1])
            qty_parameters[index][2] = frappe.ui.form.make_control({
                parent: $(el).find('.qty-parameters'),
                df: {
                    fieldtype: 'Small Text',
                    fieldname: key + '_rework',
                    label: key + ' Rework',
                    reqd:true,
                },
                doc: sample_doc.value,
                render_input: true,
            });
            controlRefs.value.quantities.push(qty_parameters[index][2])
        });
    });
}

function add_item(data) {  
    let x = 0
    Object.keys(items.value[edit_index.value].items[edit_index1.value].values).forEach((row,index) => { 
        items.value[edit_index.value].items[edit_index1.value]['values'][row.toString()]['accepted_qty'] = data[ x ]
        items.value[edit_index.value].items[edit_index1.value]['values'][row.toString()]['rejected_qty'] = data[ x + 1]
        items.value[edit_index.value].items[edit_index1.value]['values'][row.toString()]['rework_details'] = data[ x + 2 ]
        x = x + 3
    })
    items.value[edit_index.value]['created'] = 1
    items.value[edit_index.value].items[edit_index1.value]['created'] = 1
}

const root = ref(null);

onMounted(() => {
    console.log('new-grn-item mounted');
    EventBus.$on("update_grn_details", data => {
        load_data(data);
    })
});

function load_data(data, skip_watch=false) {
    if (data) {
        // Only update the values which are present in the data object
        // let keys = ['supplier', 'against', 'against_id', 'docstatus', 'items']
        // for (let key in keys) {
        //     if (data.hasOwnProperty(key)) {
        //         this[key] = data[key];
        //     }
        // }

        if (data.hasOwnProperty('supplier')) {
            supplier.value = data['supplier']
        }
        if (data.hasOwnProperty('against')) {
            against.value = data['against']
        }
        if (data.hasOwnProperty('against_id')) {
            against_id.value = data['against_id']
        }
        if (data.hasOwnProperty('docstatus')) {
            docstatus.value = data['docstatus']
        }
        if (data.hasOwnProperty('items')) {
            items.value = data['items']
        }

        if (data.hasOwnProperty("against_id") && !skip_watch) {
            against_id_changed();
        }
        if (data.hasOwnProperty("items")) {
            _skip_watch = skip_watch;
        }
    }
}

function update_status() {
    docstatus.value = cur_frm.doc.docstatus;
}

function get_purchase_order_items() {
    frappe.call({
        method: "production_api.production_api.doctype.purchase_order.purchase_order.get_purchase_order_items",
        args: {
            "purchase_order": against_id.value
        },
        callback: function(r) {
            if (r.message) {
                items.value = r.message;
            }
        }
    });
}
function get_work_order_items(){
    frappe.call({
        method: "production_api.production_api.doctype.work_order.work_order.get_work_order_items",
        args: {
            "work_order": against_id.value
        },
        callback: function(r) {
            if (r.message) {
                items.value = r.message;
            }
        }
    });
}


function clear_items() {
    items.value = [];
}

function against_id_changed() {
    if (against_id.value) {
        if (against.value == "Purchase Order") {
            get_purchase_order_items();
        }
        else{
            get_work_order_items();
        }
    } else {
        clear_items();
    }
}

function get_items() {
    // Parse the received values to 0 if it is empty or null
    for (let i in items.value) {
        for (let j in items.value[i].items) {
            for (let k in items.value[i].items[j].values) {
                if (items.value[i].items[j].values[k].received == null || items.value[i].items[j].values[k].received == "") {
                    items.value[i].items[j].values[k].received = 0;
                }
                if (items.value[i].items[j].values[k].accepted_qty == null || items.value[i].items[j].values[k].accepted_qty == "") {
                    items.value[i].items[j].values[k].accepted_qty = 0;
                }
                if (items.value[i].items[j].values[k].rework_details == null || items.value[i].items[j].values[k].rework_details == "") {
                    items.value[i].items[j].values[k].rework_details = "";
                }
                if (items.value[i].items[j].values[k].rejected_qty == null || items.value[i].items[j].values[k].rejected_qty == "") {
                    items.value[i].items[j].values[k].rejected_qty = 0;
                }
                if (items.value[i].items[j].values[k].secondary_received == null || items.value[i].items[j].values[k].secondary_received == "") {
                    items.value[i].items[j].values[k].secondary_received = 0;
                }
            }
        }
    }
    return items.value;
}
function update_reworks(item, key){
    item[key] = item[key]
}
function update_received_qty(item, key) {
    item[key] = parseFloat(parseFloat(item[key]).toFixed(3));
}

watch(items, (newVal, oldVal) => {
    console.log("Item Updated", _skip_watch)
    if (_skip_watch) {
        _skip_watch = false;
        return;
    }
    EventBus.$emit("grn_updated", true);
}, {deep: true})

defineExpose({
	items,
    load_data,
    update_status,
    get_items,
});
</script>