<template>
    <div class="dpr-tab">
        <div class="sp-filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">{{ summary_mode ? 'Filter by Date Range' : 'Filter by Date' }}</span>
                </div>
                <div v-show="!summary_mode" class="filter-control">
                    <div ref="date_filter_wrapper"></div>
                </div>
                <div v-show="summary_mode" class="filter-control">
                    <div ref="from_date_filter_wrapper"></div>
                </div>
                <div v-show="summary_mode" class="filter-control">
                    <div ref="to_date_filter_wrapper"></div>
                </div>
                <div class="filter-control">
                     <div ref="ws_filter_wrapper"></div>
                </div>
                <div class="filter-control">
                      <div ref="input_type_filter_wrapper"></div>
                </div>
                <div class="filter-actions">
                    <button
                        type="button"
                        class="btn btn-primary fetch-button"
                        :disabled="loading"
                        :aria-busy="loading"
                        @click="fetchDPRData(true)"
                    >
                        <span
                            v-if="loading"
                            class="spinner-border spinner-border-sm"
                            aria-hidden="true"
                        ></span>
                        {{ loading ? 'Loading...' : 'Fetch' }}
                    </button>
                    <label class="summary-toggle">
                        <input type="checkbox" v-model="summary_mode" />
                        <span>Summary</span>
                    </label>
                </div>
            </div>
        </div>
        <div v-if="reports.length > 0">
            <section v-for="report in reports" :key="report.date" class="report-date-section">
                <div v-for="header in report.headers" :key="`${report.date}-${header}`">
                    <div v-if="report.dpr_data.hasOwnProperty(header)" :ref="el => setSectionRef(el, report.date, header)">
                        <div class="section-header">
                            <div class="section-title-block">
                                <span class="section-title">Daily Production Report</span>
                                <span class="section-divider">|</span>
                                <span class="section-title">{{ frappe.datetime.str_to_user(report.date) }}</span>
                                <span class="section-divider">|</span>
                                <span class="section-title">{{ header }}</span>
                            </div>
                            <div class="section-actions">
                                <button class="copy-btn" @click="copyToClipboard(report.date, header)" :disabled="copyingHeader === sectionKey(report.date, header)" title="Copy to Clipboard">
                                    <template v-if="copyingHeader === sectionKey(report.date, header)">
                                        <svg class="copy-icon spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                                        </svg>
                                        Copying...
                                    </template>
                                    <template v-else>
                                        <svg class="copy-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                                        </svg>
                                        Copy
                                    </template>
                                </button>
                                <div class="section-total-block">
                                    <span class="total-label">Total Qty</span>
                                    <span class="total-value">{{ getHeaderTotal(report.dpr_data, header) }}</span>
                                </div>
                            </div>
                        </div>
                        <div class="table-wrapper no-scrollbar">
                            <table class="data-table table-with-gap" v-for="lot in Object.keys(report.dpr_data[header])" :key="lot">
                            <thead>
                                <tr class="header-row">
                                    <th class="index-col">#</th>
                                    <th class="lot-col">Lot</th>
                                    <th class="item-col">Item</th>
                                    <th class="colourname-col">Colour</th>
                                    <th class="line-col">Line</th>
                                    <th class="type-col">Type</th>
                                    <th v-if="report.dpr_data[header][lot]['is_set_item']" class="part-col">
                                        {{ report.dpr_data[header][lot]['set_attr'] }}
                                    </th>
                                    <th v-for="size in report.dpr_data[header][lot]['primary_values']" :key="size"
                                        class="size-col">
                                        {{ size }}
                                    </th>
                                    <th class="remarks-col">Remarks</th>
                                    <th class="total-col">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template v-for="(ws, idx) in Object.keys(report.dpr_data[header][lot]['details'])"
                                    :key="ws">
                                    <template v-for="(received_type, idx) in Object.keys(report.dpr_data[header][lot]['details'][ws])"
                                        :key="received_type">
                                        <tr v-for="colour in Object.keys(report.dpr_data[header][lot]['details'][ws][received_type])" :key="colour" class="data-row">
                                            <td class="index-cell">{{ idx + 1 }}</td>
                                            <td class="lot-cell">{{ lot }}</td>
                                            <td class="item-cell">{{ report.dpr_data[header][lot]['item'] }}</td>
                                            <td class="colour-cell">
                                                <span class="colour-badge">{{ colour.split("@")[0] }}</span>
                                            </td>
                                            <td class="colour-cell">{{ ws }}</td>
                                            <td class="colour-cell">
                                                <span class="colour-badge">{{ received_type }}</span>
                                            </td>
                                            <td v-if="report.dpr_data[header][lot]['is_set_item']" class="part-cell">
                                                <span class="part-pill">
                                                    {{ report.dpr_data[header][lot]['details'][ws][received_type][colour]['part']}}
                                                </span>
                                            </td>
                                            <td v-for="size in report.dpr_data[header][lot]['primary_values']" :key="size"
                                                class="size-cell">
                                                {{ report.dpr_data[header][lot]['details'][ws][received_type][colour]['values'][size] }}
                                            </td>
                                            <td class="remarks-cell">
                                                <input
                                                    type="text"
                                                    class="remarks-input"
                                                    :value="remarks[rowKey(report.date, header, lot, ws, received_type, colour)] || ''"
                                                    @input="remarks[rowKey(report.date, header, lot, ws, received_type, colour)] = $event.target.value"
                                                    placeholder="Remarks"
                                                />
                                            </td>
                                            <td class="total-cell">
                                                <span class="total-val">
                                                    {{ report.dpr_data[header][lot]['details'][ws][received_type][colour]['total'] }}
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
            </section>
        </div>
        <div v-else class="empty-state">
            <p>{{ summary_mode ? 'Select a date range to view the report' : 'Select a Date to view the report' }}</p>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as htmlToImage from 'html-to-image'
import { buildDPRRequest, normalizeDPRReports } from './dpr_summary_utils.mjs'
import { createReportLoadingTracker } from './dpr_loading_state.mjs'

const props = defineProps({
    selected_supplier: {
        type: String,
        required: true
    },
    refresh_counter: {
        type: Number,
        default: 0
    }
})

const date_filter_wrapper = ref(null)
const from_date_filter_wrapper = ref(null)
const to_date_filter_wrapper = ref(null)
const ws_filter_wrapper = ref(null)
const input_type_filter_wrapper = ref(null)
let date_filter_control = null
let from_date_filter_control = null
let to_date_filter_control = null
let ws_value = null
let input_type_control = null
const copyingHeader = ref(null)
const loading = ref(false)
const loadingTracker = createReportLoadingTracker((value) => {
    loading.value = value
})

const summary_mode = ref(false)
const selected_date = ref(null)
const from_date = ref(null)
const to_date = ref(null)
const selected_ws = ref(null)
const selected_input_type = ref(null)
const reports = ref([])
const sectionRefs = ref({})
const remarks = ref({})

const sectionKey = (date, header) => `${date}|${header}`
const rowKey = (date, header, lot, ws, received_type, colour) =>
    `${date}|${header}|${lot}|${ws}|${received_type}|${colour}`

const setSectionRef = (el, date, header) => {
    if (el) {
        sectionRefs.value[sectionKey(date, header)] = el
    }
}

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

    $(from_date_filter_wrapper.value).empty()
    from_date_filter_control = frappe.ui.form.make_control({
        parent: $(from_date_filter_wrapper.value),
        df: {
            fieldtype: 'Date',
            fieldname: 'from_date',
            label: 'From Date',
            default: from_date.value,
            placeholder: 'From Date',
            change: () => {
                from_date.value = from_date_filter_control.get_value()
            }
        },
        render_input: true
    })

    $(to_date_filter_wrapper.value).empty()
    to_date_filter_control = frappe.ui.form.make_control({
        parent: $(to_date_filter_wrapper.value),
        df: {
            fieldtype: 'Date',
            fieldname: 'to_date',
            label: 'To Date',
            default: to_date.value,
            placeholder: 'To Date',
            change: () => {
                to_date.value = to_date_filter_control.get_value()
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

    if (!input_type_filter_wrapper.value) return

    $(input_type_filter_wrapper.value).empty()

    input_type_control = frappe.ui.form.make_control({
        parent: $(input_type_filter_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'input_type',
            label: 'Input Type',
            options: 'Sewing Plan Input Type',
            placeholder: "Input Type",
            change: () => {
                selected_input_type.value = input_type_control.get_value()
            },
            get_query: () => {
                return {
                    filters: {
                        'name': ['!=', 'Order Qty']
                    }
                }
            }
        },
        render_input: true
    })
}

const showPendingFI = (pending) => {
    if (pending.length === 0) return
    const byLot = {}
    pending.forEach(p => {
        if (!byLot[p.lot]) byLot[p.lot] = []
        const label = p.part ? `${p.colour} — ${p.part}` : p.colour
        byLot[p.lot].push(label)
    })
    const pillStyle = 'display:inline-block;padding:4px 10px;margin:3px 4px 3px 0;background:#fff7ed;border:1px solid #fdba74;color:#9a3412;border-radius:9999px;font-size:12px;font-weight:600;white-space:nowrap;'
    const lotStyle = 'font-weight:700;color:#111827;margin-right:10px;min-width:110px;display:inline-block;'
    const rowStyle = 'display:flex;align-items:flex-start;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid #f1f5f9;'
    const body = Object.keys(byLot).map(lot => {
        const pills = byLot[lot].map(l => `<span style="${pillStyle}">${frappe.utils.escape_html(l)}</span>`).join('')
        return `<div style="${rowStyle}"><span style="${lotStyle}">${frappe.utils.escape_html(lot)}</span><div style="flex:1;">${pills}</div></div>`
    }).join('')
    const html = `
        <p>The following Lot / Colour combinations are hidden from the DPR because their FI date is not yet updated. Please update them in the <b>FI Updates</b> tab.</p>
        <div style="margin-top:8px;">${body}</div>`
    frappe.msgprint({ title: __('FI date not updated'), message: html, indicator: 'orange' })
}

const fetchDPRData = (showValidation = false) => {
    const request = buildDPRRequest({
        summaryMode: summary_mode.value,
        supplier: props.selected_supplier,
        selectedDate: selected_date.value,
        fromDate: from_date.value,
        toDate: to_date.value,
        workStation: selected_ws.value,
        inputType: selected_input_type.value,
    })
    if (request.error) {
        if (showValidation) {
            frappe.msgprint(__(request.error))
        }
        return
    }
    loadingTracker.start()
    frappe.call({
        method: request.method,
        args: request.args,
        callback: (r) => {
            const response = r.message || {}
            remarks.value = {}
            sectionRefs.value = {}
            reports.value = normalizeDPRReports({
                summaryMode: summary_mode.value,
                selectedDate: selected_date.value,
                response,
            })
            showPendingFI(response.pending_fi || [])
        },
        always: () => {
            loadingTracker.finish()
        },
    })
}

onMounted(() => {
    initFilter()
})

watch(summary_mode, () => {
    reports.value = []
    remarks.value = {}
    sectionRefs.value = {}
})

watch(
    () => [
        props.selected_supplier,
        summary_mode.value,
        selected_date.value,
        from_date.value,
        to_date.value,
        selected_ws.value,
        selected_input_type.value,
        props.refresh_counter,
    ],
    () => fetchDPRData(false),
)

const getHeaderTotal = (reportData, header) => {
    if (!reportData[header]) return 0
    let total = 0
    for (const lot of Object.keys(reportData[header])) {
        const lotData = reportData[header][lot]
        if (lotData.details) {
            for (const ws of Object.keys(lotData.details)) {
                for (const receivedType of Object.keys(lotData.details[ws])) {
                    for (const colour of Object.keys(lotData.details[ws][receivedType])) {
                        total += lotData.details[ws][receivedType][colour].total || 0
                    }
                }
            }
        }
    }
    return total
}

const copyToClipboard = async (date, header) => {
    const key = sectionKey(date, header)
    const sectionEl = sectionRefs.value[key]
    copyingHeader.value = key
    if (!sectionEl) {
        console.log(`No element found for header: ${header}`)
        copyingHeader.value = null
        return
    }

    try {
        if (document.activeElement && typeof document.activeElement.blur === 'function') {
            document.activeElement.blur()
        }
        sectionEl.querySelectorAll('input.remarks-input').forEach(inp => {
            inp.setAttribute('value', inp.value)
        })
        const blob = await htmlToImage.toBlob(sectionEl, {
            backgroundColor: '#ffffff',
            pixelRatio: 1
        })
        await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob })
        ])
        copyingHeader.value = null
        frappe.show_alert({ message: `${frappe.datetime.str_to_user(date)} - ${header} copied`, indicator: 'green' })
    } catch (err) {
        copyingHeader.value = null
        frappe.show_alert({ message: 'Copy failed', indicator: 'red' })
    }
}

</script>
    
<style scoped>
@import "../SewingPlan.css";

.dpr-tab {
    padding: 1rem;
}

.filter-card {
    max-width: 100%;
    flex-wrap: wrap;
    gap: 1rem;
}

.filter-actions,
.summary-toggle {
    display: flex;
    align-items: center;
}

.filter-actions {
    gap: 0.85rem;
}

.fetch-button {
    min-width: 104px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    border-radius: 12px;
    font-weight: 700;
}

.summary-toggle {
    gap: 0.45rem;
    margin: 0;
    color: #475569;
    font-size: 0.875rem;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
}

.summary-toggle input {
    width: 16px;
    height: 16px;
    margin: 0;
    accent-color: #1a73e8;
}

.report-date-section + .report-date-section {
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 1px solid #e2e8f0;
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

.copy-btn {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}


.copy-btn:hover:not(:disabled) {
    background: #1557b0;
    transform: translateY(-1px);
}

.copy-btn:disabled {
    background: #94a3b8;
    cursor: not-allowed;
}

.copy-icon {
    width: 1rem;
    height: 1rem;
}

.spin {
    animation: spin 1s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1rem 1.5rem;
    margin-bottom: 1rem;
}

.section-title-block {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
}

.section-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.section-title {
    font-size: 1.125rem;
    font-weight: 700;
    color: #1e293b;
    margin: 0;
    white-space: nowrap;
}

.section-divider {
    color: #cbd5e1;
    font-size: 1.125rem;
    font-weight: 300;
}

.section-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.section-total-block {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.25rem;
}

.total-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.total-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1a73e8;
}

.colour-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: #1e293b;
    background: #fdfdfd;
    vertical-align: middle;
    text-align: center;
}

.part-cell {
    vertical-align: middle;
    text-align: center;
}

.table-with-gap {
    margin-bottom: 24px;
}

.table-with-gap:last-child {
    margin-bottom: 0;
}

/* Fixed-layout so every per-Lot table aligns column-for-column.
   The mandatory columns get explicit widths; the size matrix absorbs
   the per-Lot difference, so Lot/Item/Colour/Line/Type stay aligned on
   the left and Remarks/Total stay aligned on the right across all tables. */
.data-table {
    table-layout: fixed;
}

.index-col { width: 36px; }
.lot-col { width: 120px; }
.item-col { width: 200px; }
.colourname-col { width: 100px; }
.line-col { width: 130px; }
.type-col { width: 100px; }
.part-col { width: 110px; }
.total-col { width: 80px; }

/* Colour / Line / Type: wrap a long value to a second line instead of letting
   nowrap text bleed into the next column at these reduced widths. */
.colour-cell {
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: break-word;
}

/* Lot fits on one line at 120px */
.lot-cell {
    padding: 10px;
    border: 1px solid #e2e8f0;
    color: #334155;
    font-weight: 500;
    text-align: center;
    white-space: nowrap;
}

/* Item names can be long → allow wrapping inside the fixed 200px column */
.item-cell {
    padding: 10px;
    border: 1px solid #e2e8f0;
    color: #334155;
    font-weight: 500;
    text-align: center;
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: break-word;
}

.remarks-col {
    width: 140px;
}

.remarks-cell {
    padding: 6px 8px;
    border: 1px solid #e2e8f0;
    text-align: center;
    vertical-align: middle;
}

.remarks-input {
    width: 100%;
    min-width: 120px;
    padding: 6px 8px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #ffffff;
    color: #334155;
    font-size: 0.875rem;
    font-weight: 500;
    outline: none;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.remarks-input::placeholder {
    color: #cbd5e1;
    font-weight: 400;
}

.remarks-input:hover {
    border-color: #cbd5e1;
}

.remarks-input:focus {
    border-color: #1a73e8;
    box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.12);
}
</style>
