<template>
    <div ref="root" class="ppo-root">
        <div class="ppo-header">
            <h3 class="ppo-title">PPO Report</h3>
            <div class="ppo-controls">
                <div class="status-input ctrl-slot"></div>
                <div class="category-input ctrl-slot"></div>
                <div class="item-input ctrl-slot"></div>
                <div class="from-date-input ctrl-slot"></div>
                <div class="to-date-input ctrl-slot"></div>
                <div class="ppo-actions">
                    <button class="btn btn-primary btn-get" @click="get_report">Get Report</button>
                    <button class="btn btn-default btn-dl" @click="download_excel" v-if="flat_orders.length > 0">
                        <svg class="download-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Excel
                    </button>
                </div>
            </div>
        </div>

        <div v-if="flat_orders.length > 0" class="ppo-body">
            <div class="ppo-summary-bar">
                <div class="summary-item">
                    <span class="summary-label">Total Orders</span>
                    <span class="summary-value">{{ flat_orders.length }}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Total Quantity</span>
                    <span class="summary-value summary-value--primary">{{ overall_total.toLocaleString() }}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Size Groups</span>
                    <span class="summary-value">{{ size_groups.length }}</span>
                </div>
            </div>

            <div class="ppo-toggles">
                <span class="ppo-toggles-label">Columns</span>
                <label class="ppo-toggle"><input type="checkbox" v-model="show_fabric" /> Show Fabric</label>
                <label class="ppo-toggle"><input type="checkbox" v-model="show_dia" /> Show Dia</label>
                <label class="ppo-toggle"><input type="checkbox" v-model="show_gsm" /> Show GSM</label>
                <span class="ppo-toggles-sep"></span>
                <label class="ppo-toggle ppo-toggle--accent">
                    <input type="checkbox" v-model="summarized" @change="onSummarizedToggle" /> Summarized
                </label>
            </div>

            <div class="table-wrap">
                <table class="ppo-table">
                    <thead>
                        <tr v-for="(sg, sgIdx) in size_groups" :key="'sgr-' + sgIdx"
                            :class="{ 'header-row-alt': sgIdx % 2 === 1 }">
                            <template v-if="sgIdx === 0">
                                <th :rowspan="size_groups.length">#</th>
                                <th :rowspan="size_groups.length">PPO</th>
                                <th :rowspan="size_groups.length">Item</th>
                                <th v-if="show_fabric" :rowspan="size_groups.length">Fabric</th>
                                <th v-if="show_dia" :rowspan="size_groups.length">Dia</th>
                                <th v-if="show_gsm" :rowspan="size_groups.length">GSM</th>
                                <th :rowspan="size_groups.length">Posting Date</th>
                                <th :rowspan="size_groups.length">Delivery Date</th>
                                <th :rowspan="size_groups.length">Don't Deliver After</th>
                                <th :rowspan="size_groups.length">Lead Time</th>
                                <th :rowspan="size_groups.length">Status</th>
                                <th :rowspan="size_groups.length">Action</th>
                            </template>
                            <th class="group-label-cell">{{ sg.label }}</th>
                            <th v-for="colIdx in max_cols" :key="'sh-' + sgIdx + '-' + colIdx"
                                class="group-header-cell">
                                {{ colIdx - 1 < sg.sizes.length ? sg.sizes[colIdx - 1] : '' }}
                            </th>
                            <template v-if="sgIdx === 0">
                                <th :rowspan="size_groups.length">Total</th>
                                <th :rowspan="size_groups.length">Comments</th>
                            </template>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="(order, idx) in flat_orders" :key="order.name">
                        <tr>
                            <td class="cell-dim">{{ idx + 1 }}</td>
                            <td>
                                <a :href="'/app/production-order/' + order.name" class="ppo-link">
                                    {{ order.name }}
                                </a>
                            </td>
                            <td>{{ order.item }}</td>
                            <td v-if="show_fabric">{{ order.fabric }}</td>
                            <td v-if="show_dia">{{ order.dia }}</td>
                            <td v-if="show_gsm">{{ order.gsm || '' }}</td>
                            <td>{{ formatDate(order.posting_date) }}</td>
                            <td>{{ formatDate(order.delivery_date) }}</td>
                            <td>{{ formatDate(order.dont_deliver_after) }}</td>
                            <td>{{ order.lead_time }}</td>
                            <td>
                                <span :class="order.status === 'Draft' ? 'status-draft' : 'status-submitted'">
                                    {{ order.status }}
                                </span>
                            </td>
                            <td>
                                <button class="btn btn-xs btn-default btn-summarize" @click="show_summary(order.name)">
                                    {{ summaryState[order.name]?.expanded ? 'Hide' : 'Summarize' }}
                                </button>
                            </td>
                            <td class="cell-group-label" :title="order.group_label">{{ order.group_label }}</td>
                            <td v-for="colIdx in max_cols" :key="'q-' + colIdx"
                                :class="{ 'cell-zero': !order.qty_by_pos[colIdx - 1] }">
                                {{ order.qty_by_pos[colIdx - 1] || '—' }}
                            </td>
                            <td class="cell-total">{{ order.total.toLocaleString() }}</td>
                            <td class="cell-comments" :title="order.comments">{{ order.comments }}</td>
                        </tr>
                        <template v-if="summaryState[order.name]?.expanded">
                          <tr v-if="summaryState[order.name]?.loading" class="summary-row">
                            <td :colspan="full_colspan" class="summary-status">Loading...</td>
                          </tr>
                          <tr v-else-if="!summaryState[order.name]?.data?.rows?.length" class="summary-row">
                            <td :colspan="full_colspan" class="summary-status">No dispatch records found.</td>
                          </tr>
                          <template v-else>
                            <tr v-for="(row, rIdx) in summaryState[order.name].data.rows"
                                :key="'s-' + order.name + '-' + rIdx" class="summary-row">
                              <td :colspan="label_colspan" class="summary-label-cell">
                                {{ formatDate(row.date) }} &middot; {{ row.lot }}
                              </td>
                              <td v-for="colIdx in max_cols" :key="'sd-' + colIdx"
                                  :class="{ 'cell-zero': !row.sizes[order.group_sizes[colIdx - 1]] }">
                                {{ (order.group_sizes[colIdx - 1] && row.sizes[order.group_sizes[colIdx - 1]]) || '—' }}
                              </td>
                              <td class="summary-total-cell">{{ row.total }}</td>
                              <td></td>
                            </tr>
                            <tr class="summary-footer-row">
                              <td :colspan="label_colspan" class="summary-label-cell summary-footer-label">Dispatched Total</td>
                              <td v-for="colIdx in max_cols" :key="'sf-' + colIdx" class="summary-footer-num">
                                {{ summarySizeTotalByPos(order.name, order.group_sizes[colIdx - 1]) }}
                              </td>
                              <td class="summary-footer-num summary-footer-grand">{{ summaryTotal(order.name) }}</td>
                              <td></td>
                            </tr>
                          </template>
                        </template>
                        </template>
                    </tbody>
                    <tfoot>
                        <tr>
                            <td :colspan="label_colspan" class="foot-label">Total</td>
                            <td v-for="colIdx in max_cols" :key="'ft-' + colIdx" class="foot-num">
                                {{ column_total_flat(colIdx - 1).toLocaleString() }}
                            </td>
                            <td class="foot-grand">{{ overall_total.toLocaleString() }}</td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <div v-else-if="fetched" class="ppo-empty">
            <div class="ppo-empty-title">No records found</div>
            <div class="ppo-empty-copy">The selected filters did not return any PPO records.</div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const root = ref(null)
const groups = ref([])
const flat_orders = ref([])
const max_cols = ref(0)
const size_groups = ref([])
const fetched = ref(false)
const summaryState = ref({})

// Toggle-able columns (all hidden by default). Data is always fetched;
// these are pure client-side v-if toggles.
const show_fabric = ref(false)
const show_dia = ref(false)
const show_gsm = ref(false)

// "Summarized" — expands the dispatch drill-down for EVERY loaded order at once
// via a single batched API call (get_ppo_dispatch_summary_bulk).
const summarized = ref(false)

// Fixed (non-size) column count drives the colspans of the Total row and the
// Summarize drill-down labels so they stay aligned when columns are toggled.
// 9 always-on fixed cols + the 3 toggle-able ones (Fabric/Dia/GSM).
const fixed_col_count = computed(
    () => 9 + (show_fabric.value ? 1 : 0) + (show_dia.value ? 1 : 0) + (show_gsm.value ? 1 : 0)
)
// group-label cell only
const label_colspan = computed(() => fixed_col_count.value + 1)
// everything: fixed cols + group-label + size cols + Total + Comments
const full_colspan = computed(() => fixed_col_count.value + max_cols.value + 3)

let status_ctrl = null
let category_ctrl = null
let item_ctrl = null
let from_date_ctrl = null
let to_date_ctrl = null
const sample_doc = ref({})

onMounted(() => {
    const el = root.value

    $(el).find(".status-input").html("")
    status_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".status-input"),
        df: {
            fieldname: "status",
            fieldtype: "Select",
            options: "\nDraft\nSubmitted",
            label: "Status",
        },
        doc: sample_doc.value,
        render_input: true,
    })

    $(el).find(".category-input").html("")
    category_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".category-input"),
        df: {
            fieldname: "product_category",
            fieldtype: "Link",
            options: "Product Category",
            label: "Product Category",
        },
        doc: sample_doc.value,
        render_input: true,
    })

    $(el).find(".item-input").html("")
    item_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: {
            fieldname: "item",
            fieldtype: "MultiSelectList",
            options: "Item",
            label: "Item",
            get_data: function (txt) {
                return frappe.db.get_link_options("Item", txt)
            },
        },
        doc: sample_doc.value,
        render_input: true,
    })

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
    const status = status_ctrl.get_value()
    const product_category = category_ctrl.get_value()
    const item = item_ctrl.get_value()
    const from_date = from_date_ctrl.get_value()
    const to_date = to_date_ctrl.get_value()

    const args = {}
    if (status) args.status = status
    if (product_category) args.product_category = product_category
    if (item && item.length) args.item = JSON.stringify(item)
    if (from_date) args.from_date = from_date
    if (to_date) args.to_date = to_date

    frappe.call({
        method: "production_api.utils.get_ppo_report_data",
        args,
        freeze: true,
        freeze_message: "Fetching PPO Report...",
        callback: function (r) {
            groups.value = r.message.groups || []
            flat_orders.value = r.message.flat_orders || []
            max_cols.value = r.message.max_cols || 0
            size_groups.value = r.message.size_groups || []
            fetched.value = true
            summaryState.value = {}
            summarized.value = false
        },
    })
}

const overall_total = computed(() => {
    let total = 0
    for (const order of flat_orders.value) {
        total += order.total
    }
    return total
})

function formatDate(dateStr) {
    if (!dateStr) return ''
    const parts = dateStr.split('-')
    if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`
    return dateStr
}

function download_excel() {
    const status = status_ctrl.get_value()
    const product_category = category_ctrl.get_value()
    const item = item_ctrl.get_value()
    const from_date = from_date_ctrl.get_value()
    const to_date = to_date_ctrl.get_value()
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (product_category) params.set('product_category', product_category)
    if (item && item.length) params.set('item', JSON.stringify(item))
    if (from_date) params.set('from_date', from_date)
    if (to_date) params.set('to_date', to_date)
    window.open(`/api/method/production_api.utils.download_ppo_report?${params.toString()}`)
}

function column_total_flat(posIdx) {
    let total = 0
    for (const order of flat_orders.value) {
        total += order.qty_by_pos[posIdx] || 0
    }
    return total
}

function show_summary(ppo_name) {
    const entry = summaryState.value[ppo_name]

    // Already fetched — just toggle
    if (entry && entry.data !== undefined) {
        summaryState.value[ppo_name] = { ...entry, expanded: !entry.expanded }
        return
    }

    // First click — expand + fetch
    summaryState.value[ppo_name] = { loading: true, expanded: true }

    frappe.call({
        method: "production_api.utils.get_ppo_dispatch_summary",
        args: { production_order: ppo_name },
        callback(r) {
            summaryState.value[ppo_name] = {
                loading: false,
                data: r.message || { sizes: [], rows: [] },
                expanded: true,
            }
        },
    })
}

// "Summarized" master toggle. Checked → ONE batched call that expands the
// dispatch drill-down for every loaded order; unchecked → collapse them all.
function onSummarizedToggle() {
    if (summarized.value) {
        load_all_summaries()
    } else {
        collapse_all_summaries()
    }
}

function load_all_summaries() {
    const names = flat_orders.value.map((o) => o.name)
    if (!names.length) return

    frappe.call({
        method: "production_api.utils.get_ppo_dispatch_summary_bulk",
        args: { production_orders: JSON.stringify(names) },
        freeze: true,
        freeze_message: "Summarizing dispatch...",
        callback(r) {
            const map = r.message || {}
            const next = { ...summaryState.value }
            for (const name of names) {
                // Preload rows so the per-row Summarize button re-uses them
                // (show_summary sees data !== undefined and only toggles —
                //  no per-order fetch fires).
                next[name] = {
                    loading: false,
                    data: map[name] || { sizes: [], rows: [] },
                    expanded: true,
                }
            }
            summaryState.value = next
        },
    })
}

function collapse_all_summaries() {
    const next = { ...summaryState.value }
    for (const name of Object.keys(next)) {
        if (next[name]) next[name] = { ...next[name], expanded: false }
    }
    summaryState.value = next
}

function summaryTotal(ppo_name) {
    const rows = summaryState.value[ppo_name]?.data?.rows || []
    let total = 0
    for (const row of rows) total += row.total || 0
    return total
}

function summarySizeTotalByPos(ppo_name, sizeName) {
    if (!sizeName) return '—'
    const rows = summaryState.value[ppo_name]?.data?.rows || []
    let total = 0
    for (const row of rows) total += row.sizes[sizeName] || 0
    return total
}

function load_data(data) {
    groups.value = data.groups || []
    flat_orders.value = data.flat_orders || []
    max_cols.value = data.max_cols || 0
    size_groups.value = data.size_groups || []
    fetched.value = true
}

defineExpose({ load_data })
</script>

<style scoped>
.ppo-root {
    --ppo-bg: #f7f9fc;
    --ppo-surface: #ffffff;
    --ppo-surface-muted: #f8fafc;
    --ppo-border: #e2e8f0;
    --ppo-border-strong: #cbd5e1;
    --ppo-text: #0f172a;
    --ppo-muted: #64748b;
    --ppo-faint: #94a3b8;
    --ppo-blue: #2563eb;
    --ppo-blue-soft: #eff6ff;
    --ppo-teal: #0f766e;
    --ppo-teal-soft: #ecfdf5;
    --ppo-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);

    min-height: calc(100vh - 120px);
    padding: 22px 28px 32px;
    color: var(--ppo-text);
    background: var(--ppo-bg);
}

.ppo-header {
    margin-bottom: 18px;
    padding: 18px;
    background: var(--ppo-surface);
    border: 1px solid var(--ppo-border);
    border-radius: 8px;
    box-shadow: var(--ppo-shadow);
}

.ppo-title {
    margin: 0;
    padding: 0;
    color: var(--ppo-text);
    font-size: 22px;
    font-weight: 700;
    line-height: 1.25;
    letter-spacing: 0;
}

.ppo-title::after {
    display: block;
    width: 42px;
    height: 3px;
    margin-top: 10px;
    background: var(--ppo-blue);
    border-radius: 3px;
    content: "";
}

.ppo-controls {
    display: grid;
    grid-template-columns: repeat(5, minmax(150px, 1fr)) auto;
    gap: 12px;
    align-items: end;
    margin-top: 18px;
}

.ppo-toggles {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 16px;
    padding: 10px 14px;
    background: var(--ppo-surface);
    border: 1px solid var(--ppo-border);
    border-radius: 8px;
    box-shadow: var(--ppo-shadow);
}

.ppo-toggles-label {
    color: var(--ppo-muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.ppo-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    color: var(--ppo-text);
    cursor: pointer;
    font-size: 12.5px;
    font-weight: 600;
}

.ppo-toggle input {
    margin: 0;
    cursor: pointer;
}

.ppo-toggles-sep {
    align-self: stretch;
    width: 1px;
    margin: 2px 2px;
    background: var(--ppo-border);
}

.ppo-toggle--accent {
    color: var(--ppo-teal);
}

.ctrl-slot {
    min-width: 0;
    width: auto;
}

.ctrl-slot :deep(.frappe-control),
.ctrl-slot :deep(.form-group) {
    margin-bottom: 0;
}

.ctrl-slot :deep(.control-label) {
    margin-bottom: 6px;
    color: var(--ppo-muted);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0;
}

.ctrl-slot :deep(.form-control) {
    min-height: 34px;
    color: var(--ppo-text);
    background: var(--ppo-surface-muted);
    border-color: var(--ppo-border);
    border-radius: 6px;
    box-shadow: none;
    font-size: 13px;
    transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.ctrl-slot :deep(.form-control:focus) {
    background: var(--ppo-surface);
    border-color: var(--ppo-blue);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.ppo-actions {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: flex-end;
}

.btn-get,
.btn-dl,
.btn-summarize {
    border-radius: 6px;
    letter-spacing: 0;
    white-space: nowrap;
}

.btn-get {
    min-height: 34px;
    padding: 7px 18px;
    background: var(--ppo-blue);
    border-color: var(--ppo-blue);
    box-shadow: 0 2px 6px rgba(37, 99, 235, 0.22);
    font-size: 12.5px;
    font-weight: 700;
}

.btn-get:hover,
.btn-get:focus {
    background: #1d4ed8;
    border-color: #1d4ed8;
}

.btn-dl {
    display: inline-flex;
    align-items: center;
    min-height: 34px;
    padding: 7px 13px;
    color: #334155;
    background: var(--ppo-surface);
    border-color: var(--ppo-border-strong);
    font-size: 12.5px;
    font-weight: 600;
}

.btn-dl:hover,
.btn-dl:focus {
    color: var(--ppo-blue);
    background: var(--ppo-blue-soft);
    border-color: #bfdbfe;
}

.download-icon {
    flex: 0 0 auto;
    margin-right: 6px;
}

.ppo-body {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.ppo-summary-bar {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    overflow: hidden;
    background: var(--ppo-surface);
    border: 1px solid var(--ppo-border);
    border-radius: 8px;
    box-shadow: var(--ppo-shadow);
}

.summary-item {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-width: 0;
    padding: 15px 18px;
}

.summary-item + .summary-item {
    border-left: 1px solid var(--ppo-border);
}

.summary-label {
    color: var(--ppo-muted);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0;
}

.summary-value {
    color: var(--ppo-text);
    font-size: 24px;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: 0;
}

.summary-value--primary {
    color: var(--ppo-teal);
}

.table-wrap {
    overflow: auto;
    max-height: calc(100vh - 360px);
    background: var(--ppo-surface);
    border: 1px solid var(--ppo-border);
    border-radius: 8px;
    box-shadow: var(--ppo-shadow);
    /* Firefox: always-visible scrollbars */
    scrollbar-width: auto;
    scrollbar-color: #94a3b8 #eef2f7;
}

/* WebKit/Blink: force visible scrollbars on both axes */
.table-wrap::-webkit-scrollbar {
    width: 12px;
    height: 12px;
}

.table-wrap::-webkit-scrollbar-track {
    background: #eef2f7;
    border-radius: 6px;
}

.table-wrap::-webkit-scrollbar-thumb {
    background: #94a3b8;
    border-radius: 6px;
    border: 2px solid #eef2f7;
}

.table-wrap::-webkit-scrollbar-thumb:hover {
    background: #64748b;
}

.table-wrap::-webkit-scrollbar-corner {
    background: #eef2f7;
}

.ppo-table {
    width: 100%;
    min-width: 1180px;
    border-collapse: separate;
    border-spacing: 0;
    color: #334155;
    font-size: 12.5px;
}

.ppo-table thead th {
    padding: 9px 10px;
    color: #475569;
    background: var(--ppo-surface-muted);
    border-right: 1px solid var(--ppo-border);
    border-bottom: 1px solid var(--ppo-border-strong);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0;
    line-height: 1.2;
    text-align: center;
    text-transform: uppercase;
    white-space: nowrap;
}

.ppo-table thead th:last-child,
.ppo-table tbody td:last-child,
.ppo-table tfoot td:last-child {
    border-right: 0;
}

.group-header-cell {
    color: #1d4ed8 !important;
    background: var(--ppo-blue-soft) !important;
    border-right-color: #dbeafe !important;
    border-left: 1px solid #dbeafe;
    font-size: 10.5px !important;
    letter-spacing: 0;
}

.header-row-alt .group-header-cell,
.header-row-alt .group-label-cell {
    color: var(--ppo-teal) !important;
    background: var(--ppo-teal-soft) !important;
    border-color: #bbf7d0 !important;
}

.group-label-cell {
    max-width: 120px;
    padding: 5px 8px !important;
    overflow: hidden;
    color: #1e40af !important;
    background: var(--ppo-blue-soft) !important;
    border-left: 1px solid #dbeafe;
    font-size: 10.5px !important;
    font-weight: 800;
    letter-spacing: 0;
    text-align: left !important;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.ppo-table tbody td {
    padding: 8px 10px;
    border-right: 1px solid #edf2f7;
    border-bottom: 1px solid #edf2f7;
    text-align: center;
    vertical-align: middle;
    white-space: nowrap;
}

.ppo-table tbody tr:nth-child(even) {
    background: #fbfdff;
}

.ppo-table tbody tr:hover {
    background: #f1f5f9;
}

.ppo-table tbody tr.summary-row,
.ppo-table tbody tr.summary-row:nth-child(even),
.ppo-table tbody tr.summary-footer-row,
.ppo-table tbody tr.summary-footer-row:nth-child(even) {
    background: transparent;
}

.cell-dim {
    color: var(--ppo-faint);
    font-weight: 600;
}

.cell-group-label {
    max-width: 120px;
    overflow: hidden;
    color: #1d4ed8;
    background: #f8fafc;
    font-size: 10.5px;
    font-weight: 700;
    text-align: left !important;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.status-draft,
.status-submitted {
    display: inline-flex;
    align-items: center;
    min-height: 22px;
    padding: 2px 8px;
    border: 1px solid;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    line-height: 1;
}

.status-draft {
    color: #b45309;
    background: #fff7ed;
    border-color: #fed7aa;
}

.status-submitted {
    color: #047857;
    background: #ecfdf5;
    border-color: #a7f3d0;
}

.btn-summarize {
    min-height: 26px;
    padding: 3px 10px;
    color: #334155;
    background: #ffffff;
    border-color: var(--ppo-border-strong);
    font-size: 11px;
    font-weight: 700;
}

.btn-summarize:hover,
.btn-summarize:focus {
    color: var(--ppo-blue);
    background: var(--ppo-blue-soft);
    border-color: #bfdbfe;
}

.cell-comments {
    max-width: 260px;
    min-width: 130px;
    overflow: hidden;
    color: var(--ppo-muted);
    cursor: default;
    font-size: 11.5px;
    text-align: left !important;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.cell-zero {
    color: #cbd5e1;
}

.cell-total {
    color: var(--ppo-text);
    background: #f8fafc;
    font-weight: 800;
}

.ppo-link {
    color: var(--ppo-blue);
    font-size: 12px;
    font-weight: 700;
    text-decoration: none;
}

.ppo-link:hover,
.ppo-link:focus {
    color: #1d4ed8;
    text-decoration: underline;
}

.ppo-table tfoot td {
    position: sticky;
    bottom: 0;
    z-index: 2;
    padding: 10px;
    color: var(--ppo-text);
    background: #f8fafc;
    border-top: 1px solid var(--ppo-border-strong);
    border-right: 1px solid var(--ppo-border);
    font-size: 12.5px;
    font-weight: 800;
    text-align: center;
    white-space: nowrap;
}

.foot-label {
    color: var(--ppo-muted);
    font-size: 11px;
    letter-spacing: 0;
    text-align: right !important;
    text-transform: uppercase;
}

.foot-grand {
    color: var(--ppo-teal);
    background: var(--ppo-teal-soft);
    font-weight: 800;
}

.summary-row td {
    background: #f0f7ff;
    border-bottom: 1px solid #dbeafe;
    font-size: 12px;
}

.summary-row:hover td {
    background: #e7f1ff;
}

.summary-label-cell {
    color: #475569;
    font-weight: 700;
    padding-right: 14px !important;
    text-align: right !important;
}

.summary-total-cell {
    color: var(--ppo-text);
    font-weight: 800;
}

.summary-status {
    padding: 12px 0;
    color: var(--ppo-muted);
    background: #f0f7ff;
    font-size: 12.5px;
    font-weight: 600;
    text-align: center;
}

.summary-footer-row td {
    background: #eaf7f5;
    border-bottom: 1px solid #b7e4dd;
    font-size: 12px;
    font-weight: 800;
}

.summary-footer-row:hover td {
    background: #ddf1ed;
}

.summary-footer-label {
    color: var(--ppo-teal);
    font-size: 11px;
    letter-spacing: 0;
    text-transform: uppercase;
}

.summary-footer-num {
    color: #334155;
    font-weight: 800;
}

.summary-footer-grand {
    color: var(--ppo-teal);
    font-weight: 800;
}

.ppo-empty {
    padding: 46px 18px;
    color: var(--ppo-muted);
    background: var(--ppo-surface);
    border: 1px dashed var(--ppo-border-strong);
    border-radius: 8px;
    box-shadow: var(--ppo-shadow);
    text-align: center;
}

.ppo-empty-title {
    color: var(--ppo-text);
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0;
}

.ppo-empty-copy {
    margin-top: 5px;
    font-size: 13px;
    font-weight: 500;
}

@media (max-width: 1100px) {
    .ppo-controls {
        grid-template-columns: repeat(2, minmax(180px, 1fr));
    }

    .ppo-actions {
        justify-content: flex-start;
    }
}

@media (max-width: 640px) {
    .ppo-root {
        padding: 14px;
    }

    .ppo-header {
        padding: 14px;
    }

    .ppo-controls,
    .ppo-summary-bar {
        grid-template-columns: 1fr;
    }

    .summary-item + .summary-item {
        border-top: 1px solid var(--ppo-border);
        border-left: 0;
    }

    .ppo-actions {
        flex-wrap: wrap;
    }

    .btn-get,
    .btn-dl {
        justify-content: center;
        flex: 1 1 150px;
    }
}
</style>
