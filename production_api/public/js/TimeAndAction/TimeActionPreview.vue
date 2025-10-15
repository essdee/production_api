<template>
    <div ref="root" v-if="Object.keys(items).length > 0">
        <div v-for="item in Object.keys(items)" :key="item">
            <div v-if='items[item].length > 0'>
                <h4 style="line-height:1;">{{item}}</h4>
                <div class="scroll-container2">
                    <table class="inner-table" style="margin-bottom: 20px;">
                        <thead>
                            <tr>
                                <th class="sticky-col col1">Colour</th>
                                <th class="sticky-col col2">Start Date</th>
                                <th class="sticky-col col3">Dispatch Date</th>
                                <th class="sticky-col col4">Activity</th>
                                <th v-for="(value,index) in items[item]">{{ value.action }}</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td class="sticky-col col1" rowspan="4">{{ item }}</td>
                                <td class="sticky-col col2" rowspan="4">{{ date_format(start) }}</td>
                                <td class="sticky-col col3" rowspan="4">{{ date_format(items[item][items[item].length - 1]['date']) }}</td>
                            </tr>
                            <tr>
                                <td class="sticky-col col4">Lead Time</td>
                                <td v-for="(value,index) in items[item]">
                                    {{ value.lead_time }}
                                </td>
                            </tr>
                            <tr>
                                <td class="sticky-col col4">Department</td>
                                <td v-for="(value,index) in items[item]">
                                    {{ value.department }}
                                </td>
                            </tr>
                            <tr>
                                <td class="sticky-col col4">Completion Date</td>
                                <td v-for="(value,index) in items[item]">
                                    {{ date_format(value.date) }}
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>    
            </div>
        </div>
    </div>
</template>
<script setup>
import {ref} from 'vue';

let items = ref({})
let start = ref(null)
function load_data(item, start_date){
    items.value = item
    start.value = start_date
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

<style scoped>

.scroll-container2 {
    width: 100%;
    max-height: 700px;
    overflow: auto;
    position: relative;
}

.sticky-col {
    border: 1px solid black;
    position: sticky;
    background: white;
    z-index: 1;
    border-right: 1px solid black;
    box-shadow: 2px 0 5px -2px black;
}

.inner-table thead {
    position: sticky;
    top: 0;
    z-index: 5;
    background: white; 
}

.inner-table {
    min-width: 3200px;
}

.inner-table thead th.sticky-col {
  position: sticky;
  top: 0;
  z-index: 5;
  background: white;
}

.inner-table th, .inner-table td, .inner-table thead, .inner-table tbody{
    text-align: center;
    word-wrap: break-word; 
    border: 1px solid black;
}

.inner-table tbody tr:nth-child(odd) td {
  background-color: #f9f9f9; /* light gray */
}

.inner-table tbody tr:nth-child(even) td {
  background-color: #ffffff; /* white */
}

.inner-table tr{
    border: 1px solid black;
}

.inner-table th{
    background-color: #D3D3D3;
}

.col1 { left: 0;     box-shadow: inset 0 0 0 0.05rem black; width: 60px;}
.col2 { left: 60px;  box-shadow: inset 0 0 0 0.05rem black; width: 120px;}
.col3 { left: 180px; box-shadow: inset 0 0 0 0.05rem black; width: 120px;}
.col4 { left: 300px; box-shadow: inset 0 0 0 0.05rem black; width: 100px;}

</style>