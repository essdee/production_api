<template>
    <div>
        <div class="header-row">
            <h3 style="margin:0;">Rejection Details</h3>
            <div v-if="receivedTypeOptions.length" class="filter-wrap">
                <label for="rejection-received-type-filter">Received Type:</label>
                <select
                    id="rejection-received-type-filter"
                    class="form-control input-sm filter-select"
                    v-model="selectedType"
                >
                    <option value="">All</option>
                    <option
                        v-for="rt in receivedTypeOptions"
                        :key="rt"
                        :value="rt"
                    >{{ rt }}</option>
                </select>
            </div>
        </div>
        <div v-if="summaryRows.length" class="summary-wrap">
            <table class="table table-sm bordered-table summary-table">
                <thead class="dark-border">
                    <tr>
                        <th>Received Type</th>
                        <th>Rework Qty</th>
                        <th>Rejection Qty</th>
                    </tr>
                </thead>
                <tbody class="dark-border">
                    <tr v-for="row in summaryRows" :key="row.received_type">
                        <td><strong>{{ row.received_type }}</strong></td>
                        <td>{{ row.rework }}</td>
                        <td>{{ row.rejection }}</td>
                    </tr>
                </tbody>
                <tfoot class="dark-border">
                    <tr>
                        <td><strong>Grand Total</strong></td>
                        <td><strong>{{ summaryGrand.rework }}</strong></td>
                        <td><strong>{{ summaryGrand.rejection }}</strong></td>
                    </tr>
                </tfoot>
            </table>
        </div>
        <div v-if="!hasData" class="no-data">
            No rejection data
        </div>
        <table v-else class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th style="width:150px;">Received Type</th>
                    <th style="width:180px;">Colour</th>
                    <th v-if="items.is_set_item" style="width:80px;">{{ items.set_attr }}</th>
                    <th style="width:130px;">Type</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <template v-for="(rtBlock, rtName) in filteredData" :key="rtName">
                    <template
                        v-for="(colourBlock, colour, cIdx) in rtBlock"
                        :key="rtName + '__' + colour"
                    >
                        <tr>
                            <td
                                v-if="cIdx === 0"
                                :rowspan="Object.keys(rtBlock).length * 2"
                            >
                                <strong>{{ rtName }}</strong>
                            </td>
                            <td :rowspan="2">{{ colour.split('@')[0] }}</td>
                            <td v-if="items.is_set_item" :rowspan="2">{{ colourBlock.part }}</td>
                            <td>Rework Qty</td>
                            <td v-for="size in items.primary_values" :key="size">
                                {{ colourBlock.rework.values[size] ?? 0 }}
                            </td>
                            <td><strong>{{ colourBlock.rework.total ?? 0 }}</strong></td>
                        </tr>
                        <tr>
                            <td>Rejection Qty</td>
                            <td v-for="size in items.primary_values" :key="size">
                                {{ colourBlock.rejection.values[size] ?? 0 }}
                            </td>
                            <td><strong>{{ colourBlock.rejection.total ?? 0 }}</strong></td>
                        </tr>
                    </template>
                </template>
            </tbody>
            <tfoot class="dark-border">
                <tr>
                    <td :colspan="footerLabelSpan" style="text-align:right;">
                        <strong>Total Rejection</strong>
                    </td>
                    <td><strong>{{ filteredRejectionTotal }}</strong></td>
                </tr>
            </tfoot>
        </table>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';

let items = ref(null)
let selectedType = ref("")

const receivedTypeOptions = computed(() => {
    if (!items.value || !items.value.data) return []
    return Object.keys(items.value.data)
})

const filteredData = computed(() => {
    if (!items.value || !items.value.data) return {}
    if (!selectedType.value) return items.value.data
    const picked = items.value.data[selectedType.value]
    return picked ? { [selectedType.value]: picked } : {}
})

const hasData = computed(() => {
    return Object.keys(filteredData.value).length > 0
})

const filteredRejectionTotal = computed(() => {
    let total = 0
    Object.values(filteredData.value).forEach(rt => {
        Object.values(rt).forEach(col => {
            total += (col.rejection && col.rejection.total) || 0
        })
    })
    return total
})

const summaryRows = computed(() => {
    if (!items.value || !items.value.data) return []
    const rows = []
    Object.entries(items.value.data).forEach(([rtName, rtBlock]) => {
        let rework = 0
        let rejection = 0
        Object.values(rtBlock).forEach(col => {
            rework += (col.rework && col.rework.total) || 0
            rejection += (col.rejection && col.rejection.total) || 0
        })
        rows.push({
            received_type: rtName,
            rework,
            rejection,
            total: rework + rejection,
        })
    })
    return rows
})

const summaryGrand = computed(() => {
    const g = { rework: 0, rejection: 0, total: 0 }
    summaryRows.value.forEach(r => {
        g.rework += r.rework
        g.rejection += r.rejection
        g.total += r.total
    })
    return g
})

const footerLabelSpan = computed(() => {
    if (!items.value) return 1
    let base = 3 + (items.value.primary_values ? items.value.primary_values.length : 0)
    if (items.value.is_set_item) base += 1
    return base
})

function load_data(data) {
    items.value = data
}

defineExpose({
    load_data,
})
</script>

<style scoped>
.header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    flex-wrap: wrap;
    gap: 12px;
}

.filter-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
}

.filter-wrap label {
    margin: 0;
    font-weight: 600;
}

.filter-select {
    min-width: 200px;
}

.summary-wrap {
    margin-bottom: 18px;
}

.summary-table {
    width: auto;
    min-width: 420px;
}

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

.dark-border {
    border: 2px solid black;
}

.no-data {
    padding: 20px;
    color: #888;
    font-style: italic;
}
</style>
