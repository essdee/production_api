<template>
    <div class="io-input-pending-tab">
        <div v-if="rows.length || searchText" class="report-toolbar">
            <div class="report-heading">
                <span class="eyebrow">Line and lot wise</span>
                <h2>I/O Input Pending</h2>
                <p>{{ inputType }} minus {{ outputType }}</p>
            </div>
            <div class="filter-controls">
                <label class="work-station-filter">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M7 12h10m-7 6h4" />
                    </svg>
                    <select v-model="selectedWorkStation">
                        <option value="">All Work Stations</option>
                        <option v-for="workStation in workStationOptions" :key="workStation" :value="workStation">
                            {{ workStation }}
                        </option>
                    </select>
                </label>
                <label class="search-box">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m21 21-4.35-4.35m1.35-5.65a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z" />
                    </svg>
                    <input v-model.trim="searchText" type="search" placeholder="Search lot or item">
                </label>
            </div>
        </div>

        <div v-if="rows.length" class="summary-grid">
            <article class="summary-card input-card">
                <span>Total Input Qty</span>
                <strong>{{ formatNumber(displayTotals.input_qty) }}</strong>
            </article>
            <article class="summary-card output-card">
                <span>Total Line Output</span>
                <strong>{{ formatNumber(displayTotals.line_output_qty) }}</strong>
            </article>
            <article class="summary-card pending-card">
                <span>Total Input Pending</span>
                <strong>{{ formatNumber(displayTotals.input_pending) }}</strong>
            </article>
        </div>

        <div v-if="loading" class="state-panel">
            <span class="loader"></span>
            <p>Loading input and output quantities...</p>
        </div>

        <div v-else-if="filteredRows.length" class="table-card">
            <div class="table-scroll">
                <table>
                    <thead>
                        <tr>
                            <th class="index-column">#</th>
                            <th>Sewing Line</th>
                            <th>Lot</th>
                            <th class="item-column">Item</th>
                            <th class="number-column">Input Qty</th>
                            <th class="number-column">Line Output Qty</th>
                            <th class="number-column">Input Pending</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(row, index) in filteredRows" :key="`${row.sewing_line}-${row.lot}-${row.item}`">
                            <td class="index-cell">{{ index + 1 }}</td>
                            <td><span class="line-pill">{{ row.sewing_line }}</span></td>
                            <td>
                                <button class="lot-link" type="button" @click="openLot(row.lot)">
                                    {{ row.lot }}
                                </button>
                            </td>
                            <td class="item-cell">{{ row.item }}</td>
                            <td class="numeric-cell input-value">{{ formatNumber(row.input_qty) }}</td>
                            <td class="numeric-cell output-value">{{ formatNumber(row.line_output_qty) }}</td>
                            <td class="numeric-cell">
                                <span class="pending-value" :class="pendingClass(row.input_pending)">
                                    {{ formatNumber(row.input_pending) }}
                                </span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div class="row-count">Showing {{ filteredRows.length }} of {{ rows.length }} line-lot rows</div>
        </div>

        <div v-else class="state-panel">
            <div class="empty-icon">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M4 7h16M4 12h16M4 17h10" />
                </svg>
            </div>
            <p>{{ searchText ? 'No matching line, lot or item found' : 'No input or line output data for this Warehouse' }}</p>
        </div>
    </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
    selected_supplier: {
        type: String,
        default: null
    },
    refresh_counter: {
        type: Number,
        default: 0
    }
})

const rows = ref([])
const inputType = ref('Input Qty')
const outputType = ref('Line Output')
const selectedWorkStation = ref('')
const searchText = ref('')
const loading = ref(false)

const workStationOptions = computed(() => {
    return [...new Set(rows.value.map((row) => row.sewing_line).filter(Boolean))].sort()
})

const filteredRows = computed(() => {
    const search = searchText.value.toLowerCase()
    return rows.value.filter((row) => {
        if (selectedWorkStation.value && row.sewing_line !== selectedWorkStation.value) {
            return false
        }
        if (!search) return true
        return [row.sewing_line, row.lot, row.item]
            .some((value) => String(value || '').toLowerCase().includes(search))
    })
})

const displayTotals = computed(() => {
    return filteredRows.value.reduce((result, row) => {
        result.input_qty += Number(row.input_qty || 0)
        result.line_output_qty += Number(row.line_output_qty || 0)
        result.input_pending += Number(row.input_pending || 0)
        return result
    }, { input_qty: 0, line_output_qty: 0, input_pending: 0 })
})

const formatNumber = (value) => {
    return new Intl.NumberFormat().format(Number(value || 0))
}

const pendingClass = (value) => {
    if (value > 0) return 'is-pending'
    if (value < 0) return 'is-excess'
    return 'is-clear'
}

const openLot = (lot) => {
    if (lot) frappe.set_route('Form', 'Lot', lot)
}

const clearData = () => {
    rows.value = []
    selectedWorkStation.value = ''
    searchText.value = ''
}

const fetchData = () => {
    if (!props.selected_supplier) {
        clearData()
        return
    }

    clearData()
    loading.value = true
    frappe.call({
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_io_input_pending_data',
        args: { supplier: props.selected_supplier },
        callback: (response) => {
            const data = response.message || {}
            rows.value = data.rows || []
            inputType.value = data.input_type || 'Input Qty'
            outputType.value = data.output_type || 'Line Output'
            loading.value = false
        },
        error: () => {
            clearData()
            loading.value = false
        }
    })
}

watch(() => [props.selected_supplier, props.refresh_counter], fetchData, { immediate: true })
</script>

<style scoped>
.io-input-pending-tab {
    padding: 1rem 0;
}

.report-toolbar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1.5rem;
    margin-bottom: 1.25rem;
}

.report-heading h2 {
    margin: 0.15rem 0 0.2rem;
    color: #0f172a;
    font-size: 1.25rem;
    font-weight: 700;
}

.report-heading p,
.eyebrow {
    margin: 0;
    color: #64748b;
    font-size: 0.78rem;
}

.eyebrow {
    color: #2563eb;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.search-box {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    width: min(360px, 100%);
    padding: 0.65rem 0.85rem;
    margin: 0;
    border: 1px solid #e2e8f0;
    border-radius: 0.8rem;
    background: #f8fafc;
}

.filter-controls {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.75rem;
    width: min(690px, 100%);
}

.work-station-filter {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    width: min(260px, 100%);
    padding: 0.58rem 0.85rem;
    margin: 0;
    border: 1px solid #e2e8f0;
    border-radius: 0.8rem;
    background: #f8fafc;
}

.work-station-filter svg {
    width: 1rem;
    flex: 0 0 auto;
    color: #94a3b8;
}

.work-station-filter select {
    width: 100%;
    padding: 0;
    border: 0;
    outline: 0;
    background: transparent;
    color: #334155;
    font-size: 0.85rem;
    font-weight: 500;
}

.search-box svg {
    width: 1rem;
    color: #94a3b8;
}

.search-box input {
    width: 100%;
    padding: 0;
    border: 0;
    outline: 0;
    background: transparent;
    color: #0f172a;
    font-size: 0.85rem;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    margin-bottom: 1.25rem;
}

.summary-card {
    position: relative;
    overflow: hidden;
    padding: 1.15rem 1.25rem;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    background: #fff;
}

.summary-card::before {
    position: absolute;
    inset: 0 auto 0 0;
    width: 4px;
    content: '';
}

.input-card::before { background: #2563eb; }
.output-card::before { background: #16a34a; }
.pending-card::before { background: #f59e0b; }

.summary-card span {
    display: block;
    margin-bottom: 0.35rem;
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.summary-card strong {
    color: #0f172a;
    font-size: 1.65rem;
    font-variant-numeric: tabular-nums;
}

.table-card {
    overflow: hidden;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    background: #fff;
}

.table-scroll {
    max-height: 65vh;
    overflow: auto;
}

table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
}

th {
    position: sticky;
    top: 0;
    z-index: 2;
    padding: 0.85rem 1rem;
    border-bottom: 1px solid #cbd5e1;
    background: #f8fafc;
    color: #475569;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.035em;
    text-align: left;
    text-transform: uppercase;
    white-space: nowrap;
}

td {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #edf2f7;
    color: #334155;
    font-size: 0.84rem;
}

tbody tr:hover td {
    background: #f8fafc;
}

tbody tr:last-child td {
    border-bottom: 0;
}

.index-column,
.index-cell {
    width: 48px;
    color: #94a3b8;
    text-align: center;
}

.item-column {
    width: 32%;
}

.item-cell {
    min-width: 220px;
    color: #0f172a;
    font-weight: 500;
}

.number-column,
.numeric-cell {
    text-align: right;
}

.numeric-cell {
    color: #0f172a;
    font-size: 0.9rem;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    white-space: nowrap;
}

.input-value { color: #1d4ed8; }
.output-value { color: #15803d; }

.line-pill {
    display: inline-flex;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    background: #f1f5f9;
    color: #334155;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
}

.lot-link {
    padding: 0;
    border: 0;
    background: transparent;
    color: #2563eb;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
}

.lot-link:hover {
    text-decoration: underline;
}

.pending-value {
    display: inline-flex;
    min-width: 74px;
    justify-content: flex-end;
    padding: 0.28rem 0.55rem;
    border-radius: 0.45rem;
}

.is-pending { background: #fff7ed; color: #c2410c; }
.is-clear { background: #f0fdf4; color: #15803d; }
.is-excess { background: #eff6ff; color: #1d4ed8; }

.row-count {
    padding: 0.65rem 1rem;
    border-top: 1px solid #e2e8f0;
    background: #f8fafc;
    color: #64748b;
    font-size: 0.75rem;
    text-align: right;
}

.state-panel {
    display: flex;
    min-height: 300px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.8rem;
    color: #94a3b8;
}

.state-panel p {
    margin: 0;
    font-size: 0.86rem;
}

.empty-icon {
    display: grid;
    width: 3.5rem;
    height: 3.5rem;
    place-items: center;
    border-radius: 1rem;
    background: #f8fafc;
}

.empty-icon svg {
    width: 1.7rem;
}

.loader {
    width: 1.6rem;
    height: 1.6rem;
    border: 2px solid #e2e8f0;
    border-top-color: #2563eb;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
    .report-toolbar {
        align-items: stretch;
        flex-direction: column;
    }

    .search-box {
        width: 100%;
    }

    .filter-controls {
        align-items: stretch;
        flex-direction: column;
        width: 100%;
    }

    .work-station-filter {
        width: 100%;
    }

    .summary-grid {
        grid-template-columns: 1fr;
    }
}
</style>
