<template>
    <div class="status-summary-tab">
        <!-- Filter Section -->
        <div class="filter-section" v-if="dataRows.length > 0">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filters</span>
                </div>
                <select class="filter-select" v-model="selected_lot">
                    <option value="">All Lots</option>
                    <option v-for="lot in lotOptions" :key="lot" :value="lot">{{ lot }}</option>
                </select>
                <select class="filter-select" v-model="selected_item">
                    <option value="">All Items</option>
                    <option v-for="item in itemOptions" :key="item" :value="item">{{ item }}</option>
                </select>
                <select class="filter-select" v-model="selected_colour">
                    <option value="">All Colours</option>
                    <option v-for="colour in colourOptions" :key="colour" :value="colour">{{ colour }}</option>
                </select>
                <select class="filter-select" v-model="selected_part">
                    <option value="">All Parts</option>
                    <option v-for="part in partOptions" :key="part" :value="part">{{ part }}</option>
                </select>
            </div>
        </div>

        <div class="report-wrapper">
            <div class="report-container no-scrollbar" v-if="displayData.length > 0">
                <table class="report-table">
                    <thead>
                        <tr class="header-row">
                            <th v-for="header in items['header1']" :key="header" class="header-cell primary-header">
                                {{ header }}
                            </th>
                            <th v-for="header in items['header2']" :key="header" class="header-cell primary-header">
                                {{ header }}
                            </th>
                            <th v-for="header in items['header3']" :key="header" class="header-cell primary-header">
                                {{ header }}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(row, idx) in displayData" :key="idx" class="data-row" :style="idx === 0 ? 'background: bisque' : ''">
                            <template v-if="idx == 0">
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td v-for="header in items['header2']" :key="header" class="data-cell numeric-cell">
                                    {{ formatNumber(row[header]) }}
                                </td>
                                <td v-for="header in items['header3']" :key="header" class="data-cell"></td>
                            </template>
                            <template v-else>
                                <td class="data-cell item-cell">{{ row['item'] }}</td>
                                <td class="data-cell">
                                    <span class="lot-pill">{{ row['lot'] }}</span>
                                </td>
                                <td class="data-cell item-cell">{{ row['display_colour'] || getAttrValue(row, row['pack_attr']) }}</td>
                                <td class="data-cell item-cell">{{ row['is_set_item'] ? getAttrValue(row, row['set_attr']) : '-' }}</td>
                                <td class="data-cell item-cell">{{ formatDate(row['FI Date']) }}</td>
                                <td class="data-cell item-cell">{{ formatDate(row['Input Date']) }}</td>
                                <td class="data-cell item-cell">{{ formatDate(row['Last Sewing Output']) }}</td>
                                <td class="data-cell numeric-cell">{{ row['Total Running Days'] }}</td>
                                <td v-for="header in items['header2']" :key="header" class="data-cell numeric-cell">
                                    {{ formatNumber(row[header]) }}
                                </td>
                                <td v-for="header in items['header3']" :key="header" class="data-cell numeric-cell" :style="{ backgroundColor: getStatusStyle(row[header]) }">
                                    {{ row[header] }}
                                </td>
                            </template>
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
                <p class="empty-text">No production data for this Warehouse</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, computed } from "vue"

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

const items = ref({
    "header1": [],
    "header2": [],
    "header3": [],
    "data": []
})

// Filter state
const selected_lot = ref('')
const selected_item = ref('')
const selected_colour = ref('')
const selected_part = ref('')

// Data rows (excluding total row at idx 0)
const dataRows = computed(() => {
    return items.value.data.length > 1 ? items.value.data.slice(1) : []
})

// --- Filter option computeds ---

const lotOptions = computed(() => {
    const vals = new Set()
    for (const row of dataRows.value) {
        if (row.lot) vals.add(row.lot)
    }
    return [...vals].sort()
})

const itemOptions = computed(() => {
    const vals = new Set()
    for (const row of dataRows.value) {
        if (selected_lot.value && row.lot !== selected_lot.value) continue
        if (row.item) vals.add(row.item)
    }
    return [...vals].sort()
})

const colourOptions = computed(() => {
    const vals = new Set()
    for (const row of dataRows.value) {
        if (selected_lot.value && row.lot !== selected_lot.value) continue
        if (row.display_colour) vals.add(row.display_colour)
    }
    return [...vals].sort()
})

const partOptions = computed(() => {
    const vals = new Set()
    for (const row of dataRows.value) {
        if (selected_lot.value && row.lot !== selected_lot.value) continue
        if (row.is_set_item && row.attr_details && row.set_attr) {
            const part = row.attr_details[row.set_attr]
            if (part) vals.add(part)
        }
    }
    return [...vals].sort()
})

// --- Filtered data computeds ---

const filteredRows = computed(() => {
    return dataRows.value.filter(row => {
        if (selected_lot.value && row.lot !== selected_lot.value) return false
        if (selected_item.value && row.item !== selected_item.value) return false
        if (selected_colour.value && row.display_colour !== selected_colour.value) return false
        if (selected_part.value) {
            if (row.is_set_item) {
                const part = row.attr_details && row.set_attr ? row.attr_details[row.set_attr] : null
                if (part !== selected_part.value) return false
            }
            // Non-set items pass through — they have no part concept
        }
        return true
    })
})

const filteredTotal = computed(() => {
    const total = {}
    for (const key of items.value.header2) {
        total[key] = 0
        for (const row of filteredRows.value) {
            total[key] += (row[key] || 0)
        }
    }
    return total
})

const displayData = computed(() => {
    if (filteredRows.value.length === 0) return []
    return [filteredTotal.value, ...filteredRows.value]
})

// --- Cascade watchers ---

watch(selected_lot, () => {
    selected_colour.value = ''
    selected_part.value = ''
    if (selected_item.value && !itemOptions.value.includes(selected_item.value)) {
        selected_item.value = ''
    }
})

// Reset all filters on data reload / supplier change
watch(items, () => {
    selected_lot.value = ''
    selected_item.value = ''
    selected_colour.value = ''
    selected_part.value = ''
})

// --- Helpers ---

const formatNumber = (val) => {
    if (!val && val !== 0) return '-'
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

const getStatusStyle = (value) => {
    if (!value) return '#fee2e2' // Light Red
    if (value === 'Completed') return '#dcfce7' // Light Green
    return '#fef9c3' // Light Yellow
}

const getAttrValue = (row, attrName) => {
    if (!row || !row.attr_details || !attrName) return '-'
    return row.attr_details[attrName] || '-'
}

const fetchData = () => {
    if (!props.selected_supplier) {
        items.value = { "header1": [], "header2": [], "data": [], "header3": [] }
        return
    }
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_sp_status_summary",
        args: {
            supplier: props.selected_supplier
        },
        callback: (r) => {
            if (r.message) {
                items.value = {
                    header1: r.message.header1 || [],
                    header2: r.message.header2 || [],
                    header3: r.message.header3 || [],
                    data: r.message.data || []
                }
            }
        }
    })
}

watch(() => [props.selected_supplier, props.refresh_counter], fetchData, { immediate: true })
</script>

<style scoped>
@import "../SewingPlan.css";

.status-summary-tab {
    padding: 1rem 0;
}

.filter-select {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    height: 38px;
    font-weight: 500;
    font-size: 0.875rem;
    color: #334155;
    padding: 0 0.75rem;
    min-width: 150px;
    outline: none;
    cursor: pointer;
    appearance: auto;
    transition: border-color 0.2s ease;
}

.filter-select:focus {
    border-color: #94a3b8;
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

/* Header Row */
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

/* Sticky Header1 Columns */
.report-table th:nth-child(-n+8),
.report-table td:nth-child(-n+8) {
    position: sticky;
    background-color: white;
    z-index: 10;
}

/* Higher Z-index for Sticky Headers (intersecting top and side) */
.report-table th:nth-child(-n+8) {
    z-index: 30;
}

.report-table th:nth-child(1), .report-table td:nth-child(1) { left: 0; min-width: 200px; max-width: 200px; }
.report-table th:nth-child(2), .report-table td:nth-child(2) { left: 200px; min-width: 140px; }
.report-table th:nth-child(3), .report-table td:nth-child(3) { left: 340px; min-width: 140px; }
.report-table th:nth-child(4), .report-table td:nth-child(4) { left: 440px; min-width: 100px; }
.report-table th:nth-child(5), .report-table td:nth-child(5) { left: 540px; min-width: 110px; }
.report-table th:nth-child(6), .report-table td:nth-child(6) { left: 650px; min-width: 110px; }
.report-table th:nth-child(7), .report-table td:nth-child(7) { left: 760px; min-width: 140px; }
.report-table th:nth-child(8), .report-table td:nth-child(8) { left: 900px; min-width: 90px; }

.data-row[style*="background: bisque"] td {
    background-color: bisque !important;
}

/* Border refining for separate collapse */
.report-table th,
.report-table td {
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
}

/* Add a visual shadow/border to the edge of the sticky segment */
.report-table th:nth-child(8),
.report-table td:nth-child(8) {
    border-right: 2px solid #cbd5e1;
}

.primary-header {
    color: #374151 !important;
}

.data-cell {
    padding: 5px;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
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
    font-size: 0.875rem;
    overflow: hidden;
    text-overflow: ellipsis;
}

.lot-pill {
    background: #eff6ff;
    color: #2563eb;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-block;
}

.attr-cell {
    color: #9CA3AF;
    font-size: 0.8rem;
}

.numeric-cell {
    text-align: right;
    font-weight: 600;
    font-size: 1rem;
    color: #111827;
}

/* Empty State Styling */
.empty-report {
    padding: 10rem 2rem;
    text-align: center;
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

/* Scrollbar Utility */
.no-scrollbar::-webkit-scrollbar {
    display: none;
}
.no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
</style>
