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
                    <td :rowspan="4">{{ idx + 1 }}</td>
                    <td :rowspan="4">{{ colour.split("@")[0] }}</td>
                    <td :rowspan="4" v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                    <td>Cutting Qty</td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size]['cutting'] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total']['cutting'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Delivered</td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size]['delivered'] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total']['delivered'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Received</td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size]['received'] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total']['received'] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>Difference</td>
                    <td v-for="size in items.primary_values" :key="size" 
                        :style="get_style(items['data']['data'][colour]['values'][size]['difference'] ?? 0)">
                        {{
                             items['data']['data'][colour]['values'][size]['difference'] ?? 0
                        }}
                    </td>
                    <td :style="get_style(items['data']['data'][colour]['colour_total']['difference'] ?? 0)">
                        <strong>{{ items['data']['data'][colour]['colour_total']['difference'] ?? 0 }}</strong>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>

import { ref } from 'vue';

let items = ref(null)

function load_data(data){
    items.value = data
}

function get_difference(qty1, qty2){
    return qty1 - qty2
}

function get_style(val){
    if(val < 0){
        return {"background":"#f57f87"};
    }
    else if(val > 0){
        return {"background":"#98ebae"}
    }
    return {"background":"#67b0b8"};
}


defineExpose({
    load_data
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