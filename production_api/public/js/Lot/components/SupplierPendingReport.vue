<template>
    <div ref="root" class="supplier-pending-report">
        <section class="report-toolbar">
            <div class="supplier-input control-slot"></div>
            <div class="process-input control-slot"></div>
            <button class="btn btn-primary action-button" :disabled="loading" @click="showReport">
                <span v-if="loading" class="spinner-border spinner-border-sm" aria-hidden="true"></span>
                {{ loading ? 'Loading...' : 'Show Report' }}
            </button>
            <button class="btn btn-success action-button" :disabled="loading || copying || !hasRows" @click="copyReport">
                {{ copying ? 'Copying...' : 'Copy' }}
            </button>
        </section>

        <section v-if="!hasFetched && !loading" class="report-state">
            Select a Supplier and Process, then click Show Report.
        </section>
        <section v-else-if="loading && !hasFetched" class="report-state">
            Fetching supplier pending quantities...
        </section>
        <section v-else-if="hasFetched && !hasRows" class="report-state empty-state">
            No pending quantities were found for the selected Supplier and Process.
        </section>

        <div v-if="hasRows" ref="reportContent" class="report-content">
            <header class="report-header">
                <div>
                    <p class="report-kicker">Supplier Pending Report</p>
                    <h2>{{ report.supplier_name || report.supplier }}</h2>
                </div>
            </header>

            <section v-for="item in report.items" :key="item.item" class="item-section">
                <h3 class="item-title"><span>Item</span>{{ item.item }}</h3>

                <article v-for="lot in item.lots" :key="lot.lot" class="lot-section">
                    <div class="lot-heading">
                        <span>Lot</span>
                        <strong>{{ lot.lot }}</strong>
                        <small>{{ lot.rows.length }} pending {{ lot.rows.length === 1 ? 'row' : 'rows' }}</small>
                    </div>

                    <div class="table-scroll">
                        <table class="report-table">
                            <thead>
                                <tr>
                                    <th class="serial-column">S.No</th>
                                    <th class="name-column">Colour</th>
                                    <th v-if="lot.is_set_item" class="part-column">{{ lot.set_attr || 'Part' }}</th>
                                    <th class="type-column">Type</th>
                                    <th v-for="size in lot.primary_values" :key="size">{{ size }}</th>
                                    <th>Total</th>
                                    <th class="date-column">First Date</th>
                                    <th class="date-column">Last Date</th>
                                    <th class="diff-column">Diff</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template v-for="(row, rowIndex) in lot.rows" :key="`${row.colour}-${row.part || ''}`">
                                    <tr>
                                        <td rowspan="3" class="row-identity">{{ rowIndex + 1 }}</td>
                                        <td rowspan="3" class="row-identity">{{ row.colour }}</td>
                                        <td v-if="lot.is_set_item" rowspan="3" class="row-identity">{{ row.part || '-' }}</td>
                                        <td class="type-cell">Delivered</td>
                                        <td v-for="size in lot.primary_values" :key="size">{{ quantity(row.values[size]?.delivered) }}</td>
                                        <td class="total-cell">{{ quantity(row.totals.delivered) }}</td>
                                        <td>{{ reportDate(row.dates.first_dc_date) }}</td>
                                        <td>{{ reportDate(row.dates.last_dc_date) }}</td>
                                        <td rowspan="3" class="row-identity">{{ row.dates.diff_days ?? '-' }}</td>
                                    </tr>
                                    <tr>
                                        <td class="type-cell">Received</td>
                                        <td v-for="size in lot.primary_values" :key="size">
                                            {{ quantity(row.values[size]?.received) }}
                                        </td>
                                        <td class="total-cell">{{ quantity(row.totals.received) }}</td>
                                        <td>{{ reportDate(row.dates.first_grn_date) }}</td>
                                        <td>{{ reportDate(row.dates.last_grn_date) }}</td>
                                    </tr>
                                    <tr class="difference-row">
                                        <td class="type-cell">Difference</td>
                                        <td
                                            v-for="size in lot.primary_values"
                                            :key="size"
                                            :class="differenceClass(row.values[size]?.received, row.values[size]?.delivered)"
                                        >
                                            {{ quantity(row.values[size]?.difference) }}
                                        </td>
                                        <td :class="['total-cell', differenceClass(row.totals.received, row.totals.delivered)]">
                                            {{ quantity(row.totals.difference) }}
                                        </td>
                                        <td></td>
                                        <td></td>
                                    </tr>
                                </template>

                                <template v-for="total in lot.totals" :key="`total-${total.part || 'item'}`">
                                    <tr class="summary-row">
                                        <td rowspan="3"></td>
                                        <td rowspan="3" class="total-label">Total</td>
                                        <td v-if="lot.is_set_item" rowspan="3" class="total-label">{{ total.part || '-' }}</td>
                                        <td class="type-cell">Delivered</td>
                                        <td v-for="size in lot.primary_values" :key="size">{{ quantity(total.values[size]?.delivered) }}</td>
                                        <td class="total-cell">{{ quantity(total.totals.delivered) }}</td>
                                        <td></td>
                                        <td></td>
                                        <td rowspan="3"></td>
                                    </tr>
                                    <tr class="summary-row">
                                        <td class="type-cell">Received</td>
                                        <td v-for="size in lot.primary_values" :key="size">{{ quantity(total.values[size]?.received) }}</td>
                                        <td class="total-cell">{{ quantity(total.totals.received) }}</td>
                                        <td></td>
                                        <td></td>
                                    </tr>
                                    <tr class="summary-row difference-row">
                                        <td class="type-cell">Difference</td>
                                        <td
                                            v-for="size in lot.primary_values"
                                            :key="size"
                                            :class="differenceClass(total.values[size]?.received, total.values[size]?.delivered)"
                                        >
                                            {{ quantity(total.values[size]?.difference) }}
                                        </td>
                                        <td :class="['total-cell', differenceClass(total.totals.received, total.totals.delivered)]">
                                            {{ quantity(total.totals.difference) }}
                                        </td>
                                        <td></td>
                                        <td></td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>
                </article>
            </section>
        </div>
    </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { copyElementAsImage } from '../../copyElementAsImage'
import {
    buildSupplierPendingRequest,
    createLoadingTracker,
    differenceTone,
    normalizeSupplierPendingResponse,
} from './supplier_pending_report_utils.mjs'

const root = ref(null)
const reportContent = ref(null)
const report = ref(normalizeSupplierPendingResponse())
const loading = ref(false)
const copying = ref(false)
const hasFetched = ref(false)
const controlDocument = ref({})

let supplierControl = null
let processControl = null

const hasRows = computed(() => report.value.items.length > 0)
const loadingTracker = createLoadingTracker((value) => {
    loading.value = value
})

onMounted(() => {
    const element = root.value
    supplierControl = frappe.ui.form.make_control({
        parent: $(element).find('.supplier-input'),
        df: {
            fieldname: 'supplier',
            fieldtype: 'Link',
            options: 'Supplier',
            label: 'Supplier',
            reqd: true,
        },
        doc: controlDocument.value,
        render_input: true,
    })
    processControl = frappe.ui.form.make_control({
        parent: $(element).find('.process-input'),
        df: {
            fieldname: 'process',
            fieldtype: 'Link',
            options: 'Process',
            label: 'Process',
            reqd: true,
        },
        doc: controlDocument.value,
        render_input: true,
    })
})

function showReport() {
    const request = buildSupplierPendingRequest({
        supplier: supplierControl?.get_value(),
        process: processControl?.get_value(),
    })
    if (request.error) {
        frappe.msgprint(request.error)
        return
    }

    hasFetched.value = false
    loadingTracker.start()
    frappe.call({
        method: request.method,
        args: request.args,
        callback(response) {
            report.value = normalizeSupplierPendingResponse(response.message)
            hasFetched.value = true
        },
        always() {
            loadingTracker.finish()
        },
    })
}

async function copyReport() {
    if (copying.value || !reportContent.value) return
    copying.value = true
    try {
        await copyElementAsImage(reportContent.value)
        frappe.show_alert({ message: 'Copied to clipboard', indicator: 'green' })
    } catch (error) {
        frappe.show_alert({ message: 'Copy failed', indicator: 'red' })
    } finally {
        copying.value = false
    }
}

function reportDate(value) {
    return value ? frappe.datetime.str_to_user(value) : '-'
}

function quantity(value) {
    const numericValue = Number(value || 0)
    return numericValue.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function differenceClass(received, delivered) {
    return `difference-${differenceTone(received, delivered)}`
}
</script>

<style scoped>
.supplier-pending-report {
    padding: 16px;
    color: var(--text-color);
}

.report-toolbar {
    display: grid;
    grid-template-columns: minmax(220px, 360px) minmax(220px, 360px) auto auto;
    gap: 12px;
    align-items: end;
    justify-content: start;
    margin-bottom: 18px;
    padding: 14px;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

.control-slot {
    min-width: 0;
}

.action-button {
    min-width: 108px;
    height: 30px;
    margin-bottom: 1px;
}

.spinner-border-sm {
    margin-right: 5px;
}

.report-state {
    display: grid;
    min-height: 220px;
    place-items: center;
    padding: 32px;
    color: var(--text-muted);
    background: var(--card-bg);
    border: 1px dashed var(--border-color);
    border-radius: 8px;
    text-align: center;
}

.empty-state {
    color: var(--text-light);
}

.report-content {
    padding: 18px;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

.report-header {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-end;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border-color);
}

.report-kicker,
.item-title span,
.lot-heading span {
    margin: 0;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.report-header h2 {
    margin: 2px 0 0;
    font-size: 20px;
}

.item-section + .item-section {
    margin-top: 24px;
}

.item-title {
    display: flex;
    gap: 10px;
    align-items: baseline;
    margin: 0 0 9px;
    font-size: 17px;
}

.lot-section {
    overflow: hidden;
    margin-bottom: 14px;
    border: 1px solid var(--border-color);
    border-radius: 7px;
}

.lot-heading {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 9px 11px;
    background: var(--subtle-fg);
}

.lot-heading small {
    margin-left: auto;
    color: var(--text-muted);
}

.table-scroll {
    overflow-x: auto;
}

.report-table {
    width: 100%;
    min-width: 920px;
    border-collapse: collapse;
    font-size: 12px;
}

.report-table th,
.report-table td {
    padding: 7px 8px;
    border: 1px solid var(--border-color);
    text-align: center;
    white-space: nowrap;
}

.report-table th {
    color: var(--text-muted);
    background: var(--control-bg);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

.report-table tr > :first-child {
    border-left: 0;
}

.report-table tr > :last-child {
    border-right: 0;
}

.serial-column {
    width: 48px;
}

.name-column {
    min-width: 130px;
}

.part-column,
.type-column {
    min-width: 90px;
}

.date-column {
    min-width: 100px;
}

.diff-column {
    width: 65px;
}

.row-identity,
.total-cell,
.total-label,
.type-cell {
    font-weight: 600;
}

.difference-row td {
    border-bottom-width: 2px;
}

.summary-row td {
    background: #fff4d6;
}

.difference-positive {
    background: #ccffda !important;
}

.difference-negative {
    background: #ffa1a7 !important;
}

.difference-zero {
    background: #ffe7a6 !important;
}

@media (max-width: 900px) {
    .report-toolbar {
        grid-template-columns: 1fr 1fr;
    }

    .report-header {
        align-items: flex-start;
        flex-direction: column;
    }

}

@media (max-width: 600px) {
    .report-toolbar {
        grid-template-columns: 1fr;
    }

    .action-button {
        width: 100%;
    }
}
</style>
