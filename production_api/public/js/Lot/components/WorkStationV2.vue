<template>
    <div ref="root" v-if="Object.keys(items).length > 0">
        <div v-for="item in Object.keys(items)" :key="item">
            <div v-if='items[item].length > 0'>
                <h4 style="line-height:0;">{{item}}</h4>
                <table class="table table-sm table-bordered">
                    <tr>
                        <th>Action</th>
                        <th>Master</th>
                        <th>Work Station Details</th>
                    </tr>
                    <tr v-for="(value,index) in items[item]" :key="index">
                        <template v-if="types == 'create' && value.work_station">
                            <td>{{value.action}}</td>
                            <td>{{value.master}}</td>
                            <td>
                                <table v-if='value.work_station.length > 0' style="width:100%;">
                                    <tr>
                                        <th style="width:40%;">Work Station</th>
                                        <th style="width:25%;">Target Per Day</th>
                                        <th style="width:25%;">Capacity</th>
                                        <td style="width:10%"></td>
                                    </tr>
                                    <tr v-for="(work_station, idx) in value.work_station" :key="work_station">
                                        <td>
                                            <select class="form-control" v-model="work_station.work_station">
                                                <option v-for="unit in work_stations[value.action]" :key="unit" :value="unit">
                                                    {{ unit }}
                                                </option>
                                            </select>
                                        </td>
                                        <td>
                                            <input class="form-control" type="number" v-model="work_station.target" />
                                        </td>
                                        <td>
                                            <input class="form-control" type="number" v-model="work_station.capacity" />    
                                        </td>   
                                        <td>
                                            <div class="pull-left cursor-pointer" @click="delete_work_station(item, index, idx)"
                                            v-html="icon"></div>
                                        </td>
                                    </tr>
                                </table>
                                <div class="btn-style">
                                    <button class="btn btn-info" @click="add_work_station(item, index)">Add Work Station</button>
                                </div>
                            </td>
                        </template>
                        <template v-else-if="types == 'update' && value.work_station">
                            <td>{{value.action}}</td>
                            <td>{{value.master}}</td>
                            <td>
                                <table v-if='value.work_station.length > 0' style="width:100%;">
                                    <tr>
                                        <th style="width:40%;">Work Station</th>
                                        <th style="width:25%;">Target Per Day</th>
                                        <th style="width:25%;">Capacity</th>
                                        <td style="width:10%"></td>
                                    </tr>
                                    <tr v-for="(work_station, idx) in value.work_station" :key="work_station">
                                        <td>
                                            <select class="form-control" v-model="work_station.work_station">
                                                <option v-for="unit in work_stations[value.action]" :key="unit" :value="unit">
                                                    {{ unit }}
                                                </option>
                                            </select>
                                        </td>
                                        <td>
                                            <input class="form-control" type="number" v-model="work_station.target" />
                                        </td>
                                        <td>
                                            <input class="form-control" type="number" v-model="work_station.capacity" />    
                                        </td>   
                                        <td>
                                            <div class="pull-left cursor-pointer" @click="delete_work_station(item, index, idx)"
                                            v-html="icon"></div>
                                        </td>
                                    </tr>
                                </table>
                                <div class="btn-style">
                                    <button class="btn btn-info" @click="add_work_station(item, index)">Add Work Station</button>
                                </div>
                            </td>
                        </template>
                    </tr>
                </table>
            </div>
        </div>
    </div>
</template>
<script setup>
import {ref, onMounted} from 'vue';

let root = ref(null)
let items = ref({})
let types = ref(null)
let work_stations = ref({})
let version = cur_frm.doc.version
function load_data(item, type){
    items.value = item
    types.value = type
}
const icon = frappe.utils.icon('delete', 'md')

onMounted(()=> {
    frappe.call({
        method: "production_api.essdee_production.doctype.lot.lot.fetch_work_stations",
        callback: function(r){
            work_stations.value = r.message
        }
    })
})

function add_work_station(colour, index){
    items.value[colour][index]['work_station'].push({
        "work_station": "",
        "target": 0,
        "capacity": 0,
    })
}

function delete_work_station(colour, index, index2){
    items.value[colour][index]['work_station'].splice(index2, 1)
}

function get_items(){
    let work_station_capacity = {}
    Object.keys(items.value).forEach(colour => {
        for(let i = 0; i < items.value[colour].length ; i++){
            let action = items.value[colour][i]['action']
            if(!items.value[colour][i]['work_station']){
                continue
            }
            if(items.value[colour][i]['work_station'].length == 0){
                frappe.throw(`Add Atleast One Work Station for ${action} ${colour}`)
            }
            for(let j = 0; j < items.value[colour][i]['work_station'].length; j++){
                let ws = items.value[colour][i]['work_station'][j]['work_station']
                let target = items.value[colour][i]['work_station'][j]['target']
                let capacity = items.value[colour][i]['work_station'][j]['capacity'] 
                if(!ws){
                    frappe.throw(`Select a Work station for ${action} ${colour}`)
                }
                if(!target || target == 0){
                    frappe.throw(`Target Should not be Zero for ${action} ${colour}`)
                }
                if(!capacity || capacity == 0){
                    frappe.throw(`Capacity Should not be Zero for ${action} ${colour}`)
                }
                if(capacity > 100){
                    frappe.throw(`Capacity Should not be greater than 100 for ${action} ${colour}`)
                }   
                if (work_station_capacity.hasOwnProperty(ws)){
                    work_station_capacity[ws] += capacity
                }
                else{
                    work_station_capacity[ws] = capacity 
                }
            }
        }
    })
    return items.value
}

defineExpose({
    load_data,
    get_items,
})
</script>
<style>
.form-group{
	margin-bottom:0 !important;
}

.btn-style{
    width: 100%;
    display: flex;
    justify-content: flex-end;
    padding: 5px;
}
</style>