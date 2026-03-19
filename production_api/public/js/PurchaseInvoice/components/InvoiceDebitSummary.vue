<template>
    <div v-if="debits.length > 0">
        <h4>WO Debit Summary</h4>
        <table class="table table-sm table-sm-bordered bordered-table">
            <thead>
                <tr>
                    <th>Work Order</th>
                    <th>WO Debit Name</th>
                    <th>Debit No</th>
                    <th>Debit Value</th>
                    <th>Reason</th>
                    <th>On Close</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="d in debits" :key="d.name">
                    <td style="cursor: pointer; color: #2490EF;" @click="openLink('work-order', d.work_order)">{{ d.work_order }}</td>
                    <td style="cursor: pointer; color: #2490EF;" @click="openLink('wo-debit', d.name)">{{ d.name }}</td>
                    <td>{{ d.debit_no }}</td>
                    <td>{{ fmt_currency(d.debit_value) }}</td>
                    <td>{{ d.reason }}</td>
                    <td>{{ d.on_close ? '✔' : '' }}</td>
                </tr>
                <tr>
                    <th colspan="3" style="text-align: right;">Total</th>
                    <th>{{ fmt_currency(total_value) }}</th>
                    <th></th>
                    <th></th>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';

let debits = ref([]);

const total_value = computed(() => {
    return debits.value.reduce((sum, d) => sum + flt(d.debit_value), 0);
});

function load_data(data) {
    debits.value = data || [];
}

function fmt_currency(val) {
    return window.format_currency ? window.format_currency(val) : val;
}

function openLink(doctype, name) {
    window.open(`/app/${doctype}/${name}`, '_blank');
}

defineExpose({ load_data });
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
</style>
