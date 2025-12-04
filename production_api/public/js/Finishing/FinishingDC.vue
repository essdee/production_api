<template>
    <div>
        <div style="display: flex; width: 100%;">
            <div style="width: 25%;">
                <label>Choose Type:</label>
                <select v-model="selected_type" @change="fill_quantity()" class="form-control" >
                    <option value="balance">Balance</option>
                    <option value="return_qty">Loose Piece</option>
                    <option value="pack_return">Loose Piece Packed</option>
                </select>
            </div>
            <div style="width: 30%; margin-top: 28px;margin-left: 10px;">
                <button @click="fill_quantity()" class="btn btn-success">Fill</button>
            </div>
        </div>
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
                    <td v-if="selected_type == 'balance'">
                        Balance Qty
                    </td>
                    <td v-else-if="selected_type == 'return_qty'">
                        Loose Piece Qty
                    </td>
                    <td v-else>
                        Packed Piece Qty
                    </td>
                    <td v-for="size in items.primary_values" :key="size">
                        {{
                            items['data']['data'][colour]["values"][size][selected_type] ?? 0
                        }}
                    </td>
                    <td><strong>{{ items['data']['data'][colour]['colour_total'][selected_type] ?? 0 }}</strong></td>
                </tr>
                <tr>
                    <td>DC Qty</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <div v-if="items['data']['data'][colour]['check_value']">
                            <input type="number" v-model="items['data']['data'][colour]['values'][size]['balance_dc']"
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

const props = defineProps({
    data: Object
});
let selected_type = ref('balance')
let items = ref(props.data);

function getData() {
    return {
        "items": items.value,
        "selected_type": selected_type.value,
    }
}

function update_qty(){
    Object.keys(items.value.data.data).forEach((colour)=> {
        items.value.data.data[colour]['colour_total']['balance_dc'] = 0
        Object.keys(items.value.data.data[colour]['values']).forEach((size)=> {
            items.value.data.data[colour]['values'][size]['balance_dc'] = 0
        })
    })
}

function fill_quantity(){
    Object.keys(items.value.data.data).forEach((colour)=> {
        items.value.data.data[colour]['colour_total']['balance_dc'] = items.value.data.data[colour]['colour_total'][selected_type.value]
        Object.keys(items.value.data.data[colour]['values']).forEach((size)=> {
            items.value.data.data[colour]['values'][size]['balance_dc'] = items.value.data.data[colour]['values'][size][selected_type.value]
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