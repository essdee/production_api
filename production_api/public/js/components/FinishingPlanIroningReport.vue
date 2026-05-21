<template>
	<div ref="report_section">
    <div ref="root" class="fpir-root" >
        <div class="fpir-header">
            <h3 class="fpir-title">Finishing Plan Ironing DPR</h3>
        </div>

        <div class="fpir-filters" >
            <div class="fpir-filter">
                <div class="fpir-control fpir-date-input"></div>
            </div>
            <div class="fpir-filter">
                <div class="fpir-control fpir-lot-input"></div>
            </div>
            <div class="fpir-filter">
                <div class="fpir-control fpir-item-input"></div>
            </div>
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

            <div
                v-for="report in reports"
                :key="report.lot"
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

let dateCtrl = null
let lotCtrl = null
let itemCtrl = null
let dcCtrl = null

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
                options: 'Item',
                get_data: function(txt) {
                    return frappe.db.get_link_options('Item', txt)
                },
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
    const selectedLots = lotCtrl ? normalizeMultiValue(lotCtrl.get_value()) : []
    const selectedItems = itemCtrl ? normalizeMultiValue(itemCtrl.get_value()) : []

    if (!selectedDate && !selectedDc) {
        frappe.show_alert({
            message: 'Select any filter before clicking the Show Report button',
            indicator: 'orange',
        })
        return
    }
	
    loading.value = true
    frappe.call({
        method: 'production_api.utils.dc_dpr_report',
        args: {
            date: selectedDate,
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
</script>

<style scoped>
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

.fpir-filters {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    align-items: end;
    margin-bottom: 20px;
}

.fpir-actions {
    display: flex;
    align-items: end;
    gap: 8px;
    height: 100%;
	padding-bottom: 8px;
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
}
</style>
