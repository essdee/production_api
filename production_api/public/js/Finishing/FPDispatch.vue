<template>
    <div ref="root">
        <table class="table table-sm table-sm-bordered bordered-table" >
            <thead class="dark-border">
                <tr>
                    <th>Size</th>
                    <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr>
                    <td>Packed</td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        {{ packed_qty[value]['packed']}}
                    </td>
                    <td>{{ props.packed }}</td>
                </tr>
                <tr>
                    <td>
                        Balance
                    </td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        {{ packed_qty[value]['packed'] - packed_qty[value]['dispatched']}}
                    </td>
                    <td>{{ props.packed - props.dispatched }}</td>
                </tr>
                <tr>
                    <td>
                        Dispatch Qty
                    </td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        <input type="number" v-model="packed_qty[value]['cur_dispatch']" class="form-control" 
                        />
                    </td>
                    <td>{{ dispatch_total }}</td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import {ref, watch, computed} from 'vue';

const root = ref(null);
const primary_values = ref([])
let packed_qty = ref({})
const props = defineProps(['packed_qty', 'primary_values', 'packed', 'dispatched'])

watch(() => props.packed_qty, (packed) => {
    packed_qty.value = packed
},{ immediate: true })

watch(()=> props.primary_values, (primary) => {
    primary_values.value = primary
}, {immediate: true})

const dispatch_total = computed(() => {
    if (!primary_values.value.length) return 0;
    return primary_values.value.reduce((sum, size) => {
        let val = Number(packed_qty.value[size]?.cur_dispatch || 0);
        return sum + val;
    }, 0);
});

defineExpose({
    packed_qty
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