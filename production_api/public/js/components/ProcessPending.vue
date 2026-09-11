<template>
    <div ref="root" class="sp-root">
        <div class="sp-header">
            <h3 class="sp-title">Process Pending Report</h3>
        </div>

        <div class="sp-filter-bar">
            <div class="sp-category-input sp-filter-field sp-filter-sm"></div>
            <div class="sp-status-input sp-filter-field sp-filter-sm"></div>
            <div class="sp-process-input sp-filter-field sp-filter-sm"></div>
            <div class="sp-lot-input sp-filter-field sp-filter-lg"></div>
            <div class="sp-item-input sp-filter-field sp-filter-lg"></div>
            <div style="padding-bottom:8px;">
                <button class="sp-btn-show" @click="fetchData">Show Report</button>
            </div>
            <div style="padding-bottom:8px;">
                <button class="sp-btn-paste" @click="openPasteDialog">Paste</button>
            </div>
        </div>

        <div v-if="loading" class="sp-loading">Loading...</div>

        <div v-else-if="rows.length > 0" class="sp-body">
            <div class="sp-summary-bar">
                <div class="summary-item">
                    <span class="summary-label">Total Lots</span>
                    <span class="summary-value">{{ rows.length }}</span>
                </div>
                <div class="summary-divider"></div>
                <div class="summary-item">
                    <span class="summary-label">Total Cutting Received</span>
                    <span class="summary-value summary-value--primary">{{ totalCuttingReceived.toLocaleString() }}</span>
                </div>
                <div class="summary-divider"></div>
                <div class="summary-item">
                    <span class="summary-label">Total Received Qty</span>
                    <span class="summary-value summary-value--green">{{ totalFinishingQty.toLocaleString() }}</span>
                </div>
                <div class="summary-divider"></div>
                <div class="summary-item">
                    <span class="summary-label">Overall Pending Qty</span>
                    <span class="summary-value summary-value--orange">{{ (totalCuttingReceived - totalFinishingQty).toLocaleString() }}</span>
                </div>
                <div class="summary-divider"></div>
                <div class="summary-item">
                    <span class="summary-label">Not Delivered</span>
                    <span class="summary-value summary-value--red">{{ notDelivered.toLocaleString() }}</span>
                </div>
                <div class="summary-divider"></div>
                <div class="summary-item summary-item--lots">
                    <span class="summary-label">Not Delivered Lots ({{ notDeliveredLots.length }})</span>
                    <div class="summary-lot-list">
                        <a
                            v-for="row in notDeliveredLots"
                            :key="row.lot"
                            :href="'/app/lot/' + row.lot"
                            class="summary-lot-link"
                        >{{ row.lot }}</a>
                        <span v-if="notDeliveredLots.length === 0" class="summary-lot-empty">None</span>
                    </div>
                </div>
            </div>

            <div class="table-wrap">
                <table class="sp-table">
                    <thead>
                        <tr>
                            <th class="cell-index">#</th>
                            <th class="text-left cell-item">Item</th>
                            <th class="text-left cell-lot">Lot</th>
                            <th class="cell-cutting-qty">Cutting Qty</th>
                            <th class="cell-cutting-completion">Cutting Completion</th>
                            <th v-for="s in suppliers" :key="s" class="cell-supplier">{{ s }}</th>
                            <th v-if="hasOthers" class="cell-supplier cell-others">Others</th>
                            <th class="cell-not-delivered">Not Delivered</th>
                            <th class="cell-total-received">Total Received Qty</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(row, idx) in rows" :key="row.lot">
                            <td class="cell-dim cell-index">{{ idx + 1 }}</td>
                            <td class="text-left cell-item">{{ row.item }}</td>
                            <td class="text-left cell-lot">
                                <a :href="'/app/lot/' + row.lot" class="sp-link">{{ row.lot }}</a>
                            </td>
                            <td class="cell-cutting-qty">{{ (row.cutting_received_qty || 0).toLocaleString() }}</td>
                            <td class="cell-cutting-completion">{{ formatDate(row.cutting_completion_date) }}</td>
                            <td v-for="s in suppliers" :key="s" class="cell-supplier">
                                <div>{{ supplierVal(row, s) }}</div>
                                <div
                                    v-if="hasSupplierPending(row, s)"
                                    class="pending-days"
                                    :title="supplierPendingTitle(row, s)"
                                >{{ pendingDaysLabel(supplierPendingDays(row, s)) }}</div>
                            </td>
                            <td v-if="hasOthers" class="cell-supplier cell-others">
                                <div>{{ supplierVal(row, 'Others') }}</div>
                                <div
                                    v-if="hasSupplierPending(row, 'Others')"
                                    class="pending-days"
                                    :title="supplierPendingTitle(row, 'Others')"
                                >{{ pendingDaysLabel(supplierPendingDays(row, 'Others')) }}</div>
                            </td>
                            <td class="cell-not-delivered">{{ rowNotDelivered(row).toLocaleString() }}</td>
                            <td class="cell-total cell-total-received">{{ (row.total_qty || 0).toLocaleString() }}</td>
                        </tr>
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colspan="3" class="foot-label">Total</td>
                            <td class="foot-num">{{ totalCuttingReceived.toLocaleString() }}</td>
                            <td></td>
                            <td v-for="s in suppliers" :key="s" class="foot-num cell-supplier">{{ supplierTotal(s).toLocaleString() }}</td>
                            <td v-if="hasOthers" class="foot-num cell-supplier cell-others">{{ supplierTotal('Others').toLocaleString() }}</td>
                            <td class="cell-not-delivered">{{ notDelivered.toLocaleString() }}</td>
                            <td class="foot-grand cell-total-received">{{ totalFinishingQty.toLocaleString() }}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <div v-else class="sp-empty">No records found.</div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { createApp } from 'vue'
import MultiSelectListConverter from './MultiSelectListConverter.vue'

const root = ref(null)
const rows = ref([])
const suppliers = ref([])
const loading = ref(false)
const sample_doc = ref({})

let categoryCtrl = null
let statusCtrl = null
let processCtrl = null
let lotCtrl = null
let itemCtrl = null

onMounted(() => {
    nextTick(() => {
        const el = root.value

        $(el).find(".sp-category-input").html("")
        categoryCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".sp-category-input"),
            df: {
                fieldtype: 'Link',
                fieldname: 'category',
                options: 'Product Category',
                label: 'Product Category',
            },
            doc: sample_doc.value,
            render_input: true,
        })

        $(el).find(".sp-status-input").html("")
        statusCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".sp-status-input"),
            df: {
                fieldtype: 'Select',
                fieldname: 'lot_status',
                options: '\nOpen\nClosed',
                label: 'Lot Status',
                default: 'Open',
                reqd: true,
            },
            doc: sample_doc.value,
            render_input: true,
        })

        $(el).find(".sp-process-input").html("")
        processCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".sp-process-input"),
            df: {
                fieldtype: 'Link',
                fieldname: 'process',
                options: 'Process',
                label: 'Process',
            },
            doc: sample_doc.value,
            render_input: true,
        })

        $(el).find(".sp-lot-input").html("")
        lotCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".sp-lot-input"),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'lot',
                label: 'Lot',
                options: 'Lot',
                get_data: function(txt) {
                    return frappe.db.get_link_options("Lot", txt)
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })

        $(el).find(".sp-item-input").html("")
        itemCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".sp-item-input"),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'item',
                label: 'Item',
                options: 'Item',
                get_data: function(txt) {
                    return frappe.db.get_link_options("Item", txt)
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    })
})

function fetchData() {
    loading.value = true
    frappe.call({
        method: "production_api.utils.get_sewing_progress_report",
        args: {
            process: processCtrl ? processCtrl.get_value() || null : null,
            status: statusCtrl ? statusCtrl.get_value() : null,
            category: categoryCtrl ? categoryCtrl.get_value() || null : null,
            lot_list_val: lotCtrl ? lotCtrl.get_value() : [],
            item_list: itemCtrl ? itemCtrl.get_value() : [],
        },
        freeze: true,
        freeze_message: "Fetching Process Pending...",
        callback(r) {
            const data = r.message || {}
            rows.value = data.rows || []
            suppliers.value = data.suppliers || []
            loading.value = false
        },
        error() {
            loading.value = false
        },
    })
}

function openPasteDialog() {
    let pasteInstance = null
    let d = new frappe.ui.Dialog({
        fields: [
            {
                fieldname: 'pop_up_html',
                fieldtype: 'HTML',
            }
        ],
        primary_action() {
            if (pasteInstance.select_value == 'Item') {
                let updated = itemCtrl.get_value().concat(pasteInstance.list)
                itemCtrl.set_value(updated)
            } else if (pasteInstance.select_value == 'Lot') {
                let updated = lotCtrl.get_value().concat(pasteInstance.list)
                lotCtrl.set_value(updated)
            }
            d.hide()
        },
    })
    d.fields_dict['pop_up_html'].$wrapper.html("")
    let wrapper = d.fields_dict['pop_up_html'].$wrapper.get(0)
    let app = createApp(MultiSelectListConverter, {
        items_list: ['Lot', 'Item'],
    })
    pasteInstance = app.mount(wrapper)
    d.show()
}

const totalCuttingReceived = computed(() => {
    return rows.value.reduce((sum, r) => sum + (r.cutting_received_qty || 0), 0)
})

const totalFinishingQty = computed(() => {
    return rows.value.reduce((sum, r) => sum + (r.total_qty || 0), 0)
})

const notDelivered = computed(() => {
    return rows.value.reduce((sum, row) => sum + rowNotDelivered(row), 0)
})

const notDeliveredLots = computed(() => {
    return rows.value.filter(row => rowNotDelivered(row) > 0)
})

const hasOthers = computed(() => {
    return rows.value.some(r => r.supplier_qty && r.supplier_qty.Others)
})

function supplierVal(row, supplier) {
    const qty = (row.supplier_qty && row.supplier_qty[supplier]) || 0
    return qty ? qty.toLocaleString() : ''
}

function supplierTotal(supplier) {
    return rows.value.reduce((sum, r) => {
        return sum + ((r.supplier_qty && r.supplier_qty[supplier]) || 0)
    }, 0)
}

function hasSupplierPending(row, supplier) {
    return ((row.supplier_qty && row.supplier_qty[supplier]) || 0) !== 0
}

function supplierPendingDays(row, supplier) {
    return row.supplier_pending_days ? row.supplier_pending_days[supplier] : null
}

function supplierPendingTitle(row, supplier) {
    const date = row.supplier_last_dc_dates && row.supplier_last_dc_dates[supplier]
    return date ? `Last DC: ${formatDate(date)}` : 'No submitted DC found'
}

function rowNotDelivered(row) {
    const supplierQty = Object.values(row.supplier_qty || {}).reduce((sum, qty) => {
        return sum + (qty || 0)
    }, 0)
    return (row.cutting_received_qty || 0) - supplierQty - (row.total_qty || 0)
}

function pendingDaysLabel(days) {
    if (days === null || days === undefined) return 'No DC'
    return `${days} ${days === 1 ? 'day' : 'days'} pending`
}

function formatDate(dateStr) {
    if (!dateStr) return ''
    const parts = dateStr.split('-')
    if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`
    return dateStr
}
</script>

<style scoped>
.sp-root {
    padding: 24px 28px;
    color: #374151;
}

.sp-header {
    margin-bottom: 24px;
}
.sp-title {
    font-size: 20px;
    font-weight: 700;
    color: #1f2937;
    margin: 0;
    padding: 0;
}

/* Filter Bar */
.sp-filter-bar {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
}
.sp-filter-field :deep(.frappe-control) {
    margin-bottom: 0 !important;
}
.sp-filter-field :deep(.form-group) {
    margin-bottom: 0 !important;
}
.sp-filter-sm {
    width: 180px;
}
.sp-filter-lg {
    width: 240px;
}
.sp-btn-show {
    height: 30px;
    padding: 0 18px;
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    background: #2563eb;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
}
.sp-btn-show:hover {
    background: #1d4ed8;
}
.sp-btn-paste {
    height: 30px;
    padding: 0 18px;
    font-size: 12px;
    font-weight: 600;
    color: #374151;
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
}
.sp-btn-paste:hover {
    background: #e5e7eb;
}

.sp-loading {
    text-align: center;
    color: #9ca3af;
    padding: 60px 0;
    font-size: 14px;
    font-weight: 500;
}

/* Summary Bar */
.sp-summary-bar {
    display: flex;
    align-items: center;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 14px 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.summary-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.summary-item--lots {
    flex: 1;
    min-width: 280px;
}
.summary-label {
    font-size: 12.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9ca3af;
}
.summary-value {
    font-size: 24px;
    font-weight: 700;
    color: #374151;
}
.summary-value--primary {
    color: #2563eb;
}
.summary-value--green {
    color: #059669;
}
.summary-value--orange {
    color: #d97706;
}
.summary-value--red {
    color: #dc2626;
}
.summary-lot-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 6px;
    margin-top: 4px;
}
.summary-lot-link {
    padding: 2px 7px;
    border-radius: 10px;
    background: #fef2f2;
    color: #dc2626;
    font-size: 12px;
    font-weight: 600;
    line-height: 1.4;
    text-decoration: none;
    white-space: nowrap;
}
.summary-lot-link:hover {
    background: #fee2e2;
    color: #b91c1c;
    text-decoration: none;
}
.summary-lot-empty {
    color: #9ca3af;
    font-size: 13px;
}
.summary-divider {
    width: 1px;
    height: 32px;
    background: #e5e7eb;
    margin: 0 24px;
}

/* Table */
.table-wrap {
    overflow: auto;
    max-height: 75vh;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
}
.sp-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}
.sp-table thead th {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #6b7280;
    background: #f9fafb;
    padding: 10px 12px;
    border-bottom: 2px solid #d1d5db;
    text-align: center;
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 2;
}
.sp-table thead th.text-left {
    text-align: left;
}
.sp-table tbody td {
    padding: 9px 12px;
    text-align: center;
    vertical-align: middle;
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
}
.sp-table tbody td.text-left {
    text-align: left;
}
.sp-table tbody tr:hover {
    background: #f9fafb;
}
.sp-table tbody tr:nth-child(even) {
    background: #fafbfc;
}
.sp-table tbody tr:nth-child(even):hover {
    background: #f3f4f6;
}
.cell-dim { color: #9ca3af; }
.cell-index {
    width: 40px;
    min-width: 40px;
    max-width: 40px;
    padding-left: 6px !important;
    padding-right: 6px !important;
}
.cell-total {
    font-weight: 700;
    color: #1f2937;
    background: #f9fafb;
}
.cell-item {
    width: 250px;
    max-width: 250px;
}
.sp-table tbody td.cell-item {
    line-height: 1.3;
    white-space: normal;
}
.cell-lot {
    width: 115px;
    max-width: 115px;
}
.cell-cutting-qty {
    width: 95px;
    max-width: 95px;
}
.cell-cutting-completion {
    width: 100px;
    max-width: 100px;
}
.sp-table thead th.cell-cutting-qty,
.sp-table thead th.cell-cutting-completion {
    white-space: normal;
}
.cell-supplier {
    color: #4b5563;
    min-width: 125px;
}
.cell-others {
    min-width: 75px;
    width: 75px;
    max-width: 75px;
}
.cell-not-delivered {
    color: #dc2626;
    font-weight: 700;
    background: #fef2f2;
    width: 90px;
    max-width: 90px;
}
.pending-days {
    margin-top: 2px;
    color: #b45309;
    font-size: 10px;
    font-weight: 600;
    line-height: 1.2;
    white-space: nowrap;
}
.cell-total-received {
    width: 90px;
    max-width: 90px;
}
.sp-table thead th.cell-not-delivered,
.sp-table thead th.cell-total-received {
    white-space: normal;
}
.sp-table thead th.cell-supplier {
    font-size: 12px;
    word-break: break-word;
    white-space: normal;
}
.sp-link {
    color: #2563eb;
    font-weight: 600;
    text-decoration: none;
    font-size: 14px;
}
.sp-link:hover {
    color: #1d4ed8;
    text-decoration: underline;
}

/* Footer */
.sp-table tfoot td {
    padding: 10px 12px;
    font-weight: 700;
    font-size: 14px;
    border-top: 2px solid #d1d5db;
    background: #f9fafb;
    text-align: center;
    white-space: nowrap;
    color: #374151;
}
.foot-label {
    text-align: right !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 13px;
    color: #6b7280;
}
.foot-num {
    font-weight: 700;
    color: #374151;
}
.foot-grand {
    font-weight: 800;
    color: #1f2937;
    background: #eef2ff;
}
.sp-table tfoot td.cell-not-delivered {
    color: #dc2626;
    background: #fef2f2;
}

.sp-empty {
    text-align: center;
    color: #9ca3af;
    padding: 60px 0;
    font-size: 14px;
    font-weight: 500;
}
</style>
