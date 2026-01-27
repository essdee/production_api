<template>
    <div class="scr-tab">
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filter by Lot</span>
                </div>
                <div class="filter-control">
                    <div ref="lot_filter_wrapper"></div>
                </div>
                <div class="filter-control" v-show="colour_options.length > 0">
                     <div ref="colour_filter_wrapper"></div>
                </div>
            </div>
        </div>

        <div class="response-container">
            <div v-if="displayedData" class="response-data">
                <h3 class="plan-title" style="margin-bottom: 20px;">{{ item_name }}</h3>
                <div class="table-wrapper no-scrollbar">
                    <table class="data-table">
                        <thead>
                            <tr class="header-row">
                                <th class="sticky-col colour-col">Colour</th>
                                <th v-if="is_set_item" class="part-col">{{ set_attr }}</th>
                                <th class="sticky-col colour-col">Type</th>
                                <th v-for="size in primary_values" :key="size" class="size-col">{{ size }}</th>
                                <th class="total-col">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template v-for="header in headers">
                                <tr v-for="(values, colour) in displayedData" :key="`${header}-${colour}`" class="data-row">
                                    <td class="sticky-col colour-cell">
                                         <span class="colour-badge">{{ colour }}</span>
                                    </td>
                                    <td v-if="is_set_item" class="part-cell">
                                        <span class="part-pill">{{ displayedData[colour]['part'] }}</span>
                                    </td>
                                    <td class="sticky-col colour-cell">
                                        <span class="type-badge">{{ header }}</span>
                                    </td>
                                    <td class="size-cell" v-for="size in primary_values"
                                        :class="{
                                            'negative-balance': isNegativeBalance(
                                                header,
                                                values['values']?.[size]?.[header] || 0
                                            )
                                        }"
                                    >
                                        {{ values['values']?.[size]?.[header] || 0 }}
                                    </td>
                                    <td class="total-cell font-bold"
                                        :class="{
                                            'negative-balance': isNegativeBalance(
                                                header,
                                                values['type_wise_total']?.[header] || 0
                                            )
                                        }"
                                    >
                                        {{ values['type_wise_total']?.[header] || 0 }}
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>
            <div v-else class="empty-state">
                <p>Select a Lot to view the report</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue'

const props = defineProps({
    selected_supplier: {
        type: String,
        default: null
    },
})

const lot_filter_wrapper = ref(null)
const colour_filter_wrapper = ref(null)
const selected_lot = ref(null)
const selected_colour = ref(null)
const response = ref(null)
const colour_options = ref([])
const headers = ref([])
const primary_values = ref([])
const is_set_item = ref(false)
const set_attr = ref(null)
const item_name = ref(null)
let lot_filter_control = null
let colour_filter_control = null

const displayedData = computed(() => {
    if (!response.value || !response.value.data) return null
    
    if (selected_colour.value && response.value.data[selected_colour.value]) {
        return {
            [selected_colour.value] : response.value.data[selected_colour.value]
        }
    }
    
    return response.value.data
})

const isNegativeBalance = (header, value) => {
    if (!header) return false
    return header.toLowerCase().includes('balance') && Number(value) < 0
}

const initLotFilter = () => {
    if (!lot_filter_wrapper.value) return
    $(lot_filter_wrapper.value).empty()
    
    lot_filter_control = frappe.ui.form.make_control({
        parent: $(lot_filter_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'lot',
            options: 'Lot',
            label: 'Lot',
            change: () => {
                selected_lot.value = lot_filter_control.get_value()
            }
        },
        render_input: true,
    })
}

const initColourFilter = () => {
    if (!colour_filter_wrapper.value) return
    // Clear previous control if it exists to avoid duplicates
    $(colour_filter_wrapper.value).empty()
    
    colour_filter_control = frappe.ui.form.make_control({
        parent: $(colour_filter_wrapper.value),
        df: {
            fieldtype: 'Select',
            fieldname: 'colour',
            options: colour_options.value,
            label: 'Colour',
            placeholder: 'Select Colour',
            change: () => {
                selected_colour.value = colour_filter_control.get_value()
            }
        },
        render_input: true,
    })
}

const fetchData = () => {
    if (!props.selected_supplier || !selected_lot.value) {
        response.value = null
        colour_options.value = []
        selected_colour.value = null
        if(colour_filter_control) {
             $(colour_filter_wrapper.value).empty()
             colour_filter_control = null
        }
        return
    }

    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_scr_data",
        args: {
            supplier: props.selected_supplier,
            lot: selected_lot.value
        },
        callback: (r) => {
            response.value = r.message
            if (r.message && r.message.colours) {
                 // Add an empty option or 'All' if needed, here just raw options
                 colour_options.value = r.message.colours
                 headers.value = r.message.headers
                 primary_values.value = r.message.primary_values
                 is_set_item.value = r.message.is_set_item
                 set_attr.value = r.message.set_attr
                 item_name.value = r.message.item
                 nextTick(() => {
                    initColourFilter()
                 })
            } else {
                 colour_options.value = []
                 selected_colour.value = null
                  if(colour_filter_control) {
                     $(colour_filter_wrapper.value).empty()
                     colour_filter_control = null
                }
            }
        }
    })
}

onMounted(() => {
    initLotFilter()
})

watch(() => [props.selected_supplier, selected_lot.value], fetchData)
</script>

<style scoped>
.scr-tab {
    padding: 1.5rem;
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

.response-container {
    background: white;
    border-radius: 1rem;
    padding: 0;
    /* border: 1px solid #e2e8f0; */
    overflow: hidden;
    margin-top: 1rem;
}

.response-data {
    width: 100%;
    margin: 0;
    /* overflow-x: auto; */
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

.type-badge {
    background: #e2e8f0;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: #475569;
}

.negative-balance {
    background: #fecaca;
    color: #7f1d1d;
    font-weight: 600;
}

.plan-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #334155;
    margin: 0;
}
</style>
