<template>
    <div>
        <h3 style="text-align: center;">Lot Transferred Items</h3>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:40px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <template v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                    <tr>
                        <td>{{ idx + 1 }}</td>
                        <td>{{ colour.split("@")[0] }}</td>
                        <td v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['data'][colour]["values"][size]['lot_transferred'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['data'][colour]['colour_total']['lot_transferred'] ?? 0 }}</strong></td>
                    </tr>
                </template>
                <tr>
                    <th></th>
                    <th>Total</th>
                    <th v-if="items.is_set_item"></th>
                    <th v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['total'][size]['lot_transferred'] ?? 0
                        }}
                    </th>
                    <th>{{ items['data']['total_qty']['lot_transferred'] }}</th>
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