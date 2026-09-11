<template>
	<div ref="report_section">
    <div ref="root" class="fpir-root" >
        <div class="fpir-header">
            <h3 class="fpir-title">Finishing Plan Ironing DPR</h3>
        </div>

        <div class="sp-filter-section">
        <div class="filter-card fpir-filter-row">
            <div class="filter-title-group">
                <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                </svg>
                <span class="filter-label">Filter by Date</span>
            </div>
            <div v-show="!summary" class="filter-control">
                <div class="fpir-control fpir-date-input"></div>
            </div>
            <div v-show="summary" class="filter-control">
                <div class="fpir-control fpir-item-input"></div>
            </div>
            <div v-show="summary" class="filter-control">
                <div class="fpir-control fpir-lot-input"></div>
            </div>
            <div v-show="summary" class="filter-control">
                <div class="fpir-control fpir-from-date-input"></div>
            </div>
            <div v-show="summary" class="filter-control">
                <div class="fpir-control fpir-to-date-input"></div>
            </div>
            <label class="fpir-summary-toggle">
                <input v-model="summary" type="checkbox" @change="onSummaryChange">
                <span>Summary</span>
            </label>
            <div class="fpir-actions">
                <button class="btn btn-primary" :disabled="loading" @click="loadReport">
                    {{ loading ? 'Loading...' : 'Show Report' }}
                </button>
                <button
                    class="btn btn-success fpir-shot-btn"
                    :disabled="loading || copying || !reports.length"
                    @click="copyToClipboard"
                >
                    {{ copying ? 'Copying...' : 'Copy' }}
                </button>
            </div>
        </div>
        </div>

        <div v-if="loading" class="fpir-state">Loading report...</div>

        <div v-else-if="reports.length" class="fpir-body">
            <div class="fpir-summary">
                <div class="fpir-card">
                    <div class="fpir-card-label">Lots</div>
                    <div class="fpir-card-value">{{ reports.length }}</div>
                </div>
                <div class="fpir-card">
                    <div class="fpir-card-label">Rows</div>
                    <div class="fpir-card-value">{{ totalRows }}</div>
                </div>
                <div class="fpir-card">
                    <div class="fpir-card-label">Total Qty</div>
                    <div class="fpir-card-value">{{ fmt(totalQty) }}</div>
                </div>
            </div>

            <section v-for="group in reportsByDate" :key="group.date" class="fpir-date-section">
                <div v-if="summary" class="fpir-date-heading">
                    <strong>{{ formatDate(group.date) }}</strong>
                    <span>{{ group.rows.length }} lots · {{ fmt(getDateTotal(group.rows)) }} qty</span>
                </div>

                <div
                    v-for="report in group.rows"
                    :key="`${group.date}-${report.lot}`"
                    class="fpir-block"
                >
                    <div class="fpir-block-header">
                        <div class="fpir-block-title">LOT: {{ report.lot }}</div>
                        <div class="fpir-block-meta">
                            <span>Item: {{ report.item }}</span>
                        </div>
                    </div>

                    <div class="table-responsive">
                        <table class="table table-bordered table-sm fpir-table">
                            <thead>
                                <tr>
                                    <th>No</th>
                                    <th v-if="shouldShowPart(report)">Part</th>
                                    <th>Colour</th>
                                    <th
                                        v-for="size in getSizes(report)"
                                        :key="`${report.lot}-${size}`"
                                        class="text-end"
                                    >
                                        {{ size }}
                                    </th>
                                    <th class="text-end">Total Qty</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr
                                    v-for="row in report.rows"
                                    :key="`${report.lot}-${row.s_no}-${row.colour || ''}`"
                                >
                                    <td>{{ row.s_no }}</td>
                                    <td v-if="shouldShowPart(report)">{{ row.part || '' }}</td>
                                    <td>{{ row.colour || '' }}</td>
                                    <td
                                        v-for="size in getSizes(report)"
                                        :key="`${report.lot}-${row.s_no}-${size}`"
                                        class="text-end"
                                    >
                                        {{ fmt(row[size] || 0) }}
                                    </td>
                                    <td class="text-end">{{ fmt(row.total_qty || 0) }}</td>
                                </tr>
                            </tbody>
                            <tfoot>
                                <tr>
                                    <th :colspan="shouldShowPart(report) ? 3 : 2">Total</th>
                                    <th
                                        v-for="size in getSizes(report)"
                                        :key="`${report.lot}-total-${size}`"
                                        class="text-end"
                                    >
                                        {{ fmt(getSizeTotal(report.rows, size)) }}
                                    </th>
                                    <th class="text-end">{{ fmt(getReportTotal(report.rows)) }}</th>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                </div>
            </section>
        </div>

        <div v-else class="fpir-state">No records found.</div>
    </div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import * as htmlToImage from 'html-to-image'

const root = ref(null)
const loading = ref(false)
const copying = ref(false)
const reports = ref([])
const sampleDoc = ref({})
const report_section=ref(null)
const summary = ref(false)

let dateCtrl = null
let lotCtrl = null
let itemCtrl = null
let dcCtrl = null
let fromDateCtrl = null
let toDateCtrl = null

onMounted(() => {
    nextTick(() => {
        const el = root.value

        $(el).find('.fpir-date-input').html('')
        dateCtrl = frappe.ui.form.make_control({
            parent: $(el).find('.fpir-date-input'),
            df: {
                fieldtype: 'Date',
                fieldname: 'date',
                label: 'Actual Date *',
                placeholder: 'Actual Date',
            },
            doc: sampleDoc.value,
            render_input: true,
        })

        $(el).find('.fpir-lot-input').html('')
        lotCtrl = frappe.ui.form.make_control({
            parent: $(el).find('.fpir-lot-input'),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'lot',
                label: 'Lot',
                placeholder: 'Lot',
                options: 'Lot',
                get_data: function(txt) {
                    return frappe.db.get_link_options('Lot', txt)
                },
            },
            doc: sampleDoc.value,
            render_input: true,
        })

        $(el).find('.fpir-item-input').html('')
        itemCtrl = frappe.ui.form.make_control({
            parent: $(el).find('.fpir-item-input'),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'item',
                label: 'Item',
                placeholder: 'Item',
                options: 'Item',
                get_data: function(txt) {
                    return frappe.db.get_link_options('Item', txt)
                },
            },
            doc: sampleDoc.value,
            render_input: true,
        })

        $(el).find('.fpir-from-date-input').html('')
        fromDateCtrl = frappe.ui.form.make_control({
            parent: $(el).find('.fpir-from-date-input'),
            df: {
                fieldtype: 'Date',
                fieldname: 'from_date',
                label: 'From Date *',
                placeholder: 'From Date',
            },
            doc: sampleDoc.value,
            render_input: true,
        })

        $(el).find('.fpir-to-date-input').html('')
        toDateCtrl = frappe.ui.form.make_control({
            parent: $(el).find('.fpir-to-date-input'),
            df: {
                fieldtype: 'Date',
                fieldname: 'to_date',
                label: 'To Date *',
                placeholder: 'To Date',
            },
            doc: sampleDoc.value,
            render_input: true,
        })
    })
})

function normalizeValue(value) {
    if (!value) return null
    if (typeof value === 'string') return value
    if (value && typeof value === 'object') {
        return value.value || value.name || null
    }
    return value || null
}

function normalizeMultiValue(value) {
    if (!value) return []
    if (typeof value === 'string') {
        if (!value.trim() || value.trim() === '[]') return []
        try {
            value = JSON.parse(value)
        } catch (e) {
            return [value]
        }
    }
    if (Array.isArray(value)) {
        return value
            .map((row) => {
                if (row && typeof row === 'object') {
                    return row.value || row.name || null
                }
                return row || null
            })
            .filter(Boolean)
    }
    if (value && typeof value === 'object') {
        return [value.value || value.name].filter(Boolean)
    }
    return [value].filter(Boolean)
}

function loadReport() {
    const selectedDate = dateCtrl ? normalizeValue(dateCtrl.get_value()) : null
    const selectedDc = dcCtrl ? normalizeValue(dcCtrl.get_value()) : null
    const fromDate = fromDateCtrl ? normalizeValue(fromDateCtrl.get_value()) : null
    const toDate = toDateCtrl ? normalizeValue(toDateCtrl.get_value()) : null
    const selectedLots = summary.value && lotCtrl ? normalizeMultiValue(lotCtrl.get_value()) : []
    const selectedItems = summary.value && itemCtrl ? normalizeMultiValue(itemCtrl.get_value()) : []

    if (!summary.value && !selectedDate && !selectedDc) {
        frappe.show_alert({
            message: 'Select a date before clicking the Show Report button',
            indicator: 'orange',
        })
        return
    }
	if (summary.value && (!fromDate || !toDate)) {
        frappe.show_alert({
            message: 'Select From Date and To Date before clicking the Show Report button',
            indicator: 'orange',
        })
        return
    }
    if (summary.value && fromDate > toDate) {
        frappe.show_alert({ message: 'From Date cannot be after To Date', indicator: 'orange' })
        return
    }
	
    loading.value = true
    frappe.call({
        method: 'production_api.utils.dc_dpr_report',
        args: {
            date: summary.value ? null : selectedDate,
            from_date: summary.value ? fromDate : null,
            to_date: summary.value ? toDate : null,
            summary: summary.value ? 1 : 0,
            lot: selectedLots,
            item: selectedItems,
            dc_name: selectedDc,
        },
        freeze: true,
        freeze_message: 'Fetching Finishing Plan Ironing Report...',
        callback(r) {
            reports.value = r.message || []
            loading.value = false
        },
        error() {
            loading.value = false
        },
    })
}

function onSummaryChange() {
    reports.value = []
}

const copyToClipboard = async () => {
    const sourceDiv = root.value
    if (!sourceDiv || !reports.value.length || copying.value) {
        frappe.show_alert({
            message: 'Please click Show Report before copying the report',
            indicator: 'orange',
        })
        return
    }

    copying.value = true
    try {
        const blob = await htmlToImage.toBlob(sourceDiv, {
            backgroundColor: '#ffffff',
            pixelRatio: 1,
        })

        if (!blob || !navigator.clipboard?.write || typeof ClipboardItem === 'undefined') {
            throw new Error('Clipboard image copy is not supported')
        }

        await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob }),
        ])

        frappe.show_alert({ message: 'Copied to clipboard', indicator: 'green' })
    } catch (err) {
        console.error('Failed to copy ironing report image', err)
        frappe.show_alert({ message: 'Copy failed', indicator: 'red' })
    } finally {
        copying.value = false
    }
}

function getSizes(report) {
    return report?.primary_attributes || []
}

function shouldShowPart(report) {
    const hasPartAttr = (report?.attributes || []).some(
        (attr) => String(attr).toLowerCase() === 'part'
    )
    const hasPartValue = (report?.rows || []).some((row) => String(row.part || '').trim())
    return hasPartAttr && hasPartValue
}

function getSizeTotal(rows, size) {
    return (rows || []).reduce((sum, row) => sum + Number(row[size] || 0), 0)
}

function getReportTotal(rows) {
    return (rows || []).reduce((sum, row) => sum + Number(row.total_qty || 0), 0)
}

function getDateTotal(dateReports) {
    return (dateReports || []).reduce(
        (sum, report) => sum + getReportTotal(report.rows),
        0
    )
}

function formatDate(date) {
    return date ? frappe.datetime.str_to_user(date) : ''
}

function fmt(value) {
    return Number(value || 0).toLocaleString('en-IN', {
        maximumFractionDigits: 3,
    })
}

const totalRows = computed(() => {
    return reports.value.reduce((sum, report) => sum + (report.rows || []).length, 0)
})

const totalQty = computed(() => {
    return reports.value.reduce((sum, report) => sum + getReportTotal(report.rows), 0)
})

const reportsByDate = computed(() => {
    const groups = new Map()
    for (const report of reports.value) {
        const reportDate = report.date || ''
        if (!groups.has(reportDate)) groups.set(reportDate, [])
        groups.get(reportDate).push(report)
    }
    return [...groups.entries()].map(([date, dateReports]) => ({
        date,
        rows: dateReports,
    }))
})
</script>

<style scoped>
@import "../SewingPlan/SewingPlan.css";

.fpir-root {
    padding: 16px;
}

.fpir-header {
    margin-bottom: 16px;
}

.fpir-title {
    font-size: 25px;
    font-weight: 700;
    margin: 0 0 6px;
    color: #172033;
	text-align: center;
}

.fpir-subtitle {
    margin: 0;
    color: #60708a;
    font-size: 16px;
}

.fpir-filter-row {
    flex-wrap: wrap;
    gap: 1rem 1.5rem;
    max-width: 100%;
}

.fpir-summary-toggle {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 38px;
    margin: 0;
    color: #334155;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
}

.fpir-summary-toggle input {
    width: 16px;
    height: 16px;
    margin: 0;
    accent-color: #1f2937;
}

.fpir-date-section + .fpir-date-section {
    margin-top: 20px;
}

.fpir-date-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 12px;
    margin-bottom: 10px;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    background: #eff6ff;
    color: #1e3a5f;
}

.fpir-date-heading span {
    color: #60708a;
    font-size: 12px;
    font-weight: 600;
}

.fpir-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 38px;
}

.fpir-shot-btn {
    white-space: nowrap;
}

.fpir-state {
    padding: 28px 0;
    color: #60708a;
    font-size: 16px;
}

.fpir-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 8px;
    margin-bottom: 12px;
}

.fpir-card {
    border: 1px solid #d9e2ef;
    border-radius: 12px;
    padding: 10px 12px;
    background: linear-gradient(180deg, #ffffff 0%, #f7fafc 100%);
}

.fpir-card-label {
    color: #60708a;
    font-size: 11px;
    margin-bottom: 4px;
    text-transform: uppercase;
}

.fpir-card-value {
    color: #1f3247;
    font-size: 16px;
    font-weight: 700;
}

.fpir-block {
    margin-bottom: 12px;
}

.fpir-block-header {
    display: flex;
    flex-direction:row;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 2px;
}

.fpir-block-title {
    font-size: 15px;
    font-weight: 700;
    color: #172033;
}

.fpir-block-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    color:  #172033;
    font-size: 15px;
	font-weight: 700;
}

.fpir-table th,
.fpir-table td {
    vertical-align: middle;
}

@media (max-width: 768px) {
    .fpir-root {
        padding: 12px;
    }

    .fpir-title {
        font-size: 26px;
    }

    .fpir-block-header {
        flex-direction: column;
        align-items: flex-start;
    }

    .fpir-filter-row {
        width: 100%;
        min-width: 0;
        align-items: stretch;
    }

    .fpir-filter-row .filter-control {
        flex-basis: 100%;
    }
}
</style>
