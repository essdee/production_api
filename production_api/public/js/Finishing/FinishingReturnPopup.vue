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
                </tr>
            </thead>
            <tbody class="dark-border" v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                <tr>
                    <td :rowspan="2">{{ idx + 1 }}</td>
                    <td :rowspan="2">{{ colour.split("@")[0] }}</td>
                    <td :rowspan="2" v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                    <td v-if="is_loose_piece">Balance Qty</td>
                    <td v-else>Delivered</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <span v-if="is_loose_piece">
                            {{
                                items['data']['data'][colour]["values"][size]['balance'] ?? 0
                            }}
                        </span>
                        <span v-else>
                            {{
                                items['data']['data'][colour]["values"][size]['dc_qty'] ?? 0
                            }}
                        </span>
                    </td>
                </tr>
                <tr>
                    <td v-if="is_loose_piece">Quantity</td>
                    <td v-else>Quantity</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <input type="number" class="form-control" v-model="items['data']['data'][colour]['values'][size]['return_qty']" />
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>

import { ref } from 'vue';

const props = defineProps({
    data: Object,
    loose_piece: Boolean,
});

let items = ref(props.data);
let is_loose_piece = ref(props.loose_piece)

function getData() {
    return items.value
}

function update_qty(){
    Object.keys(items.value.data.data).forEach((colour)=> {
        items.value.data.data[colour]['colour_total']['return_qty'] = 0
        Object.keys(items.value.data.data[colour]['values']).forEach((size)=> {
            items.value.data.data[colour]['values'][size]['return_qty'] = 0
        })
    })
}

defineExpose({
    getData,
    update_qty
});


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