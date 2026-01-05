<template>
    <div>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:20px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th style="width:150px;">Type</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border" v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                <tr>
                    <td :rowspan="4">
                        {{ idx + 1 }}
                        <input type="checkbox" v-model="items['data']['data'][colour]['check_value']"/>
                    </td>
                    <td :rowspan="4">{{ colour.split("@")[0] }}</td>
                    <td :rowspan="4" v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                    <td> Qty </td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size]['balance'] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total']['balance'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Conversion Qty</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <div v-if="items['data']['data'][colour]['check_value']">
                            <input type="number" v-model="items['data']['data'][colour]['values'][size]['conversion_qty']"
                            class="form-control"/>
                        </div>
                        <div v-else>
                            0
                        </div>
                    </td>
                    <td></td>
                </tr>
            </tbody>
        </table>
    </div>    
</template>

<script setup>

import { ref } from 'vue';

let items = ref({})

function load_data(data) {
    Object.keys(data['data']['data']).forEach((colour)=> {
        Object.keys(data['data']['data'][colour]['values']).forEach((size)=> {
            console.log(data['data']['data'][colour]['values'][size])
            data['data']['data'][colour]['values'][size]['conversion_qty'] = 10
        })
    })
    items.value = data
}

function get_items(){
    return items.value
}

defineExpose({
    load_data,
    get_items
})
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
    padding: 6px 8px;
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}

.dark-border{
    border: 2px solid black;
}
</style>
