<template>
    <div class="item-summary-tab">
        <!-- Filter Section -->
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filters</span>
                </div>
                <div ref="lot_wrapper" class="filter-control"></div>
                <div ref="item_wrapper" class="filter-control"></div>
                <button
                    class="record-btn"
                    :disabled="!selected_supplier"
                    @click="fetchData"
                >
                    <svg class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                    </svg>
                    Fetch
                </button>
            </div>
        </div>

        <div v-if="loading" class="report-wrapper">
            <div class="empty-state">
                <p class="empty-text">Loading...</p>
            </div>
        </div>

        <template v-else-if="groups.length > 0">
            <div v-for="group in groups" :key="group.item + '-' + group.lot" class="group-section">
                <div class="group-header">
                    <span class="group-item">{{ group.item }}</span>
                    <span class="group-lot-pill">{{ group.lot }}</span>
                </div>
                <div class="report-wrapper">
                    <div class="report-container no-scrollbar">
                        <table class="report-table">
                            <thead>
                                <tr class="header-row">
                                    <th class="header-cell primary-header sticky-col-date">Date</th>
                                    <th class="header-cell primary-header sticky-col-type">Input Type</th>
                                    <th class="header-cell primary-header sticky-col-ws">Work Station</th>
                                    <th class="header-cell primary-header sticky-col-colour">Colour</th>
                                    <th v-if="group.has_part" class="header-cell primary-header sticky-col-part">Part</th>
                                    <th v-for="size in group.headers" :key="size" class="header-cell primary-header">{{ size }}</th>
                                    <th class="header-cell primary-header">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(row, idx) in group.rows" :key="idx" class="data-row">
                                    <td class="data-cell item-cell sticky-col-date">{{ formatDate(row.date) }}</td>
                                    <td class="data-cell sticky-col-type">
                                        <span class="type-pill">{{ row.input_type }}</span>
                                    </td>
                                    <td class="data-cell sticky-col-ws">{{ row.work_station || '-' }}</td>
                                    <td class="data-cell item-cell sticky-col-colour">{{ row.colour }}</td>
                                    <td v-if="group.has_part" class="data-cell item-cell sticky-col-part">{{ row.part || '-' }}</td>
                                    <td v-for="size in group.headers" :key="size" class="data-cell numeric-cell">
                                        {{ formatNumber(row.values[size]) }}
                                    </td>
                                    <td class="data-cell numeric-cell">
                                        {{ formatNumber(row.total) }}
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </template>

        <div v-else class="report-wrapper">
            <div class="empty-state">
                <div class="empty-icon-wrapper">
                    <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                    </svg>
                </div>
                <p class="empty-text">{{ fetched ? 'No data found for the selected filters' : 'Select at least one Lot or Item and click Fetch' }}</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'

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

// Filter options from API
const lotOptions = ref([])
const itemOptions = ref([])

// Frappe control refs
const lot_wrapper = ref(null)
const item_wrapper = ref(null)
let lotCtrl = null
let itemCtrl = null
const sample_doc = ref({})

// Data
const groups = ref([])
const loading = ref(false)
const fetched = ref(false)

const getSelectedLots = () => (lotCtrl ? lotCtrl.get_value() : []) || []
const getSelectedItems = () => (itemCtrl ? itemCtrl.get_value() : []) || []

const formatNumber = (val) => {
    if (!val && val !== 0) return '-'
    if (val === 0) return '-'
    return new Intl.NumberFormat().format(val)
}

const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const parts = dateStr.split('-')
    if (parts.length === 3) {
        return `${parts[2]}-${parts[1]}-${parts[0]}`
    }
    return dateStr
}

const initControls = () => {
    if (lot_wrapper.value && !lotCtrl) {
        lotCtrl = frappe.ui.form.make_control({
            parent: $(lot_wrapper.value),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'lot',
                label: '',
                placeholder: 'Select Lots',
                get_data: function(txt) {
                    return lotOptions.value
                        .filter(l => !txt || l.toLowerCase().includes(txt.toLowerCase()))
                        .map(l => ({ value: l, description: '' }))
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
    if (item_wrapper.value && !itemCtrl) {
        itemCtrl = frappe.ui.form.make_control({
            parent: $(item_wrapper.value),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'item',
                label: '',
                placeholder: 'Select Items',
                get_data: function(txt) {
                    return itemOptions.value
                        .filter(i => !txt || i.toLowerCase().includes(txt.toLowerCase()))
                        .map(i => ({ value: i, description: '' }))
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
}

const loadOptions = () => {
    if (!props.selected_supplier) {
        lotOptions.value = []
        itemOptions.value = []
        return
    }
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_item_summary_options",
        args: { supplier: props.selected_supplier },
        callback: (r) => {
            if (r.message) {
                lotOptions.value = r.message.lots || []
                itemOptions.value = r.message.items || []
            }
        }
    })
}

const fetchData = () => {
    const lots = getSelectedLots()
    const items = getSelectedItems()
    if (!props.selected_supplier || (!lots.length && !items.length)) {
        frappe.msgprint("Please select at least one Lot or Item")
        return
    }
    loading.value = true
    fetched.value = true

    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_item_summary_data",
        args: {
            supplier: props.selected_supplier,
            lots: JSON.stringify(lots.length ? lots : null),
            items: JSON.stringify(items.length ? items : null),
        },
        callback: (r) => {
            loading.value = false
            if (r.message) {
                groups.value = r.message.groups || []
            }
        },
        error: () => {
            loading.value = false
        }
    })
}

onMounted(() => {
    initControls()
})

// Reload options on supplier change or refresh
watch(() => [props.selected_supplier, props.refresh_counter], () => {
    if (lotCtrl) lotCtrl.set_value([])
    if (itemCtrl) itemCtrl.set_value([])
    groups.value = []
    fetched.value = false
    loadOptions()
}, { immediate: true })
</script>

<style scoped>
@import "../SewingPlan.css";

.item-summary-tab {
    padding: 1rem 0;
}

.filter-control {
    min-width: 250px;
}

.filter-control :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.filter-control :deep(.control-label) {
    display: none !important;
}

.filter-control :deep(.control-input-wrapper) {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 0.75rem !important;
    min-height: 38px !important;
    font-weight: 500 !important;
}

.filter-control :deep(.control-input) {
    background: transparent !important;
    border: none !important;
}

.filter-control :deep(.input-with-feedback) {
    background: transparent !important;
    border: none !important;
    font-weight: 500 !important;
}

/* Group Section */
.group-section {
    margin-bottom: 2rem;
}

.group-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 1.5rem;
    margin-bottom: 0.5rem;
}

.group-item {
    font-size: 1.1rem;
    font-weight: 700;
    color: #111827;
    letter-spacing: -0.01em;
}

.group-lot-pill {
    background: #eff6ff;
    color: #2563eb;
    padding: 0.3rem 0.9rem;
    border-radius: 1rem;
    font-size: 0.8rem;
    font-weight: 600;
}

/* Report */
.report-wrapper {
    background: white;
    border-radius: 3rem;
    padding: 1rem;
    border: 1px solid #f3f4f6;
    box-shadow: 0 40px 100px -20px rgba(0, 0, 0, 0.04);
}

.report-container {
    overflow: auto;
    max-height: 65vh;
    border-radius: 2.2rem;
    position: relative;
}

.report-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-top: 1px solid #e2e8f0;
    border-left: 1px solid #e2e8f0;
}

.header-row th {
    position: sticky;
    top: 0;
    z-index: 20;
    background: white;
    padding: 15px;
    text-align: left;
    font-size: 0.875rem;
    font-weight: 700;
    color: #475569;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
}

.primary-header {
    color: #374151 !important;
}

/* Sticky left columns */
.sticky-col-date,
.sticky-col-type,
.sticky-col-ws,
.sticky-col-colour,
.sticky-col-part {
    position: sticky;
    background-color: white;
    z-index: 10;
}

.header-row .sticky-col-date,
.header-row .sticky-col-type,
.header-row .sticky-col-ws,
.header-row .sticky-col-colour,
.header-row .sticky-col-part {
    z-index: 30;
}

.sticky-col-date { left: 0; min-width: 110px; }
.sticky-col-type { left: 110px; min-width: 130px; }
.sticky-col-ws { left: 240px; min-width: 130px; }
.sticky-col-colour { left: 370px; min-width: 140px; }
.sticky-col-part { left: 510px; min-width: 100px; }

/* Border on last sticky col */
.sticky-col-colour {
    border-right: 2px solid #cbd5e1 !important;
}

/* When part column exists, shift the thick border */
.report-table:has(.sticky-col-part) .sticky-col-colour {
    border-right: 1px solid #e2e8f0 !important;
}

.report-table:has(.sticky-col-part) .sticky-col-part {
    border-right: 2px solid #cbd5e1 !important;
}

.report-table th,
.report-table td {
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
}

.data-cell {
    padding: 5px 10px;
    font-size: 0.875rem;
    font-weight: 500;
    color: #4B5563;
    white-space: nowrap;
    transition: all 0.2s ease;
}

.data-row {
    transition: background-color 0.2s ease;
}

.data-row:hover {
    background-color: #f8fafc;
}

.data-row:hover .data-cell {
    color: #111827;
}

.item-cell {
    font-weight: 600;
    color: #111827;
}

.numeric-cell {
    text-align: right;
    font-weight: 600;
    font-size: 1rem;
    color: #111827;
}

.type-pill {
    background: #f0fdf4;
    color: #15803d;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-block;
}

.record-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
    box-shadow: none !important;
}

.empty-state {
    grid-column: 1 / -1;
    padding: 8rem 0;
    text-align: center;
}

.empty-icon-wrapper {
    width: 4rem;
    height: 4rem;
    background-color: #F9FAFB;
    border-radius: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1.5rem;
    opacity: 0.4;
}

.empty-icon {
    width: 2rem;
    height: 2rem;
    color: #D1D5DB;
}

.empty-text {
    color: #9CA3AF;
    font-weight: 500;
    font-size: 0.875rem;
    margin: 0;
}

.no-scrollbar::-webkit-scrollbar {
    display: none;
}
.no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
</style>
