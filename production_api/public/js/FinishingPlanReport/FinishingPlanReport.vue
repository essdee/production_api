<template>
    <div class="fpr-tab">
        <div class="page-title-bar">Finishing Plan Report</div>

        <div class="sp-filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filters</span>
                </div>
                <div class="filter-control">
                    <div ref="lot_filter_wrapper"></div>
                </div>
                <div class="filter-control">
                    <div ref="item_filter_wrapper"></div>
                </div>
                <div class="filter-control">
                    <div ref="season_filter_wrapper"></div>
                </div>
                <div>
                    <button class="btn btn-primary" @click="fetchData()" style="border-radius: 12px; font-weight: 700;">
                        Get Report
                    </button>
                </div>
            </div>
        </div>

        <div v-if="rows.length > 0" class="table-wrapper no-scrollbar fpr-table-wrapper">
            <table class="data-table fpr-table">
                <thead>
                    <tr class="header-row">
                        <th
                            v-for="col in columns"
                            :key="col.fieldname"
                            :class="headerClass(col)"
                            :style="frozenStyle(col, true)"
                        >
                            {{ col.label }}
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(row, idx) in rows" :key="idx" class="data-row">
                        <td
                            v-for="col in columns"
                            :key="col.fieldname"
                            :class="cellClass(col)"
                            :style="frozenStyle(col, false)"
                        >
                            <span v-if="cellColor(col, row)" :style="{ color: cellColor(col, row) }">{{ formatCell(col, row) }}</span>
                            <template v-else>{{ formatCell(col, row) }}</template>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div v-else-if="fetched" class="empty-state">
            <p>No data for the selected filters</p>
        </div>

        <div v-else class="empty-state">
            <p>Loading…</p>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// The page is pure presentation: it reuses the existing "Finishing Plan Report"
// Script Report through Frappe's built-in query_report.run endpoint, so all
// columns and formulas live in finishing_plan_report.py — nothing is duplicated here.
const REPORT_NAME = 'Finishing Plan Report'

// The four left-pinned columns, in column order, with fixed pixel widths.
// Everything else scrolls horizontally underneath them.
const FROZEN = [
    { fieldname: 'item', width: 150 },
    { fieldname: 'description', width: 180 },
    { fieldname: 'lot', width: 140 },
    { fieldname: 'pieces_per_box', width: 110 },
]

// Difference columns the source report colours red (negative) / green (positive).
const COLOR_COLS = new Set([
    'sewing_diff',
    'cut_to_finishing_diff',
    'unaccountable',
    'cut_to_dispatch_diff',
    'finishing_inward_to_dispatch_diff',
])

// Pre-compute each frozen column's cumulative left offset from the widths above.
const frozenMeta = {}
let runningLeft = 0
FROZEN.forEach((f, i) => {
    frozenMeta[f.fieldname] = {
        left: runningLeft,
        width: f.width,
        last: i === FROZEN.length - 1,
    }
    runningLeft += f.width
})

const lot_filter_wrapper = ref(null)
const item_filter_wrapper = ref(null)
const season_filter_wrapper = ref(null)
let lot_control = null
let item_control = null
let season_control = null

const columns = ref([])
const rows = ref([])
const fetched = ref(false)

const isFrozen = (col) => Object.prototype.hasOwnProperty.call(frozenMeta, col.fieldname)
const isFrozenEdge = (col) => isFrozen(col) && frozenMeta[col.fieldname].last

const frozenStyle = (col, isHeader) => {
    const meta = frozenMeta[col.fieldname]
    if (!meta) return {}
    return {
        position: 'sticky',
        left: meta.left + 'px',
        width: meta.width + 'px',
        minWidth: meta.width + 'px',
        maxWidth: meta.width + 'px',
        zIndex: isHeader ? 6 : 5,
    }
}

const headerClass = (col) => ({
    'frozen-cell': isFrozen(col),
    'frozen-edge': isFrozenEdge(col),
})

const cellClass = (col) => ({
    'data-cell': true,
    'frozen-cell': isFrozen(col),
    'frozen-edge': isFrozenEdge(col),
})

// Columns can come back from query_report.run as dicts (script reports) or as
// "Label:Fieldtype/Options:Width" strings depending on the Frappe build.
const normalizeColumn = (col) => {
    if (typeof col === 'string') {
        const parts = col.split(':')
        const label = parts[0] || ''
        let fieldtype = 'Data'
        let options = ''
        if (parts[1]) {
            const typePart = parts[1]
            if (typePart.includes('/')) {
                const [ft, opt] = typePart.split('/')
                fieldtype = ft || 'Data'
                options = opt || ''
            } else {
                fieldtype = typePart
            }
        }
        return { label, fieldname: frappe.scrub(label), fieldtype, options }
    }
    return {
        label: col.label || '',
        fieldname: col.fieldname || frappe.scrub(col.label || ''),
        fieldtype: col.fieldtype || 'Data',
        options: col.options || '',
    }
}

const formatCell = (col, row) => {
    const value = row[col.fieldname]
    if (value === null || value === undefined || value === '') return ''
    if (col.fieldtype === 'Percent') {
        const rounded = Math.round((Number(value) + Number.EPSILON) * 100) / 100
        return `${rounded}%`
    }
    if (col.fieldtype === 'Int') {
        // window.format_number returns a plain string ("12,820"); frappe.format()
        // would return right-aligned HTML, which Vue escapes and shows as raw markup.
        return window.format_number(value, null, 0)
    }
    if (col.fieldtype === 'Float') {
        return window.format_number(value)
    }
    return value
}

const cellColor = (col, row) => {
    if (!COLOR_COLS.has(col.fieldname)) return null
    const value = Number(row[col.fieldname])
    if (value < 0) return '#e03131'
    if (value > 0) return '#2f9e44'
    return null
}

const makeLinkFilter = (wrapper, fieldname, label, options) => {
    $(wrapper).empty()
    return frappe.ui.form.make_control({
        parent: $(wrapper),
        df: {
            fieldtype: 'Link',
            fieldname,
            label,
            options,
            placeholder: label,
        },
        render_input: true,
    })
}

const initFilters = () => {
    if (lot_filter_wrapper.value) {
        lot_control = makeLinkFilter(lot_filter_wrapper.value, 'lot', 'Lot', 'Lot')
    }
    if (item_filter_wrapper.value) {
        item_control = makeLinkFilter(item_filter_wrapper.value, 'item', 'Item', 'Item')
    }
    if (season_filter_wrapper.value) {
        season_control = makeLinkFilter(season_filter_wrapper.value, 'season', 'Season', 'Product Season')
    }
}

// Run the report for a given filters object and render the result.
const runReport = (filters) => {
    frappe.call({
        method: 'frappe.desk.query_report.run',
        args: {
            report_name: REPORT_NAME,
            filters,
        },
        freeze: true,
        freeze_message: 'Fetching report...',
        callback: (r) => {
            fetched.value = true
            const message = r.message || {}
            columns.value = (message.columns || []).map(normalizeColumn)
            rows.value = message.result || []
        },
        error: () => {
            fetched.value = true
            columns.value = []
            rows.value = []
            frappe.show_alert({ message: 'Could not load the report', indicator: 'red' })
        },
    })
}

// "Get Report" button handler: read the current filter values, then run.
const fetchData = () => {
    const filters = {}
    const lot = lot_control ? lot_control.get_value() : null
    const item = item_control ? item_control.get_value() : null
    const season = season_control ? season_control.get_value() : null
    if (lot) filters.lot = lot
    if (item) filters.item = item
    if (season) filters.season = season
    runReport(filters)
}

onMounted(() => {
    initFilters()
    // Load everything on open (matches the source report). Defer past any pending boot
    // ajax and run WITHOUT reading the freshly-created filter controls: reading a
    // just-created control can throw and silently abort the auto-load (which is why the
    // button worked but page-open did not). after_ajax runs immediately if nothing is
    // pending, so this is safe.
})
</script>

<style scoped>
@import "../SewingPlan/SewingPlan.css";

.fpr-tab {
    padding: 1rem;
}

.page-title-bar {
    text-align: center;
    font-size: 1.5rem;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 1rem;
}

/* The wrapper scrolls horizontally; the frozen columns stay pinned. */
.fpr-table-wrapper {
    overflow-x: auto;
}

.fpr-table {
    width: auto;
    min-width: 100%;
    /* Separated borders so each border belongs to its cell and rides along with
       the position:sticky frozen columns. With the shared .data-table default
       (border-collapse: collapse) the grid lines are owned by the table, not the
       cell, so the frozen-column seams flicker/bleed during horizontal scroll. */
    border-collapse: separate;
    border-spacing: 0;
}

/* Redraw the grid as per-cell borders so frozen columns keep their seams while
   scrolling. The .table-wrapper supplies the rounded outer frame. */
.fpr-table th,
.fpr-table td {
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
}

.fpr-table thead th {
    border-top: 1px solid #e2e8f0;
}

.fpr-table th:first-child,
.fpr-table td:first-child {
    border-left: 1px solid #e2e8f0;
}

.fpr-table thead th:not(.frozen-cell) {
    min-width: 80px;
}

/* Frozen cells need a solid background so scrolling columns pass underneath. */
.fpr-table tbody .frozen-cell {
    background: #ffffff;
}

.fpr-table thead .frozen-cell {
    background: #f8fafc;
}

.fpr-table .data-row:hover .frozen-cell {
    background: #f8fafc;
}

/* A soft shadow on the last frozen column marks the scroll boundary. */
.fpr-table .frozen-edge {
    box-shadow: 2px 0 5px -2px rgba(0, 0, 0, 0.15);
}
</style>
