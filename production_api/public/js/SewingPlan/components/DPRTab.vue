<template>
    <div class="dpr-tab">
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filter by Date</span>
                </div>
                <div class="filter-control">
                    <div ref="date_filter_wrapper"></div>
                </div>
                <div class="filter-control">
                     <div ref="ws_filter_wrapper"></div>
                </div>
                <div>
                     <button class="btn btn-primary" @click="fetchDPRData()" style="border-radius: 12px; font-weight: 700;">
                        Fetch
                    </button>
                </div>
            </div>
        </div>
        <div v-if="headers && headers.length > 0">
            <div v-for="header in headers">
                <div v-if="data.hasOwnProperty(header)">
                    <h3 class="plan-title" style="margin-bottom: 10px;">{{ header }}</h3>
                    <div class="table-wrapper no-scrollbar" style="margin-bottom: 20px;">
                        <table class="data-table" v-for="lot in Object.keys(data[header])">
                            <thead>
                                <tr class="header-row">
                                    <th class="sticky-col index-col">#</th>
                                    <th class="sticky-col colour-col">Lot</th>
                                    <th class="sticky-col colour-col">Item</th>
                                    <th class="sticky-col colour-col">Colour</th>
                                    <th v-if="data[header][lot]['is_set_item']" class="part-col">
                                        {{ data[header][lot]['set_attr'] }}
                                    </th>
                                    <th class="sticky-col colour-col">Line</th>
                                    <th class="sticky-col colour-col">Type</th>
                                    <th v-for="size in data[header][lot]['primary_values']" :key="size"
                                        class="size-col">
                                        {{ size }}
                                    </th>
                                    <th class="total-col">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template v-for="(ws, idx) in Object.keys(data[header][lot]['details'])"
                                    :key="ws">
                                    <template v-for="(received_type, idx) in Object.keys(data[header][lot]['details'][ws])"
                                        :key="received_type">
                                        <tr v-for="colour in Object.keys(data[header][lot]['details'][ws][received_type])" class="data-row">
                                            <td class="sticky-col index-cell">{{ idx + 1 }}</td>
                                            <td class="sticky-col colour-cell">{{ lot }}</td>
                                            <td class="sticky-col colour-cell">{{ data[header][lot]['item'] }}</td>
                                            <td class="sticky-col colour-cell">
                                                <span class="colour-badge">{{ colour.split("@")[0] }}</span>
                                            </td>
                                            <td v-if="data[header][lot]['is_set_item']" class="part-cell">
                                                <span class="part-pill">
                                                    {{ data[header][lot]['details'][ws][received_type][colour]['part']}}
                                                </span>
                                            </td>
                                            <td class="sticky-col colour-cell">{{ ws }}</td>
                                            <td class="sticky-col colour-cell">
                                                <span class="colour-badge">{{ received_type }}</span>
                                            </td>
                                            <td v-for="size in data[header][lot]['primary_values']" :key="size"
                                                class="size-cell">
                                                {{ data[header][lot]['details'][ws][received_type][colour]['values'][size] }}
                                            </td>
                                            <td class="total-cell">
                                                <span class="total-val">
                                                    {{ data[header][lot]['details'][ws][received_type][colour]['total'] }}
                                                </span>
                                            </td>
                                        </tr>
                                    </template>        
                                </template>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="empty-state">
            <p>Select a Date to view the report</p>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
    selected_supplier: {
        type: String,
        required: true
    }
})

const date_filter_wrapper = ref(null)
const ws_filter_wrapper = ref(null)
let date_filter_control = null
let ws_value = null

const selected_date = ref(null)
const selected_ws = ref(null)
const headers = ref([])
const data = ref({})

const initFilter = () => {
    if (!date_filter_wrapper.value) return

    $(date_filter_wrapper.value).empty()

    date_filter_control = frappe.ui.form.make_control({
        parent: $(date_filter_wrapper.value),
        df: {
            fieldtype: 'Date',
            fieldname: 'date',
            label: 'Date',
            default: selected_date.value,
            placeholder: "Date",
            change: () => {
                selected_date.value = date_filter_control.get_value()
            }
        },
        render_input: true
    })
    if (!ws_filter_wrapper.value) return

    $(ws_filter_wrapper.value).empty()

    ws_value = frappe.ui.form.make_control({
        parent: $(ws_filter_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'work_station',
            label: 'Work Station',
            options: 'Work Station',
            placeholder: "Work Station",
            change: () => {
                selected_ws.value = ws_value.get_value()
            }
        },
        render_input: true
    })
}

const fetchDPRData = () => {
    if (!props.selected_supplier || !selected_date.value) return
    frappe.call({
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_sewing_plan_dpr_data',
        args: {
            supplier: props.selected_supplier,
            dpr_date: selected_date.value,
            work_station: selected_ws.value ,
        },
        callback: (r) => {
            headers.value = r.message.headers
            data.value = r.message.dpr_data
        }
    })
}

onMounted(() => {
    initFilter()
})

watch(() => [props.selected_supplier, selected_date.value, selected_ws.value], fetchDPRData)

</script>
    
<style scoped>
.dpr-tab {
    padding: 1rem;
}

.filter-section {
    margin-bottom: 2rem;
    position: relative;
    z-index: 50;
    text-align: left;
}

.filter-card {
    background: white;
    padding: 1rem 1.5rem;
    border-radius: 1rem;
    border: 1px solid #f1f5f9;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
    display: flex;
    align-items: center;
    gap: 2rem;
    min-width: 400px;
    width: fit-content;
}

.filter-title-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    color: #64748b;
}

.filter-icon {
    width: 1.1rem;
    height: 1.1rem;
}

.filter-label {
    font-size: 0.875rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    white-space: nowrap;
}

.filter-control {
    flex: 1;
    min-width: 200px;
}

.filter-control :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.filter-control :deep(.control-label) {
    display: none !important;
}

.filter-control :deep(.input-with-feedback) {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 0.75rem !important;
    height: 38px !important;
    font-weight: 500 !important;
}

.plan-card {
    background: white;
    border-radius: 1.5rem;
    padding: 10px;
    border: 1px solid #f1f5f9;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.04);
}

.plan-header {
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.plan-info {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.plan-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #94a3b8;
    background: #f8fafc;
    padding: 0.25rem 0.75rem;
    border-radius: 0.5rem;
}

.plan-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #334155;
    margin: 0;
}

.record-btn {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 1.25rem;
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 0.85rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 4px 12px rgba(26, 115, 232, 0.2);
}

.record-btn:hover {
    background: #1557b0;
    transform: translateY(-1px);
    box-shadow: 0 6px 15px rgba(26, 115, 232, 0.3);
}

.record-btn:active {
    transform: translateY(0) scale(0.98);
}

.record-icon {
    width: 1rem;
    height: 1rem;
}

/* Data Table Styling */
.table-wrapper {
    overflow-x: auto;
    border-radius: 0.75rem;
    border: 1px solid #e2e8f0;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

/* Header Row */
.header-row th {
    background: transparent;
    padding: 5px;
    text-align: center;
    font-size: 0.875rem;
    font-weight: 600;
    color: #475569;
    border: 1px solid #e2e8f0;
}

.header-row th:last-child {
    border-right: 1px solid #e2e8f0;
}

.index-col,
.colour-col,
.part-col {
    text-align: center !important;
}

.sticky-col {
    position: sticky;
    left: 0;
    z-index: 10;
    background: white;
}

/* Data Rows */
.data-row {
    transition: background-color 0.15s ease;
}

.data-row:hover {
    background-color: #f8fafc;
}

.data-cell,
.index-cell,
.colour-cell,
.part-cell,
.size-cell,
.total-cell {
    padding: 10px;
    border: 1px solid #e2e8f0;
    color: #334155;
    font-weight: 500;
    white-space: nowrap;
    text-align: center;
}

.header-row th {
    font-weight: 700;
}

.data-row:last-child td {
    border-bottom: none;
}

.total-cell {
    border-right: none;
}

.index-cell,
.colour-cell {
    text-align: center;
}

.index-cell {
    color: #cbd5e1;
    font-weight: 400;
    width: 30px;
}

.colour-badge {
    color: #1e293b;
    font-weight: 500;
    font-size: 0.875rem;
}

.part-cell {
    text-align: center;
}

.part-pill {
    color: #1a73e8;
    background: #eff6ff;
    padding: 0.25rem 0.6rem;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid #dbeafe;
}

.size-cell {
    color: #334155;
    font-weight: 500;
    min-width: 60px;
}

.total-cell {
    background-color: transparent;
    color: #2563eb;
    font-weight: 600;
    font-size: 0.875rem;
    text-align: right;
}

.colour-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: #1e293b;
    background: #fdfdfd;
    vertical-align: middle;
    text-align: center;
}

.type-indicator {
    font-size: 0.75rem;
    font-weight: 600;
    text-align: center;
    padding: 0.25rem 0.5rem;
    border: 1px solid transparent;
}

.type-indicator.planned {
    color: #64748b;
    background: #f8fafc;
}

.type-indicator.actual {
    color: #1a73e8;
    background: #eff6ff;
}

.planned-val {
    background: #fdfdfd;
    color: #94a3b8;
    font-size: 0.875rem;
    font-weight: 500;
    text-align: center;
}

.part-cell {
    vertical-align: middle;
    text-align: center;
}

.empty-state {
    text-align: center;
    color: #94a3b8;
    padding: 3rem 0;
}

/* Scrollbar Utility */
.no-scrollbar::-webkit-scrollbar {
    height: 6px;
    width: 6px;
}

.no-scrollbar::-webkit-scrollbar-track {
    background: transparent;
}

.no-scrollbar::-webkit-scrollbar-thumb {
    background: #e2e8f0;
    border-radius: 10px;
}

.no-scrollbar::-webkit-scrollbar-thumb:hover {
    background: #cbd5e1;
}
</style>