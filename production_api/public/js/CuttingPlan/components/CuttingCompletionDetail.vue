<template>
    <div ref="root">
        <div v-if="items && pop_up == 1">
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
                            <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
                            <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                {{ j }}
                            </th>
                            <th v-if="i.is_set_item">Panels</th>
                            <th  v-if="pop_up == 1 || pop_up == 2">Completed</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{item1_index + 1}}</td>
                            <td v-for="(k, idx) in j.attributes" :key="idx">{{k}}</td>
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
                            <td v-if="pop_up == 1"><input type="checkbox" v-model="j['completed']" disabled></td>
                            <td v-else-if="pop_up == 2"><input type="checkbox" v-model="j['completed']"></td>
                        </tr>
                        <tr v-if="pop_up == 1">
                            <td>Total</td>
                            <td v-for="(j, idx) in i.final_state_attr" :key="idx"></td>
                            <td v-for="(j, idx) in i.total_qty" :key="idx">{{j}}</td>
                            <td></td>
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
                                <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
                                <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                    {{ j }}
                                </th>
                            </tr>
                            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                <td>{{item1_index + 1}}</td>
                                <td v-for="(k, idx) in j.attributes" :key="idx">{{k}}</td>
                                <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                    <div v-if="j.values[k] > 0">
                                        <div v-if="j['completed']">
                                            {{ j.values[k] }}
                                        </div>    
                                        <div v-else> -- </div>
                                    </div>
                                    <div v-else>--</div>
                                </td>
                            </tr>
                        </table>
                    </td>
                    <td v-else>
                        <template v-for="part in Object.keys(i.Panel)" :key="part">
                            <h3>{{part}}</h3>
                            <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                                <tr>
                                    <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
                                    <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                        {{ j }}
                                    </th>
                                </tr>
                                <template v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <tr v-if="check(j.attributes, part)">
                                        <td v-for="(k, idx) in j.attributes" :key="idx">{{k}}</td>
                                        <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                            <div v-if="j.values[k] > 0">
                                                <div v-if="j['completed']">
                                                    {{ j.values[k] }}
                                                </div>    
                                                <div v-else> -- </div>
                                            </div>
                                            <div v-else>--</div>
                                        </td>
                                    </tr>
                                </template>    
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
let lot = cur_frm.doc.lot
let item = cur_frm.doc.item
let datetime = ref(null)
let items2 = ref(null)

onMounted(()=> {
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

function load_data(item, is_pop_up){
    try {
        items.value = JSON.parse(item);
        items2.value = JSON.parse(item);
        pop_up.value = is_pop_up
    } catch(e) {
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
    display: inline; /* Display items in a single line */
}
</style>
