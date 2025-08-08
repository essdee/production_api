<template>
    <div ref="root" v-if="Object.keys(items).length > 0">
        <div v-for="item in Object.keys(items)" :key="item">
            <div v-if='items[item].length > 0'>
                <h4 style="line-height:0;">{{item}}</h4>
                <table class="table table-sm table-bordered">
                    <tr>
                        <th style="width:30%;">Action</th>
                        <th style="width:70%;">Work Station Details</th>
                    </tr>
                    <tr v-for="(value,index) in items[item]" :key="index">
                        <template v-if="value.work_station && value.completed == 0">
                            <td>{{value.action}}</td>
                            <td>
                                <table style="width:100%;">
                                    <tr>
                                        <th style="width:30%;">Work Station</th>
                                        <th style="width:70%;">Update Days</th>
                                    </tr>
                                    <tr v-for="(row, idx) in value.work_station" :key="row">
                                        <td>{{ row['work_station'] }}</td>
                                        <td>
                                            <div v-if="row['allocated_days'].length > 0">
                                                <table style="width:100%;">
                                                    <tr>
                                                        <th>Date</th>
                                                        <th>Target</th>
                                                        <th>Capacity</th>
                                                        <th></th>
                                                    </tr>
                                                    <tr v-for="(d, idx2) in row['allocated_days']">
                                                        <td>
                                                            <VueDatePicker v-model="d['allocated']" format="dd-MM-yyyy"
                                                                :disabled-dates="get_disabled_dates(row['work_station'])"
                                                                @update:model-value="(val) => onDateChange(val, item, index, idx, idx2)"
                                                                :input-class="'custom-input'">
                                                                <template #day="{ day, date }">
                                                                    <div @mouseenter="showTooltip($event, date, item, index, idx, idx2, row['work_station'])"
                                                                        @mouseleave="hideTooltip" @mousemove="updateTooltipPosition">
                                                                        {{ day }}
                                                                    </div>
                                                                </template>
                                                            </VueDatePicker>
                                                            <div v-if="is_to_show_tooltip(item, index, idx, idx2)"
                                                                :style="{
                                                                    position: 'fixed',
                                                                    top: tooltip.y + 'px',
                                                                    left: tooltip.x + 'px',
                                                                    background: '#333',
                                                                    color: '#fff',
                                                                    padding: '4px 8px',
                                                                    borderRadius: '4px',
                                                                    fontSize: '12px',
                                                                    pointerEvents: 'none',
                                                                    whiteSpace: 'nowrap',
                                                                    zIndex: 999999
                                                                }"
                                                            >
                                                                <div v-html="tooltip.text"></div>
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <input type="number" class="form-control" v-model="d['target']" step="0.01"/>
                                                        </td>
                                                        <td>
                                                            <input type="number" class="form-control" v-model="d['capacity']" step="0.01" @blur="update_capacity(d['capacity'], item, index, idx, idx2)"/>
                                                        </td>
                                                        <td>
                                                            <div class="pull-left cursor-pointer" 
                                                                @click="delete_item(item, index, idx, idx2)" 
                                                                v-html="frappe.utils.icon('delete', 'md')"
                                                            ></div>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </div>
                                            <div style="padding-top:15px;">
                                                <div>
                                                    <button class="btn btn-primary" @click="update_days(index, item, idx)">Update Date</button>
                                                </div>
                                            </div>
                                        </td>    
                                    </tr>
                                </table>
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
import VueDatePicker from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css'

let items = ref({})
let ws_allocated_dates = ref({})
let ws_date_wise_allocated = ref({})
let duplicate_value = ref({})
let tooltip = ref({
    visible: false,
    text: '',
    colour: null,
    index: null,
    idx: null,
    idx2: null,
    x: null,
    y: null,
});

onMounted(()=> {
    frappe.call({
        method: "production_api.essdee_production.doctype.lot.lot.get_allocated_ws_details",
        callback: function(r){
            ws_allocated_dates.value = r.message.total_allocated
            ws_date_wise_allocated.value = r.message.date_wise_allocated
        }
    })
})

function load_data(data){
    frappe.call({
        method: "production_api.essdee_production.doctype.lot.lot.get_allocated_days",
        args: {
            "t_and_a_data": data,
        },
        callback: function(r){
            items.value = r.message
            duplicate_value.value = JSON.stringify(r.message.data)
        }
    })
}

function get_disabled_dates(ws){
    let dates = []
    Object.keys(ws_allocated_dates.value[ws]).forEach((date)=> {
        if(ws_allocated_dates.value[ws][date] == 100){
            dates.push(date)
        }
    })
    return dates
}

function showTooltip(date, event, colour, index, idx, idx2, ws) {
    let d = formatDate(event)
    let text = ws_date_wise_allocated.value[ws][d.toString()];
    let return_text = ``
    if(!text){
        return_text = "<div>No Allocation</div>"
    }
    else{
        return_text += `<div>
                    <table>
                        <tr>
                            <th>Time and Action</th>
                            <th>Capacity</th>
                        </tr>        
                `
        Object.keys(text).forEach((t_and_a)=> {
            return_text += `
                <tr>
                    <td>${t_and_a}</td>
                    <td>${text[t_and_a]}</td>
                </tr>    
            ` 
        })
        return_text += `</table>
            </div>
        `    
    }
    tooltip.value.text = return_text
    tooltip.value.visible = true;
    tooltip.value.colour = colour;
    tooltip.value.index = index;
    tooltip.value.idx = idx;
    tooltip.value.idx2 = idx2;
    tooltip.value.x = event.clientX + 10;
    tooltip.value.y = event.clientY + 10;
}

function updateTooltipPosition(event) {
    tooltip.value.x = event.clientX + 10;
    tooltip.value.y = event.clientY + 10;
}

function hideTooltip() {
    tooltip.value.visible = false;
}
  
function is_to_show_tooltip(colour, index, idx, idx2) {
    return (
        tooltip.value.visible && 
        tooltip.value.colour == colour && 
        tooltip.value.index == index && 
        tooltip.value.idx == idx && 
        tooltip.value.idx2 == idx2
    );    
}
function formatDate(date) {
    console.log(date)
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    if (isNaN(date)) {
        throw new Error("Invalid date provided");
    }

    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${year}-${month}-${day}`;
}

function onDateChange(value, colour, index, idx, idx2) {
    const day = String(value.getDate()).padStart(2, '0');
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const year = value.getFullYear();
    let date = `${year}-${month}-${day}`
    duplicate_value.value = JSON.parse(duplicate_value.value)
    let previous_date = duplicate_value.value[colour][index]['work_station'][idx]['allocated_days'][idx2]['allocated']
    let previous_allocated = duplicate_value.value[colour][index]['work_station'][idx]['allocated_days'][idx2]['capacity']
    let work_station = items.value[colour][index]['work_station'][idx]['work_station']
    if(previous_date){
        ws_allocated_dates.value[work_station][previous_date] -= previous_allocated
    }
    let allocated = 0
    if(!ws_allocated_dates.value[work_station].hasOwnProperty(date)){
        allocated = 0
        ws_allocated_dates.value[work_station][date] = 0
    }
    else{
        allocated = ws_allocated_dates.value[work_station][date] 
    }
    items.value[colour][index]['work_station'][idx]['allocated_days'][idx2]['allocated'] = date 
    items.value[colour][index]['work_station'][idx]['allocated_days'][idx2]['capacity'] = (100 - allocated).toFixed(2)
    ws_allocated_dates.value[work_station][date] = 100
    items.value[colour][index]['work_station'][idx]['changed'] = true
    duplicate_value.value = JSON.stringify(items.value)
}


function update_days(index, colour, idx){
    items.value[colour][index]['work_station'][idx]['allocated_days'].push({
        "allocated": null,
        "target": 0,
        "capacity": 0,
    })
    items.value[colour][index]['work_station'][idx]['changed'] = true
    duplicate_value.value = JSON.stringify(items.value)
}

function delete_item(colour, index1, index2, index3){
    let p = items.value[colour][index1]['work_station'][index2]['allocated_days']
    let date = items.value[colour][index1]['work_station'][index2]['allocated_days'][index3]
    let ws = items.value[colour][index1]['work_station'][index2]['work_station']
    ws_allocated_dates.value[ws][date['allocated']] -= date['capacity']
    p.splice(index3, 1)
    items.value[colour][index1]['work_station'][index2]['allocated_days'] = p
    items.value[colour][index1]['work_station'][index2]['changed'] = true
    duplicate_value.value = JSON.stringify(items.value)
}

function get_data(){
    let v = {}
    Object.keys(items.value).forEach((colour) => {
        for(let i = 0; i < items.value[colour].length; i++){
            if(items.value[colour][i]['work_station']){
                for(let j = 0; j < items.value[colour][i]['work_station'].length; j++){
                    let ws = items.value[colour][i]['work_station'][j]['work_station']
                    if (!(ws in v)) {
                       v[ws] = {};
                    }
                    for(let k = 0; k < items.value[colour][i]['work_station'][j]['allocated_days'].length; k++){
                        let d = items.value[colour][i]['work_station'][j]['allocated_days'][k]['allocated']
                        let c = items.value[colour][i]['work_station'][j]['allocated_days'][k]['capacity']
                        if(!(d in v[ws])){
                            v[ws][d] = 100
                        }
                        v[ws][d] -= c
                        v[ws][d] = v[ws][d].toFixed(2);
                        if(v[ws][d] < 0){
                            frappe.throw(`Allocated more than 100% in ${ws} on ${d}`)
                        }
                    }
                }
            }
        }
    })
    return items.value
}

function update_capacity(capacity, colour, index, idx, idx2){
    duplicate_value.value = JSON.parse(duplicate_value.value)
    let ws = items.value[colour][index]['work_station'][idx]['work_station']
    let date = duplicate_value.value[colour][index]['work_station'][idx]['allocated_days'][idx2]['allocated']
    let previous_capacity = duplicate_value.value[colour][index]['work_station'][idx]['allocated_days'][idx2]['capacity']
    ws_allocated_dates.value[ws][date] -= previous_capacity
    ws_allocated_dates.value[ws][date] += capacity
    duplicate_value.value = JSON.stringify(items.value)
    items.value[colour][index]['work_station'][idx]['changed'] = true
}

defineExpose({
    load_data,
    get_data,
})
</script>

<style scoped>
.custom-input {
    height: 30px;
    padding: 4px 8px;
    font-size: 14px;
}
</style>