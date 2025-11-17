<template>
    <div ref="root"> 
        <table class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>Size</th>
                    <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">    
                <tr>
                    <td>Quantity</td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        <input type="number" v-model="box_qty[value]" class="form-control" />
                    </td>
                    <td>{{ grn_total }}</td>
                </tr>
            </tbody>    
        </table>
    </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue';

const root = ref(null);
const primary_values = ref([])
let box_qty = ref({})

const props = defineProps(['primary_values', 'box_qty'])

watch(() => props.box_qty, (box) => {
    box_qty.value = box
},{ immediate: true })

watch(()=> props.primary_values, (primary) => {
    primary_values.value = primary
}, {immediate: true})

const grn_total = computed(() => {
    if (!primary_values.value.length) return 0;

    return primary_values.value.reduce((sum, size) => {
        let val = Number(box_qty.value[size] || 0);
        return sum + val;
    }, 0);
});

defineExpose({
    box_qty,
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