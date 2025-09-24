<template>
    <div>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:20px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                </tr>
            </thead>
            <tbody class="dark-border" v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                <tr>
                    <td>{{ idx + 1 }}</td>
                    <td>{{ colour.split("@")[0] }}</td>
                    <td v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                    <td v-for="size in items.primary_values" :key="size">
                        <input type="number" class="form-control"
                            v-model="items['data']['data'][colour]['values'][size]['pack_return']"/>
                    </td>
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

let items = ref(props.data);

function getData() {
    return items.value
}

defineExpose({
    getData
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