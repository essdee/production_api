<template>
    <div ref="root" class="wop-root">
        <div class="wop-header">
            <h3 class="wop-title">Work Order Pending Report</h3>
        </div>

        <div class="wop-filters">
            <div class="wop-filter">
                <div class="wop-control wop-lot-input"></div>
            </div>
            <div class="wop-filter">
                <div class="wop-control wop-process-input"></div>
            </div>
            <div class="wop-filter">
                <div class="wop-control wop-supplier-input"></div>
            </div>
            <div class="wop-filter">
                <div class="wop-control wop-item-input"></div>
            </div>
			 <div class="wop-filter">
                <div class="wop-control wop-status-input"></div>
            </div>
            <div class="wop-actions">
                <button class="btn btn-primary" :disabled="loading" @click="loadReport">
                    {{ loading ? 'Loading...' : 'Show Report' }}
                </button>
            </div>
        </div>

        <div v-if="loading" class="wop-state">Loading report...</div>

        <div v-else-if="rows.length" class="wop-body">
            <div class="wop-summary">
                <div class="wop-card">
                    <div class="wop-card-label">Rows</div>
                    <div class="wop-card-value">{{ rows.length }}</div>
                </div>
                <div class="wop-card">
                    <div class="wop-card-label">Delivered</div>
                    <div class="wop-card-value">{{ totalDelivered }}</div>
                </div>
                <div class="wop-card">
                    <div class="wop-card-label">Received</div>
                    <div class="wop-card-value">{{ totalReceived }}</div>
                </div>
                <div class="wop-card">
                    <div class="wop-card-label">Pending</div>
                    <div class="wop-card-value">{{ totalPending }}</div>
                </div>
            </div>

            <div class="table-responsive">
                <table class="table table-bordered table-sm wop-table">
                    <thead>
                        <tr>
                            <th>No</th>
                            <th>Lot</th>
                            <th>Process</th>
                            <th>Supplier</th>
                            <th>Item</th>
                            <th class="text-end">Delivered Qty</th>
                            <th class="text-end">Received Qty</th>
                            <th class="text-end">Pending Qty</th>
							<th>Summary</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="row in rows" :key="`${row.lot}-${row.process_name}-${row.supplier}-${row.item_name || ''}`" class="wop-row" @click="openRowDetails(row)">
                            <td>{{ rows.indexOf(row) + 1 }}</td>
                            <td>{{ row.lot }}</td>
                            <td>{{ row.process_name }}</td>
                            <td>{{ row.supplier_name }}</td>
                            <td>{{ row.item_name }}</td>
                            <td class="text-end">{{ fmt(row.delivered_qty) }}</td>
                            <td class="text-end">{{ fmt(row.received_qty) }}</td>
                            <td if  class="text-end" :class="pendingClass(row.pending_quantity)">{{ fmt(row.pending_quantity) }}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary" @click.stop="openRowDetails(row)">
                                    View Details
                                </button>
                            </td>
                        </tr>
                    </tbody>
                    <tfoot>
                        <tr>
                            <th colspan="5">Total</th>
                            <th class="text-end">{{ totalDelivered }}</th>
                            <th class="text-end">{{ totalReceived }}</th>
                            <th class="text-end">{{ totalPending }}</th>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <div v-else class="wop-state">No records found.</div>
    </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { createApp } from 'vue'
import MultiSelectListConverter from './MultiSelectListConverter.vue'

const root = ref(null)
const loading = ref(false)
const rows = ref([])
const sample_doc = ref({})
const detailLoading = ref(false)
let lotCtrl = null
let processCtrl = null
let supplierCtrl = null
let itemCtrl = null
let statusCtrl = null

onMounted(() => {
    nextTick(() => {
        const el = root.value

        $(el).find(".wop-lot-input").html("")
        lotCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".wop-lot-input"),
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

        $(el).find(".wop-process-input").html("")
        processCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".wop-process-input"),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'process',
                label: 'Process',
                options: 'Process',
				get_data: function(txt) {
                    return frappe.db.get_link_options("Process", txt)
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })

        $(el).find(".wop-supplier-input").html("")
        supplierCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".wop-supplier-input"),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'supplier',
                label: 'Supplier',
                options: 'Supplier',
				get_data: function(txt) {
                    return frappe.db.get_link_options("Supplier", txt)
                },
            },

            doc: sample_doc.value,
            render_input: true,
        })

        $(el).find(".wop-item-input").html("")
        itemCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".wop-item-input"),
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

        $(el).find(".wop-status-input").html("")
        statusCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".wop-status-input"),
            df: {
                fieldtype: 'Select',
                fieldname: 'status',
                label: 'Work Order Status',
                options: '\nOpen\nClosed',
            },
            doc: sample_doc.value,
            render_input: true,
        })

    })
})

function normalizeValue(value) {
    if (Array.isArray(value)) {
        return value.length ? value[0] : null
    }
    if (value && typeof value === 'object') {
        if ('value' in value) return value.value || null
        if ('name' in value) return value.name || null
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
            .map(v => {
                if (v && typeof v === 'object') {
                    return v.value || v.name || null
                }
                return v || null
            })
            .filter(Boolean)
    }
    if (value && typeof value === 'object') {
        if (Array.isArray(value.values)) {
            return value.values.filter(Boolean)
        }
        if (Array.isArray(value.list)) {
            return value.list.filter(Boolean)
        }
        if ('value' in value) return value.value ? [value.value] : []
        if ('name' in value) return value.name ? [value.name] : []
    }
    return [value].filter(Boolean)
}

function loadReport() {
    loading.value = true
    frappe.call({
        method: "production_api.utils.get_work_order_pending_report",
        args: {
            lot: lotCtrl ? normalizeMultiValue(lotCtrl.get_value()) : [],
            process: processCtrl ? normalizeMultiValue(processCtrl.get_value()) : [],
            supplier: supplierCtrl ? normalizeMultiValue(supplierCtrl.get_value()) : [],
            item: itemCtrl ? normalizeMultiValue(itemCtrl.get_value()) : [],
            status: statusCtrl ? normalizeValue(statusCtrl.get_value()) : null,
        },
        freeze: true,
        freeze_message: "Fetching Work Order Pending Report...",
        callback(r) {
            rows.value = (r.message || []).map(row => ({
                ...row,
                pending_quantity: Number(row.pending_quantity || 0),
                total_qty: Number(row.total_qty || 0),
                delivered_qty: Number(row.delivered_qty || 0),
                received_qty: Number(row.received_qty || 0),
            }))
            loading.value = false
        },
        error() {
            loading.value = false
        },
    })
}

function openRowDetails(row) {
    if (!row) return
    detailLoading.value = true
    const dialog = new frappe.ui.Dialog({
        title: 'Work Order Calculated Items',
        size: 'large',
        fields: [
            { fieldtype: 'HTML', fieldname: 'details_html' }
        ],
        primary_action_label: 'Close',
        primary_action() {
            dialog.hide()
        }
    })
    dialog.show()
    dialog.fields_dict.details_html.$wrapper.html('<div class="text-muted">Loading details...</div>')

    frappe.call({
        method: 'production_api.utils.get_the_data_of_each_row',
        args: {
            item: normalizeValue(row.item_name),
            process: normalizeValue(row.process_name),
            supplier: normalizeValue(row.supplier_name),
            lot: normalizeValue(row.lot),
        },
        callback(r) {
            const detailRows = r.message || []
            dialog.fields_dict.details_html.$wrapper.html(renderDetailTable(detailRows, row))
            detailLoading.value = false
        },
        error() {
            dialog.fields_dict.details_html.$wrapper.html('<div class="text-danger">Failed to load details.</div>')
            detailLoading.value = false
        },
    })
}

function renderDetailTable(detailRows, summaryRow) {
    if (!detailRows.length) {
        return '<div class="text-muted">No detail rows found.</div>'
    }

    const body = detailRows.map((r, idx) => `
        <tr>
            <td>${idx + 1}</td>
            <td>${frappe.utils.escape_html(r.work_order || '')}</td>
            <td>${frappe.utils.escape_html(r.item_variant || '')}</td>
            <td class="text-end">${fmt(r.delivered_quantity)}</td>
            <td class="text-end">${fmt(r.received_qty)}</td>
            <td class="text-end">${fmt(r.pending_quantity)}</td>
        </tr>
    `).join('')

    const totalDelivered = detailRows.reduce((sum, r) => sum + Number(r.delivered_quantity || 0), 0)
    const totalReceived = detailRows.reduce((sum, r) => sum + Number(r.received_qty || 0), 0)
    const totalPending = detailRows.reduce((sum, r) => sum + Number(r.pending_quantity || 0), 0)

    return `
       <div style="margin-bottom: 12px; display: flex; gap: 12px;">
		<div>
			<strong>Lot:</strong>
			${frappe.utils.escape_html(summaryRow.lot || '')}
		</div>

		<div>
			<strong>Process:</strong>
			${frappe.utils.escape_html(summaryRow.process_name || '')}
		</div>

		<div>
			<strong>Supplier:</strong>
			${frappe.utils.escape_html(summaryRow.supplier_name || '')}
		</div>

		<div>
			<strong>Item:</strong>
			${frappe.utils.escape_html(summaryRow.item_name || '')}
		</div>
		</div>
        <div class="table-responsive">
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>No</th>
                        <th>Work Order</th>
                        <th>Item Variant</th>
                        <th class="text-end">Delivered</th>
                        <th class="text-end">Received</th>
                        <th class="text-end">Pending</th>
                    </tr>
                </thead>
                <tbody>${body}</tbody>
                <tfoot>
                    <tr>
                        <th colspan="3">Total</th>
                        <th class="text-end">${fmt(totalDelivered)}</th>
                        <th class="text-end">${fmt(totalReceived)}</th>
                        <th class="text-end">${fmt(totalPending)}</th>
                    </tr>
                </tfoot>
            </table>
        </div>
    `
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
                itemCtrl.set_value(pasteInstance.list[0] || '')
            } else if (pasteInstance.select_value == 'Lot') {
                lotCtrl.set_value(pasteInstance.list[0] || '')
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

function fmt(value) {
    const n = Number(value || 0)
    return n.toLocaleString()
}

function pendingClass(value) {
    const n = Number(value || 0)
    if (n > 0) return 'text-warning'
    if (n < 0) return 'text-danger'
    return 'text-success'
}

const totalQty = computed(() => rows.value.reduce((sum, row) => sum + Number(row.total_qty || 0), 0).toLocaleString())
const totalDelivered = computed(() => rows.value.reduce((sum, row) => sum + Number(row.delivered_qty || 0), 0).toLocaleString())
const totalReceived = computed(() => rows.value.reduce((sum, row) => sum + Number(row.received_qty || 0), 0).toLocaleString())
const totalPending = computed(() => rows.value.reduce((sum, row) => sum + Number(row.pending_quantity || 0), 0).toLocaleString())
</script>

<style scoped>
.wop-root {
    padding: 20px;
}

.wop-header {
    margin-bottom: 18px;
}

.wop-title {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
	text-align: center;
}

.wop-subtitle {
    margin: 6px 0 0;
    color: #6b7280;
}

.wop-filters {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 10px;
    align-items: end;
    margin-bottom: 18px;
}

.wop-control :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.wop-control :deep(.form-group) {
    margin-bottom: 0 !important;
}

.wop-actions {
    display: flex;
    align-items: end;
	padding-bottom: 8px;
}

.wop-summary {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 18px;
}

.wop-card {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 14px;
    background: #fff;
}

.wop-card-label {
    font-size: 12px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.wop-card-value {
    font-size: 22px;
    font-weight: 700;
    margin-top: 6px;
}

.wop-table th,
.wop-table td {
    vertical-align: middle;
}

.wop-row {
    cursor: pointer;
}

.wop-row:hover {
    background: #f8fafc;
}

.wop-state {
    padding: 24px;
    text-align: center;
    color: #6b7280;
}

@media (max-width: 1200px) {
    .wop-filters,
    .wop-summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 768px) {
    .wop-filters,
    .wop-summary {
        grid-template-columns: 1fr;
    }
}
</style>
