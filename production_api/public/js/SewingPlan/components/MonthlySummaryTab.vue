<template>
    <div class="monthly-summary-tab">
        <!-- Filter Section -->
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filters</span>
                </div>
                <div ref="start_date_wrapper" class="filter-control"></div>
                <div ref="end_date_wrapper" class="filter-control"></div>
                <div ref="input_type_wrapper" class="filter-control" v-show="!show_grn_val"></div>
                <div ref="show_grn_wrapper" class="filter-control-check"></div>
                <button
                    class="record-btn"
                    :disabled="!canFetch"
                    @click="fetchData"
                >
                    <svg class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                    </svg>
                    Fetch
                </button>
            </div>
        </div>

        <div class="report-wrapper">
            <div v-if="loading" class="empty-state">
                <p class="empty-text">Loading...</p>
            </div>
            <div class="report-container no-scrollbar" v-else-if="rows.length > 0">
                <table class="report-table">
                    <thead>
                        <tr class="header-row">
                            <th class="header-cell primary-header sticky-date-col">Date</th>
                            <th v-for="style in styles" :key="style" class="header-cell primary-header">{{ style }}</th>
                            <th class="header-cell primary-header">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Grand Total Row -->
                        <tr class="data-row" style="background: bisque">
                            <td class="data-cell sticky-date-col" style="font-weight:700; background-color: bisque;">Grand Total</td>
                            <td v-for="style in styles" :key="style" class="data-cell numeric-cell" style="background-color: bisque;">
                                {{ formatNumber(grand_total[style]) }}
                            </td>
                            <td class="data-cell numeric-cell" style="background-color: bisque;">
                                {{ formatNumber(grand_total.total) }}
                            </td>
                        </tr>
                        <!-- Data Rows -->
                        <tr v-for="row in rows" :key="row.date" class="data-row">
                            <td class="data-cell sticky-date-col item-cell">{{ formatDate(row.date) }}</td>
                            <td v-for="style in styles" :key="style" class="data-cell numeric-cell">
                                {{ formatNumber(row[style]) }}
                            </td>
                            <td class="data-cell numeric-cell">
                                {{ formatNumber(row.total) }}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div v-else class="empty-state">
                <div class="empty-icon-wrapper">
                    <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                    </svg>
                </div>
                <p class="empty-text">{{ fetched ? 'No data found for the selected filters' : 'Set filters and click Fetch to load data' }}</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

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

const start_date_wrapper = ref(null)
const end_date_wrapper = ref(null)
const input_type_wrapper = ref(null)
const show_grn_wrapper = ref(null)

const start_date_val = ref(null)
const end_date_val = ref(null)
const input_type_val = ref(null)
const show_grn_val = ref(false)

const styles = ref([])
const rows = ref([])
const grand_total = ref({})
const loading = ref(false)
const fetched = ref(false)

let start_date_ctrl = null
let end_date_ctrl = null
let input_type_ctrl = null
let show_grn_ctrl = null
const sample_doc = ref({})

const canFetch = computed(() => {
    const base = !!(start_date_val.value && end_date_val.value && props.selected_supplier)
    if (show_grn_val.value) return base
    return base && !!input_type_val.value
})

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

const fetchData = () => {
    if (!canFetch.value) return
    loading.value = true
    fetched.value = true

    const args = {
        supplier: props.selected_supplier,
        start_date: start_date_val.value,
        end_date: end_date_val.value,
    }
    if (show_grn_val.value) {
        args.show_grn = 1
    } else {
        args.input_type = input_type_val.value
    }

    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_monthly_summary_data",
        args,
        callback: (r) => {
            loading.value = false
            if (r.message) {
                styles.value = r.message.styles || []
                rows.value = r.message.rows || []
                grand_total.value = r.message.grand_total || {}
            }
        },
        error: () => {
            loading.value = false
        }
    })
}

onMounted(() => {
    if (start_date_wrapper.value) {
        start_date_ctrl = frappe.ui.form.make_control({
            parent: $(start_date_wrapper.value),
            df: {
                fieldtype: "Date",
                fieldname: "start_date",
                label: "",
                placeholder: "Start Date",
                change: function() {
                    start_date_val.value = start_date_ctrl.get_value() || null
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
    if (end_date_wrapper.value) {
        end_date_ctrl = frappe.ui.form.make_control({
            parent: $(end_date_wrapper.value),
            df: {
                fieldtype: "Date",
                fieldname: "end_date",
                label: "",
                placeholder: "End Date",
                change: function() {
                    end_date_val.value = end_date_ctrl.get_value() || null
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
    if (input_type_wrapper.value) {
        input_type_ctrl = frappe.ui.form.make_control({
            parent: $(input_type_wrapper.value),
            df: {
                fieldtype: "Link",
                fieldname: "input_type",
                label: "",
                options: "Sewing Plan Input Type",
                placeholder: "Input Type",
                change: function() {
                    input_type_val.value = input_type_ctrl.get_value() || null
                },
                get_query: function() {
                    return { filters: { name: ["!=", "Order Qty"] } }
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
    if (show_grn_wrapper.value) {
        show_grn_ctrl = frappe.ui.form.make_control({
            parent: $(show_grn_wrapper.value),
            df: {
                fieldtype: "Check",
                fieldname: "show_grn",
                label: "Show GRN Qty",
                change: function() {
                    const val = !!show_grn_ctrl.get_value()
                    show_grn_val.value = val
                    if (val) {
                        input_type_val.value = null
                        if (input_type_ctrl) input_type_ctrl.set_value("")
                    }
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
})
</script>

<style scoped>
@import "../SewingPlan.css";

.monthly-summary-tab {
    padding: 1rem 0;
}

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

.sticky-date-col {
    position: sticky;
    left: 0;
    z-index: 10;
    background-color: white;
    min-width: 120px;
}

.header-row .sticky-date-col {
    z-index: 30;
}

.data-row .sticky-date-col {
    z-index: 5;
}

.data-row[style*="background: bisque"] .sticky-date-col {
    background-color: bisque !important;
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

.record-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
    box-shadow: none !important;
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

.filter-control-check {
    display: flex;
    align-items: center;
}

.filter-control-check :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.filter-control-check :deep(.control-label) {
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    color: #475569 !important;
    white-space: nowrap;
}

.filter-control-check :deep(.checkbox) {
    display: flex;
    align-items: center;
    gap: 0.4rem;
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
