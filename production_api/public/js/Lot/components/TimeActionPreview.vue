<template>
    <div ref="root" v-if="Object.keys(items).length > 0">
        <div v-for="item in Object.keys(items)" :key="item">
            <div v-if='items[item].length > 0'>
                <h4 style="line-height:0;">{{item}}</h4>
                <table class="table table-sm table-bordered">
                    <tr>
                        <th>Action</th>
                        <th>Lead Time</th>
                        <th>Department</th>
                        <th>Planned Date</th>
                        <th>Rescheduled Date</th>
                    </tr>
                    <tr  v-for="(value,index) in items[item]" :key="index">
                       <td>{{value.action}}</td>
                       <td>{{value.lead_time}}</td>
                       <td>{{value.department}}</td>
                       <td>{{date_format(value.date)}}</td>
                       <td>{{value.rescheduled_date}}</td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
</template>
<script setup>
import {ref} from 'vue';

let items = ref({})
function load_data(item){
    items.value = item
}

function date_format(date){
    if(date){
        let arr = date.split("-")
        return arr[2]+"-"+arr[1]+"-"+arr[0]
    }
}

defineExpose({
    load_data,
})
</script>