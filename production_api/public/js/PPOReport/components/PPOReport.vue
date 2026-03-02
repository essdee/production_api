<template>
    <div ref="root" class="ppo-root">
        <div class="ppo-header">
            <h3 class="ppo-title">PPO Report</h3>
            <div class="ppo-controls">
                <div class="from-date-input ctrl-slot"></div>
                <div class="to-date-input ctrl-slot"></div>
                <div class="ppo-actions">
                    <button class="btn btn-primary btn-get" @click="get_report">Get Report</button>
                    <button class="btn btn-default btn-dl" @click="download_excel" v-if="groups.length > 0">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:5px;vertical-align:-2px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Excel
                    </button>
                </div>
            </div>
        </div>

        <div v-if="groups.length > 0" class="ppo-body">
            <div class="ppo-summary-bar">
                <div class="summary-item">
                    <span class="summary-label">Total Orders</span>
                    <span class="summary-value">{{ total_orders }}</span>
                </div>
                <div class="summary-divider"></div>
                <div class="summary-item">
                    <span class="summary-label">Total Quantity</span>
                    <span class="summary-value summary-value--primary">{{ overall_total.toLocaleString() }}</span>
                </div>
                <div class="summary-divider"></div>
                <div class="summary-item">
                    <span class="summary-label">Size Groups</span>
                    <span class="summary-value">{{ groups.length }}</span>
                </div>
            </div>

            <div v-for="(group, gIdx) in groups" :key="gIdx" class="ppo-group">
                <div class="group-header">
                    <span class="group-tag">Group {{ gIdx + 1 }}</span>
                    <span class="group-sizes">{{ group.sizes.join('  /  ') }}</span>
                    <span class="group-count">{{ group.orders.length }} order{{ group.orders.length !== 1 ? 's' : '' }}</span>
                </div>
                <div class="table-wrap">
                    <table class="ppo-table">
                        <thead>
                            <tr>
                                <th class="col-sno">#</th>
                                <th class="col-ppo">PPO</th>
                                <th class="col-item">Item</th>
                                <th class="col-fabric">Fabric</th>
                                <th class="col-dia">Dia</th>
                                <th class="col-gsm">GSM</th>
                                <th class="col-date">Delivery</th>
                                <th v-for="size in group.sizes" :key="size" class="col-size">{{ size }}</th>
                                <th class="col-total">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(order, idx) in group.orders" :key="order.name">
                                <td class="col-sno cell-dim">{{ idx + 1 }}</td>
                                <td class="col-ppo">
                                    <a :href="'/app/production-order/' + order.name" class="ppo-link">
                                        {{ order.name }}
                                    </a>
                                </td>
                                <td class="col-item">{{ order.item }}</td>
                                <td class="col-fabric">{{ order.fabric }}</td>
                                <td class="col-dia">{{ order.dia }}</td>
                                <td class="col-gsm">{{ order.gsm || '' }}</td>
                                <td class="col-date">{{ formatDate(order.delivery_date) }}</td>
                                <td v-for="size in group.sizes" :key="size" class="col-size"
                                    :class="{ 'cell-zero': !(order.qty[size]) }">
                                    {{ order.qty[size] || '—' }}
                                </td>
                                <td class="col-total cell-total">{{ order.total.toLocaleString() }}</td>
                            </tr>
                        </tbody>
                        <tfoot>
                            <tr>
                                <td :colspan="7" class="foot-label">Total</td>
                                <td v-for="size in group.sizes" :key="size" class="col-size foot-num">
                                    {{ column_total(group, size).toLocaleString() }}
                                </td>
                                <td class="col-total foot-grand">{{ group_total(group).toLocaleString() }}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>
        </div>

        <div v-else-if="fetched" class="ppo-empty">
            No records found for the selected date range.
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const root = ref(null)
const groups = ref([])
const fetched = ref(false)

let from_date_ctrl = null
let to_date_ctrl = null
const sample_doc = ref({})

onMounted(() => {
    const el = root.value

    $(el).find(".from-date-input").html("")
    from_date_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".from-date-input"),
        df: {
            fieldname: "from_date",
            fieldtype: "Date",
            label: "From Date",
        },
        doc: sample_doc.value,
        render_input: true,
    })

    $(el).find(".to-date-input").html("")
    to_date_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".to-date-input"),
        df: {
            fieldname: "to_date",
            fieldtype: "Date",
            label: "To Date",
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

function get_report() {
    const from_date = from_date_ctrl.get_value()
    const to_date = to_date_ctrl.get_value()

    const args = {}
    if (from_date) args.from_date = from_date
    if (to_date) args.to_date = to_date

    frappe.call({
        method: "production_api.utils.get_ppo_report_data",
        args,
        freeze: true,
        freeze_message: "Fetching PPO Report...",
        callback: function (r) {
            groups.value = r.message.groups || []
            fetched.value = true
        },
    })
}

const overall_total = computed(() => {
    let total = 0
    for (const group of groups.value) {
        for (const order of group.orders) {
            total += order.total
        }
    }
    return total
})

const total_orders = computed(() => {
    let count = 0
    for (const group of groups.value) {
        count += group.orders.length
    }
    return count
})

function formatDate(dateStr) {
    if (!dateStr) return ''
    const parts = dateStr.split('-')
    if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`
    return dateStr
}

function download_excel() {
    const from_date = from_date_ctrl.get_value()
    const to_date = to_date_ctrl.get_value()
    const params = new URLSearchParams()
    if (from_date) params.set('from_date', from_date)
    if (to_date) params.set('to_date', to_date)
    window.open(`/api/method/production_api.utils.download_ppo_report?${params.toString()}`)
}

function column_total(group, size) {
    let total = 0
    for (const order of group.orders) {
        total += order.qty[size] || 0
    }
    return total
}

function group_total(group) {
    let total = 0
    for (const order of group.orders) {
        total += order.total
    }
    return total
}

function load_data(data) {
    groups.value = data.groups || []
    fetched.value = true
}

defineExpose({ load_data })
</script>

<style scoped>
.ppo-root {
    padding: 24px 28px;
    color: #374151;
}

/* ── Header ── */
.ppo-header {
    margin-bottom: 24px;
}
.ppo-title {
    font-size: 20px;
    font-weight: 700;
    color: #1f2937;
    margin: 0 0 16px 0;
    padding: 0;
}
.ppo-controls {
    display: flex;
    align-items: flex-end;
    gap: 14px;
}
.ctrl-slot {
    width: 180px;
}
.ppo-actions {
    display: flex;
    gap: 8px;
    padding-bottom: 2px;
}
.btn-get {
    font-weight: 600;
    font-size: 12.5px;
    padding: 7px 18px;
}
.btn-dl {
    font-weight: 500;
    font-size: 12.5px;
    padding: 7px 14px;
    display: inline-flex;
    align-items: center;
}

/* ── Summary Bar ── */
.ppo-summary-bar {
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
.summary-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9ca3af;
}
.summary-value {
    font-size: 20px;
    font-weight: 700;
    color: #374151;
}
.summary-value--primary {
    color: #2563eb;
}
.summary-divider {
    width: 1px;
    height: 32px;
    background: #e5e7eb;
    margin: 0 24px;
}

/* ── Group ── */
.ppo-group {
    margin-bottom: 28px;
}
.group-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 2px solid #e5e7eb;
}
.group-tag {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #2563eb;
    background: #eff6ff;
    padding: 3px 8px;
    border-radius: 3px;
    border: 1px solid #bfdbfe;
}
.group-sizes {
    font-size: 13px;
    font-weight: 600;
    color: #4b5563;
}
.group-count {
    margin-left: auto;
    font-size: 11.5px;
    font-weight: 500;
    color: #9ca3af;
}

/* ── Table ── */
.table-wrap {
    overflow-x: auto;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
}
.ppo-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
}
.ppo-table thead th {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #6b7280;
    background: #f9fafb;
    padding: 8px 10px;
    border-bottom: 2px solid #d1d5db;
    text-align: center;
    white-space: nowrap;
}
.ppo-table tbody td {
    padding: 7px 10px;
    text-align: center;
    vertical-align: middle;
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
}
.ppo-table tbody tr:hover {
    background: #f9fafb;
}
.ppo-table tbody tr:nth-child(even) {
    background: #fafbfc;
}
.ppo-table tbody tr:nth-child(even):hover {
    background: #f3f4f6;
}

/* Column-specific */
.col-sno { width: 40px; }
.col-item, .col-fabric { text-align: left; }
.ppo-table thead .col-item,
.ppo-table thead .col-fabric { text-align: left; }

.cell-dim { color: #9ca3af; }
.cell-zero {
    color: #d1d5db;
}
.cell-total {
    font-weight: 700;
    color: #1f2937;
    background: #f9fafb;
}
.ppo-link {
    color: #2563eb;
    font-weight: 600;
    text-decoration: none;
    font-size: 12px;
}
.ppo-link:hover {
    color: #1d4ed8;
    text-decoration: underline;
}

/* Footer row */
.ppo-table tfoot td {
    padding: 9px 10px;
    font-weight: 700;
    font-size: 12.5px;
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
    font-size: 11px;
    color: #6b7280;
}
.foot-grand {
    font-weight: 800;
    color: #1f2937;
    background: #eef2ff;
}

/* ── Empty state ── */
.ppo-empty {
    text-align: center;
    color: #9ca3af;
    padding: 60px 0;
    font-size: 14px;
    font-weight: 500;
}
</style>
