<template>
    <div ref="root">
        <div v-if="items && pop_up == 1 && !from_page">
            <h4>Completed Cut Quantity</h4>        
        </div>
        <table v-if="pop_up == 1 || pop_up == 2" class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <template v-if="!i.is_set_item">
                    <td>
                        <strong>Panels:</strong>
                        <div v-for="(panel,index) in i[i.stiching_attr]" :key="panel" class="panel-column">
                            {{ panel }}<span v-if="index < i[i.stiching_attr].length - 1">,</span>
                        </div>
                    </td>
                </template>
            </tr>
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td>
                    <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                        <tr>
                            <th>S.No.</th>
                            <th v-for="(j, idx) in i.attributes" :key="idx">{{ j }}</th>
                            <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                {{ j }}
                            </th>
                            <th v-if="i.is_set_item">Panels</th>
                            <th v-if="!from_page && pop_up == 1 || pop_up == 2">Completed</th>
                            <th v-if="from_page">Total</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{item1_index + 1}}</td>
                            <td v-for="(k, idx) in i.attributes" :key="idx">
                                {{j.attributes[k]}}
                                <span v-if="version == 'V2' || version == 'V3'">
                                    <span v-if="k == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                    <span v-else-if="k == 'Colour' && !j.is_set_item && j.attributes[k] != j.item_keys['major_colour'] && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                </span>
                            </td>
                            <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                <div v-if="j.values[k] > 0">
                                    {{ j.values[k] }}
                                </div>
                                <div v-else>--</div>
                            </td>
                            <td v-if='i.is_set_item'>
                                <div v-for="panel in i[i.stiching_attr][j.attributes[i.set_item_attr]]" :key="panel">
                                    {{panel}}
                                </div>
                            </td>
                            <td v-if="pop_up == 1 && !from_page"><input type="checkbox" v-model="j['completed']" disabled></td>
                            <td v-else-if="pop_up == 2 && !from_page"><input type="checkbox" v-model="j['completed']"></td>
                            <td v-if="from_page">{{ j['total_qty'] }}</td>
                        </tr>
                        <tr v-if="pop_up == 1">
                            <td>Total</td>
                            <td v-for="(j, idx) in i.attributes" :key="idx"></td>
                            <td v-for="(j, idx) in i.total_qty" :key="idx">{{j}}</td>
                            <td v-if="!from_page"></td>
                            <td v-else>{{ i['total_sum'] }}</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <div v-if="pop_up == 3" style="padding:10px;">
            <div style="width:100%;display:flex;justify-content:space-between">
                <div><strong>Lot : </strong> {{lot}}</div>
                <div><strong>Item: </strong>{{item}}</div>
            </div>    
            <div><strong>Date: </strong>{{datetime}}</div>
            <table class="table table-sm table-bordered">
                <tr v-for="(i, item_index) in items" :key="item_index">
                    <template v-if="!i.is_set_item">
                        <td>
                            <strong>Panels:</strong>
                            <div v-for="(panel,index) in i[i.stiching_attr]" :key="panel" class="panel-column">
                                {{ panel }}<span v-if="index < i[i.stiching_attr].length - 1">,</span>
                            </div>
                        </td>
                    </template>
                </tr>
                <tr v-for="(i, item_index) in items" :key="item_index">
                    <td v-if="!i.is_set_item">
                        <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                            <tr>
                                <th>S.No.</th>
                                <th v-for="(j, idx) in i.attributes" :key="idx">{{ j }}</th>
                                <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                    {{ j }}
                                </th>
                                <th>Total</th>
                            </tr>
                            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                <td>{{item1_index + 1}}</td>
                                <td v-for="(k, idx) in i.attributes" :key="idx">{{j.attributes[k]}}</td>
                                <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                    <div v-if="j.values[k] > 0">
                                        <div v-if="j['completed']">
                                            {{ j.values[k] }}
                                        </div>    
                                        <div v-else> -- </div>
                                    </div>
                                    <div v-else>--</div>
                                </td>
                                <td><strong>{{j.total_qty}}</strong></td>
                            </tr>
                            <tr>
                                <td>Total</td>
                                <td v-for="(j, idx) in i.attributes" :key="idx"></td>
                                <td v-for="(j, idx) in completed_total" :key="idx"><strong>{{j}}</strong></td>
                                <td v-if="total_cut_qty['qty']"><strong>{{total_cut_qty['qty']}}</strong></td>
                            </tr>
                        </table>
                    </td>
                    <td v-else>
                        <template v-for="part in Object.keys(i.Panel)" :key="part">
                            <h3>{{part}}</h3>
                            <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                                <tr>
                                    <th v-for="(j, idx) in i.attributes" :key="idx">{{ j }}</th>
                                    <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                        {{ j }}
                                    </th>
                                    <th>Total</th>
                                </tr>
                                <template v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <tr v-if="check(j.attributes, part)">
                                        <td v-for="(k, idx) in i.attributes" :key="idx">
                                            {{j.attributes[k]}}
                                            <span v-if="version == 'V2' || version == 'V3'">
                                                <span v-if="k == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                                <span v-else-if="k == 'Colour' && !j.is_set_item && j.attributes[k] != j.item_keys['major_colour'] && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                            </span>
                                        </td>
                                        <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                            <div v-if="j.values[k] > 0">
                                                <div v-if="j['completed']">
                                                    {{ j.values[k] }}
                                                </div>    
                                                <div v-else> -- </div>
                                            </div>
                                            <div v-else>--</div>
                                        </td>
                                        <td><strong>{{j.total_qty}}</strong></td>
                                    </tr>
                                </template>  
                                <tr>
                                    <td v-for="(j, idx) in i.attributes" :key="idx"></td>
                                    <td v-for="(j, idx) in completed_total[part]" :key="idx"><strong>{{j}}</strong></td>
                                    <td v-if="total_cut_qty[part]"><strong>{{total_cut_qty[part]}}</strong></td>
                                </tr>  
                            </table>
                        </template>    
                    </td>
                </tr>
            </table>
        </div>    
    </div>  
</template>

<script setup>
import {ref, onMounted} from 'vue';

let items = ref(null)
let pop_up = ref(0)
let lot = null
let item = null
let datetime = ref(null)
let items2 = ref(null)
let completed_total = ref({})
let version = null
let total_cut_qty = {}
let from_page = false

const props = defineProps({
    data: {
        type: Array,
        default: () => []
    }
})

onMounted(()=> {
    if(props.data){
        from_page = true
        items.value = props.data;
        items2.value = props.data;
        pop_up.value = 1
    }
    let today = new Date()
    let date = format_datetime(today.getDate()) + "-" + format_datetime(today.getMonth()+1) + "-" + today.getFullYear()
    let time = format_datetime(today.getHours()) + ":" + format_datetime(today.getMinutes()) + ":" + format_datetime(today.getSeconds())
    datetime.value = date+" "+time
})

function format_datetime(val){
    if(val < 10){
        return '0'+val
    }
    return val
}

function load_data(item_data, is_pop_up){
    lot = cur_frm.doc.lot
    item = cur_frm.doc.item
    version = cur_frm.doc.version
    try {
        items.value = JSON.parse(item_data);
        items2.value = JSON.parse(item_data);
        pop_up.value = is_pop_up
        if(pop_up.value == 3){
            get_total()
        }
    } 
    catch(e) {
        console.log(e)
    }
}

function get_items(){
    let is_system_manager = frappe.user.has_role('System Manager')
    for(let i = 0 ; i < items.value[0]['items'].length; i++){
        if(!is_system_manager && !items.value[0]['items'][i]['completed'] && items2.value[0]['items'][i]['completed']){
            items.value[0]['items'][i]['completed'] = true
        }
    }
    return items.value
}

function get_total(){
    let total_dict =  {}
    for(let i = 0 ; i < items.value.length; i++){
        let item = items.value[i]
        if(!item.is_set_item){
            total_cut_qty['qty'] = 0
            item.items.forEach((row) => {
                if(row.completed){
                    let x = 0
                    Object.keys(row.values).forEach(key => {
                        if (total_dict[key]){
                            total_dict[key] += row.values[key]
                        }
                        else{
                            total_dict[key] = row.values[key]
                        }
                        x += row.values[key]
                    })
                    row.total_qty = x
                    total_cut_qty['qty'] += x
                }
            })
        }
        else{
            Object.keys(item.Panel).forEach(part => {
                total_cut_qty[part] = 0
                item.items.forEach((row) => {
                    if(row.completed && row.attributes[item.set_item_attr] == part){
                        let x = 0
                        Object.keys(row.values).forEach(key => {
                            x += row.values[key]
                            if (!total_dict[part]){
                                total_dict[part] = {}
                            }    
                            if (total_dict[part][key]){
                                total_dict[part][key] += row.values[key]
                            }
                            else{
                                total_dict[part][key] = row.values[key]
                            }
                        })
                        row.total_qty = x
                        total_cut_qty[part] += x
                    }
                })  
            })
        }
    }
    completed_total.value = total_dict
}

function check(attributes, part){
    if(attributes[items.value[0]['set_item_attr']] == part){
        return true
    }
    return false
}
defineExpose({
    load_data,
    get_items,
})
</script>
<style scoped>
.panel-column {
    display: inline;
}
</style>
