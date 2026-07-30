<template>
    <div ref="root" class="wop-root">
        <header class="wop-header">
            <h3 class="wop-title">WO Pending Report</h3>
            <p class="wop-subtitle">
                Delivered, received, and difference values from submitted Work Orders
            </p>
        </header>

        <div class="wop-filters">
            <div class="wop-control wop-production-order-input"></div>
            <div class="wop-control wop-lot-input"></div>
            <div class="wop-control wop-item-input"></div>
            <div class="wop-control wop-item-variant-input"></div>
            <div class="wop-control wop-process-input"></div>
            <div class="wop-control wop-supplier-input"></div>
            <div class="wop-control wop-from-date-input"></div>
            <div class="wop-control wop-to-date-input"></div>
            <div class="wop-control wop-status-input"></div>
            <div class="wop-actions">
                <button class="btn btn-primary" :disabled="loading" @click="loadReport">
                    {{ loading ? "Loading..." : "Show Report" }}
                </button>
            </div>
        </div>

        <div v-if="loading" class="wop-state">Loading report...</div>

        <div v-else-if="rows.length" class="wop-body">
            <div class="wop-summary">
                <div class="wop-card">
                    <div class="wop-card-label">Rows</div>
                    <div class="wop-card-value">{{ rows.length.toLocaleString() }}</div>
                </div>
                <div class="wop-card">
                    <div class="wop-card-label">Delivered</div>
                    <div class="wop-card-value">{{ totalDelivered }}</div>
                </div>
                <div class="wop-card">
                    <div class="wop-card-label">Received</div>
                    <div class="wop-card-value">{{ totalReceived }}</div>
                </div>
                <div class="wop-card wop-card--pending">
                    <div class="wop-card-label">Diff</div>
                    <div class="wop-card-value">{{ totalPending }}</div>
                </div>
            </div>

            <div class="table-responsive wop-table-wrap">
                <table class="table table-bordered table-sm wop-table">
                    <thead>
                        <tr>
                            <th>Production Order</th>
                            <th>WO</th>
                            <th>Lot</th>
                            <th>Process</th>
                            <th>Supplier</th>
                            <th>Item</th>
                            <th>Item Variant</th>
                            <th class="text-end">Delivered</th>
                            <th class="text-end">Received</th>
                            <th class="text-end">Diff</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="row in rows"
                            :key="rowKey(row)"
                        >
                            <td>{{ row.production_order }}</td>
                            <td>{{ row.work_order }}</td>
                            <td>{{ row.lot }}</td>
                            <td>{{ row.process_name }}</td>
                            <td>{{ row.supplier_name }}</td>
                            <td>{{ row.item_name }}</td>
                            <td>{{ row.item_variant }}</td>
                            <td class="text-end">{{ fmt(row.delivered_qty) }}</td>
                            <td class="text-end">{{ fmt(row.received_qty) }}</td>
                            <td class="text-end wop-pending">{{ fmt(row.pending_quantity) }}</td>
                        </tr>
                    </tbody>
                    <tfoot>
                        <tr>
                            <th colspan="7">Total</th>
                            <th class="text-end">{{ totalDelivered }}</th>
                            <th class="text-end">{{ totalReceived }}</th>
                            <th class="text-end">{{ totalPending }}</th>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <div v-else class="wop-state">No submitted Work Order details found.</div>
    </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from "vue"

const root = ref(null)
const loading = ref(false)
const rows = ref([])
const sampleDoc = ref({})

let productionOrderCtrl = null
let lotCtrl = null
let itemCtrl = null
let itemVariantCtrl = null
let processCtrl = null
let supplierCtrl = null
let fromDateCtrl = null
let toDateCtrl = null
let statusCtrl = null

function makeMultiSelect(el, selector, fieldname, label, doctype) {
    $(el).find(selector).html("")
    return frappe.ui.form.make_control({
        parent: $(el).find(selector),
        df: {
            fieldtype: "MultiSelectList",
            fieldname,
            label,
            options: doctype,
            get_data(txt) {
                return frappe.db.get_link_options(doctype, txt)
            },
        },
        doc: sampleDoc.value,
        render_input: true,
    })
}

function makeDate(el, selector, fieldname, label) {
    $(el).find(selector).html("")
    return frappe.ui.form.make_control({
        parent: $(el).find(selector),
        df: {
            fieldtype: "Date",
            fieldname,
            label,
        },
        doc: sampleDoc.value,
        render_input: true,
    })
}

onMounted(() => {
    nextTick(() => {
        const el = root.value
        productionOrderCtrl = makeMultiSelect(
            el,
            ".wop-production-order-input",
            "production_order",
            "Production Order",
            "Production Order",
        )
        lotCtrl = makeMultiSelect(el, ".wop-lot-input", "lot", "Lot", "Lot")
        itemCtrl = makeMultiSelect(el, ".wop-item-input", "item", "Item", "Item")
        itemVariantCtrl = makeMultiSelect(
            el,
            ".wop-item-variant-input",
            "item_variant",
            "Item Variant",
            "Item Variant",
        )
        processCtrl = makeMultiSelect(
            el,
            ".wop-process-input",
            "process",
            "Process Name",
            "Process",
        )
        supplierCtrl = makeMultiSelect(
            el,
            ".wop-supplier-input",
            "supplier",
            "Supplier",
            "Supplier",
        )
        fromDateCtrl = makeDate(
            el,
            ".wop-from-date-input",
            "from_date",
            "From Date",
        )
        toDateCtrl = makeDate(el, ".wop-to-date-input", "to_date", "To Date")

        $(el).find(".wop-status-input").html("")
        statusCtrl = frappe.ui.form.make_control({
            parent: $(el).find(".wop-status-input"),
            df: {
                fieldtype: "Select",
                fieldname: "status",
                label: "Open Status",
                options: [
                    "",
                    "Open",
                    "Close Request",
                    "Close",
                ].join("\n"),
            },
            doc: sampleDoc.value,
            render_input: true,
        })
    })
})

function normalizeMultiValue(value) {
    if (!value) return []
    if (typeof value === "string") {
        if (!value.trim() || value.trim() === "[]") return []
        try {
            value = JSON.parse(value)
        } catch (error) {
            return [value]
        }
    }
    if (!Array.isArray(value)) value = [value]
    return value
        .map((row) => {
            if (row && typeof row === "object") {
                return row.value || row.name || row.label || null
            }
            return row || null
        })
        .filter(Boolean)
}

function loadReport() {
    const fromDate = fromDateCtrl?.get_value() || null
    const toDate = toDateCtrl?.get_value() || null
    if (Boolean(fromDate) !== Boolean(toDate)) {
        frappe.msgprint("Set both From Date and To Date, or leave both blank.")
        return
    }

    loading.value = true
    frappe.call({
        method: "production_api.utils.get_work_order_pending_report",
        args: {
            production_order: normalizeMultiValue(productionOrderCtrl?.get_value()),
            lot: normalizeMultiValue(lotCtrl?.get_value()),
            item: normalizeMultiValue(itemCtrl?.get_value()),
            item_variant: normalizeMultiValue(itemVariantCtrl?.get_value()),
            process: normalizeMultiValue(processCtrl?.get_value()),
            supplier: normalizeMultiValue(supplierCtrl?.get_value()),
            from_date: fromDate,
            to_date: toDate,
            status: statusCtrl?.get_value() || null,
        },
        freeze: true,
        freeze_message: "Fetching WO Pending Report...",
        callback(r) {
            rows.value = (r.message || []).map((row) => ({
                ...row,
                delivered_qty: Number(row.delivered_qty || 0),
                received_qty: Number(row.received_qty || 0),
                pending_quantity: Number(row.pending_quantity || 0),
            }))
            loading.value = false
        },
        error() {
            loading.value = false
        },
    })
}

function rowKey(row) {
    return [
        row.production_order,
        row.work_order,
        row.lot,
        row.process_name,
        row.supplier_name,
        row.item_name,
        row.item_variant,
    ].join("|")
}

function fmt(value) {
    return Number(value || 0).toLocaleString()
}

const totalDelivered = computed(() =>
    fmt(rows.value.reduce((sum, row) => sum + row.delivered_qty, 0))
)
const totalReceived = computed(() =>
    fmt(rows.value.reduce((sum, row) => sum + row.received_qty, 0))
)
const totalPending = computed(() =>
    fmt(rows.value.reduce((sum, row) => sum + row.pending_quantity, 0))
)
</script>

<style scoped>
.wop-root {
    padding: 20px;
}

.wop-header {
    margin-bottom: 18px;
    text-align: center;
}

.wop-title {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
}

.wop-subtitle {
    margin: 5px 0 0;
    color: #6b7280;
}

.wop-filters {
    display: grid;
    grid-template-columns: repeat(5, minmax(170px, 1fr));
    gap: 10px;
    align-items: end;
    margin-bottom: 18px;
}

.wop-control :deep(.frappe-control),
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
    grid-template-columns: repeat(4, minmax(150px, 220px));
    gap: 12px;
    margin-bottom: 18px;
}

.wop-card {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 14px;
    background: #fff;
}

.wop-card--pending {
    border-color: #f59e0b;
    background: #fffbeb;
}

.wop-card-label {
    font-size: 12px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.wop-card-value {
    margin-top: 6px;
    font-size: 22px;
    font-weight: 700;
}

.wop-table-wrap {
    max-height: 70vh;
}

.wop-table {
    white-space: nowrap;
}

.wop-table thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: #f8fafc;
}

.wop-table th,
.wop-table td {
    vertical-align: middle;
}

.wop-pending {
    color: #b45309;
    font-weight: 700;
}

.wop-state {
    padding: 36px 24px;
    text-align: center;
    color: #6b7280;
}

@media (max-width: 1200px) {
    .wop-filters {
        grid-template-columns: repeat(3, minmax(170px, 1fr));
    }
}

@media (max-width: 768px) {
    .wop-filters,
    .wop-summary {
        grid-template-columns: 1fr;
    }
}
</style>
