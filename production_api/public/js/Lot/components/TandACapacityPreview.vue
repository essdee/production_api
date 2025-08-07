<template>
    <div>
        <div v-if="items && Object.keys(items).length > 0">
            <div v-for="item in Object.keys(items)" :key="item">
                <h3 style="line-height:0;">{{item}}</h3>
                <table class="table table-sm table-bordered">
                    <tr>
                        <th>Action</th>
                        <th>Lead Time</th>
                        <th>Department</th>
                        <th>Planned Date</th>
                        <th>Rescheduled Date</th>
                        <th>Work Station Details</th>
                    </tr>
                    <tr v-for="(value,index) in items[item]['details']" :key="index">
                        <td>{{value.action}}</td>
                        <td>{{value.lead_time}}</td>
                        <td>{{value.department}}</td>
                        <td>{{date_format(value.date)}}</td>
                        <td>{{date_format(value.rescheduled_date)}}</td>
                        <td v-if="value.hasOwnProperty('work_station_details')">
                            <div v-for="ws in Object.keys(value.work_station_details)" style="padding-top:10px;">
                                <h4>{{ ws }}({{value.work_station_details[ws]['total_production']}})</h4>
                                <h5>Start Date: {{ date_format(value.work_station_details[ws]['start_date']) }}</h5>
                                <h5>End Date: {{ date_format(value.work_station_details[ws]['end_date']) }}</h5>
                                <button class="btn btn-secondary" @click="show_allocated_days(item, index, ws)">
                                    Click
                                </button>
                                <table v-if="value.work_station_details[ws]['show_allocated']">
                                    <tr>
                                        <th>Allocated Date</th>
                                        <th>Per Day Capacity</th>
                                    </tr>
                                    <tr v-for="(capacity, date) in value.work_station_details[ws]['allocated_days']">
                                        <td>{{ date_format(date) }}</td>
                                        <td>{{ capacity }}%</td>
                                    </tr>
                                </table>
                            </div>
                        </td>
                        <td v-else>
                            --
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup>

import {ref} from 'vue';

let items = ref({})

function load_data(data){
    items.value = data
}

function date_format(date){
    if(date){
        let arr = date.split("-")
        return arr[2]+"-"+arr[1]+"-"+arr[0]
    }
}

function show_allocated_days(colour, index, ws){
    let x = !items.value[colour]["details"][index]['work_station_details'][ws]['show_allocated']
    items.value[colour]["details"][index]['work_station_details'][ws]['show_allocated'] = x
}

defineExpose({
    load_data,
})

</script>