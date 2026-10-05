<template>
    <div class="audit-dashboard">
        <header class="dashboard-header">
            <div>
                <div class="title-line">
                    <h2>Audit Pending Finishing Plans</h2>
                    <span v-if="asOf" class="as-of">As of {{ formatDate(asOf) }}</span>
                </div>
                <p>Plans sitting in Dispatched or Fully Dispatched for over {{ thresholdDays }} days.</p>
            </div>
            <button type="button" class="secondary-button refresh-button" :disabled="loading" @click="loadDashboard">
                <svg :class="{ spinning: loading }" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M20 11a8.1 8.1 0 0 0-15.5-3M4 4v4h4M4 13a8.1 8.1 0 0 0 15.5 3M20 20v-4h-4" />
                </svg>
                {{ loading ? 'Refreshing' : 'Refresh' }}
            </button>
        </header>

        <section class="summary-grid" aria-label="Audit pending summary">
            <article class="summary-card">
                <span>Overdue Plans</span>
                <strong>{{ summary.overdue || 0 }}</strong>
            </article>
            <article class="summary-card">
                <span>Dispatched</span>
                <strong class="warning-text">{{ summary.dispatched || 0 }}</strong>
            </article>
            <article class="summary-card">
                <span>Fully Dispatched</span>
                <strong class="success-text">{{ summary.fully_dispatched || 0 }}</strong>
            </article>
            <article class="summary-card">
                <span>Oldest Pending</span>
                <div class="oldest-value">
                    <strong class="danger-text">{{ summary.oldest_days || 0 }}</strong>
                    <small>days</small>
                </div>
            </article>
        </section>

        <section class="filter-card" aria-label="Dashboard filters">
            <div class="filter-label">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16l-6.5 7.2V19l-3 1.5v-8.3L4 5Z" /></svg>
                <span>Filters</span>
            </div>
            <input v-model="filters.search" type="search" placeholder="Search Plan, Lot, or Item..." aria-label="Search Plan, Lot, or Item" />
            <select v-model="filters.status" aria-label="Filter by status">
                <option value="">All Statuses</option>
                <option value="Dispatched">Dispatched</option>
                <option value="Fully Dispatched">Fully Dispatched</option>
            </select>
            <select v-model="filters.age" aria-label="Filter by age">
                <option value="">All Ages</option>
                <option value="8-14">8-14 Days</option>
                <option value="15+">15+ Days</option>
            </select>
            <button type="button" class="secondary-button" @click="resetFilters">Reset</button>
        </section>

        <div v-if="errorMessage" class="state-card error-state">
            <strong>Could not load the dashboard</strong>
            <span>{{ errorMessage }}</span>
            <button type="button" class="secondary-button" @click="loadDashboard">Try again</button>
        </div>

        <div v-else-if="loading && !plans.length" class="state-card loading-state">
            <span class="loader" aria-hidden="true"></span>
            <span>Loading audit-pending plans...</span>
        </div>

        <div v-else-if="filteredPlans.length" class="table-shell">
            <table class="master-table">
                <thead>
                    <tr>
                        <th class="toggle-column"></th>
                        <th>Finishing Plan / Identity</th>
                        <th>Status</th>
                        <th>Status Since</th>
                        <th class="audit-cell-center">Age</th>
                        <th class="numeric">Total Cut</th>
                        <th class="numeric">Sewing Rx</th>
                        <th class="numeric">Packed</th>
                        <th class="numeric">Dispatched</th>
                        <th>Latest Dispatch</th>
                    </tr>
                </thead>
                <tbody>
                    <template v-for="plan in filteredPlans" :key="plan.name">
                        <tr class="plan-row" :class="{ expanded: isExpanded(plan.name) }" @click="togglePlan(plan.name)">
                            <td class="toggle-cell">
                                <svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
                            </td>
                            <td>
                                <button type="button" class="plan-link" @click.stop="openDocument('Finishing Plan', plan.name)">{{ plan.name }}</button>
                                <span class="identity-secondary">{{ plan.lot }}</span>
                                <span class="identity-item" :title="plan.item">{{ plan.item }}</span>
                            </td>
                            <td><span class="status-pill" :class="statusClass(plan.fp_status)">{{ plan.fp_status }}</span></td>
                            <td class="tabular">{{ formatDate(plan.status_since) }}</td>
                            <td class="audit-cell-center"><span class="age-badge" :class="`age-${ageTone(plan.age_days)}`">{{ plan.age_days }}d</span></td>
                            <td class="numeric tabular">{{ formatNumber(plan.total_cut) }}</td>
                            <td class="numeric tabular">{{ formatNumber(plan.sewing_received) }}</td>
                            <td class="numeric tabular">{{ formatNumber(plan.packed) }}</td>
                            <td class="numeric tabular dispatched-number">{{ formatNumber(plan.dispatched) }}</td>
                            <td>
                                <template v-if="plan.latest_dispatch">
                                    <span class="latest-date">{{ formatDate(plan.latest_dispatch.posting_date) }}</span>
                                    <span class="identity-secondary">{{ formatNumber(plan.latest_dispatch.pieces) }} pcs</span>
                                </template>
                                <span v-else class="identity-item">No dispatch history</span>
                            </td>
                        </tr>
                        <tr v-if="isExpanded(plan.name)" class="history-panel">
                            <td colspan="10">
                                <div class="history-content">
                                    <h3>
                                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h11v10H3zM14 10h4l3 3v4h-7zM7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM18 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" /></svg>
                                        Dispatch History
                                    </h3>
                                    <div v-if="plan.dispatch_history.length" class="history-shell">
                                        <table class="history-table">
                                            <thead><tr><th>Document</th><th>Posting Date</th><th>Destination</th><th>Item / Detail</th><th class="audit-cell-center">Boxes</th><th class="audit-cell-center">Pieces</th><th>Operator</th></tr></thead>
                                            <tbody>
                                                <tr v-for="history in plan.dispatch_history" :key="`${history.stock_entry}-${history.source_name}`">
                                                    <td><button type="button" class="document-link" @click.stop="showDispatchDetail(plan, history)">{{ history.document }}</button></td>
                                                    <td class="tabular">{{ formatDate(history.posting_date) }}</td>
                                                    <td>{{ history.destination || '—' }}</td>
                                                    <td>{{ history.item_detail || plan.item }}</td>
                                                    <td class="audit-cell-center tabular">{{ formatNumber(history.boxes) }}</td>
                                                    <td class="audit-cell-center tabular history-pieces">{{ formatNumber(history.pieces) }}</td>
                                                    <td>{{ history.operator || '—' }}</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                    <div v-else class="no-history">No submitted dispatch history is available.</div>
                                </div>
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>
        </div>

        <div v-else class="state-card empty-state">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4M8 8l6 6M14 8l-6 6" /></svg>
            <strong>No overdue plans match these filters</strong>
            <span>Clear or change the filters to see other pending plans.</span>
        </div>

        <footer class="dashboard-footer">
            <span>Showing {{ filteredPlans.length }} of {{ plans.length }} overdue plans</span>
            <span>Last updated: {{ lastUpdated }}</span>
        </footer>

        <div v-if="detailModal.open" class="modal-backdrop" @click.self="closeDetail">
            <section class="dispatch-modal" role="dialog" aria-modal="true" aria-labelledby="dispatch-detail-title">
                <header class="modal-header">
                    <div>
                        <span class="eyebrow">Dispatch Document</span>
                        <h2 id="dispatch-detail-title">Size-wise Dispatch Detail</h2>
                        <button v-if="detailModal.data.document" type="button" class="document-link modal-document" @click="openDispatchDocument(detailModal)">{{ detailModal.data.document }}</button>
                    </div>
                    <button type="button" class="modal-close" aria-label="Close dispatch detail" @click="closeDetail">×</button>
                </header>

                <div v-if="detailModal.loading" class="modal-loading"><span class="loader"></span> Loading dispatch details...</div>
                <template v-else>
                    <div class="meta-grid">
                        <div><span>Finishing Plan</span><strong>{{ detailModal.data.finishing_plan || '—' }}</strong></div>
                        <div><span>Posting Date</span><strong>{{ formatDate(detailModal.data.posting_date) }}</strong></div>
                        <div><span>Destination</span><strong>{{ detailModal.data.destination || '—' }}</strong></div>
                        <div><span>Item Detail</span><strong>{{ detailModal.data.item_detail || '—' }}</strong></div>
                        <div><span>Operator</span><strong>{{ detailModal.data.operator || '—' }}</strong></div>
                        <div><span>Total Dispatched</span><strong>{{ formatNumber(detailModal.data.total_dispatched) }} pcs</strong></div>
                    </div>
                    <div class="size-detail">
                        <div class="size-detail-heading"><h3>Size-wise detail</h3><span>Submitted quantities</span></div>
                        <div class="size-table-shell">
                            <table class="size-table">
                                <thead><tr><th>Size</th><th>Colour / Detail</th><th class="audit-cell-center">Pieces / Box</th><th class="audit-cell-center">Boxes</th><th class="audit-cell-center">Pieces</th></tr></thead>
                                <tbody>
                                    <tr v-for="(row, index) in detailModal.data.rows || []" :key="`${row.size}-${row.detail}-${index}`">
                                        <td class="size-value">{{ row.size }}</td><td>{{ row.detail }}</td><td class="audit-cell-center tabular">{{ formatNumber(row.pieces_per_box) }}</td><td class="audit-cell-center tabular">{{ formatNumber(row.boxes) }}</td><td class="audit-cell-center tabular size-pieces">{{ formatNumber(row.pieces) }}</td>
                                    </tr>
                                </tbody>
                                <tfoot><tr><td colspan="2">Total</td><td class="audit-cell-center muted">—</td><td class="audit-cell-center tabular">{{ formatNumber(detailModal.data.totals?.boxes) }}</td><td class="audit-cell-center tabular">{{ formatNumber(detailModal.data.totals?.pieces) }}</td></tr></tfoot>
                            </table>
                        </div>
                    </div>
                </template>
            </section>
        </div>
    </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ageTone, filterPlans } from './dashboard_utils.mjs'

const DASHBOARD_METHOD = 'production_api.production_api.page.audit_pending_finishing_plans.audit_pending_finishing_plans.get_dashboard_data'
const DETAIL_METHOD = 'production_api.production_api.page.audit_pending_finishing_plans.audit_pending_finishing_plans.get_dispatch_detail'

const loading = ref(false)
const errorMessage = ref('')
const asOf = ref('')
const thresholdDays = ref(7)
const summary = ref({})
const plans = ref([])
const expandedPlans = ref(new Set())
const lastUpdated = ref('Never')
const filters = reactive({ search: '', status: '', age: '' })
const detailModal = reactive({ open: false, loading: false, data: {}, history: null })

const filteredPlans = computed(() => filterPlans(plans.value, filters))
const formatNumber = value => new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(Number(value || 0))
const formatDate = value => value ? frappe.datetime.str_to_user(value) : '—'
const statusClass = status => status === 'Fully Dispatched' ? 'status-fully' : 'status-dispatched'
const isExpanded = name => expandedPlans.value.has(name)

function togglePlan(name) {
    const next = new Set(expandedPlans.value)
    next.has(name) ? next.delete(name) : next.add(name)
    expandedPlans.value = next
}

function resetFilters() {
    filters.search = ''
    filters.status = ''
    filters.age = ''
}

function openDocument(doctype, name) {
    frappe.set_route('Form', doctype, name)
}

function loadDashboard() {
    loading.value = true
    errorMessage.value = ''
    frappe.call({
        method: DASHBOARD_METHOD,
        callback: (response) => {
            const data = response.message || {}
            asOf.value = data.as_of || ''
            thresholdDays.value = data.threshold_days ?? 7
            summary.value = data.summary || {}
            plans.value = data.plans || []
            if (plans.value.length && !expandedPlans.value.size) {
                expandedPlans.value = new Set([plans.value[0].name])
            }
            lastUpdated.value = frappe.datetime.now_time()
        },
        error: (error) => {
            errorMessage.value = error?.message || 'Please refresh and try again.'
        },
        always: () => { loading.value = false },
    })
}

function showDispatchDetail(plan, history) {
    detailModal.open = true
    detailModal.loading = true
    detailModal.data = { document: history.document, finishing_plan: plan.name, rows: [], totals: {} }
    detailModal.history = history
    frappe.call({
        method: DETAIL_METHOD,
        args: {
            finishing_plan: plan.name,
            source_doctype: history.source_doctype,
            source_name: history.source_name,
            stock_entry: history.stock_entry,
        },
        callback: (response) => { detailModal.data = response.message || detailModal.data },
        error: () => {
            closeDetail()
            frappe.show_alert({ message: 'Could not load dispatch details', indicator: 'red' })
        },
        always: () => { detailModal.loading = false },
    })
}

function openDispatchDocument(modal) {
    const history = modal.history
    if (!history) return
    const doctype = history.source_doctype === 'Finishing Plan Dispatch' ? 'Finishing Plan Dispatch' : 'Stock Entry'
    const name = history.source_doctype === 'Finishing Plan Dispatch' ? history.source_name : history.stock_entry
    if (name) frappe.set_route('Form', doctype, name)
}

function closeDetail() {
    detailModal.open = false
    detailModal.loading = false
    detailModal.data = {}
    detailModal.history = null
}

function handleKeydown(event) {
    if (event.key === 'Escape' && detailModal.open) closeDetail()
}

onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
    loadDashboard()
})
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
.audit-dashboard { --border: #e2e8f0; --surface: #fff; --soft: #f8fafc; --primary: #1e293b; --body: #334155; --secondary: #64748b; --muted: #94a3b8; --blue: #1a73e8; max-width: 1400px; margin: 0 auto; padding: 18px 8px 28px; color: var(--body); }
.dashboard-header, .title-line, .filter-card, .filter-label, .refresh-button, .oldest-value, .history-content h3, .size-detail-heading { display: flex; align-items: center; }
.dashboard-header { justify-content: space-between; gap: 18px; margin-bottom: 20px; }
.dashboard-header h2 { margin: 0; color: var(--primary); font-size: 28.8px; font-weight: 800; }
.dashboard-header p { margin: 5px 0 0; color: var(--secondary); font-size: 15.6px; }
.title-line { flex-wrap: wrap; gap: 10px; }
.as-of { padding: 4px 8px; border: 1px solid var(--border); border-radius: 7px; background: #f1f5f9; color: var(--secondary); font-size: 14.4px; }
.secondary-button { min-height: 36px; padding: 7px 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: #475569; font-size: 15.6px; font-weight: 600; cursor: pointer; }
.secondary-button:hover { background: #f1f5f9; color: var(--primary); }
.secondary-button:disabled { cursor: wait; opacity: .65; }
.refresh-button { gap: 7px; white-space: nowrap; }
.refresh-button svg, .filter-label svg, .history-content h3 svg, .empty-state svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.spinning { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }
.summary-card { padding: 15px 17px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .03); }
.summary-card > span { display: block; margin-bottom: 4px; color: var(--secondary); font-size: 13.2px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.summary-card strong { color: var(--primary); font-size: 28.8px; font-variant-numeric: tabular-nums; }
.summary-card .warning-text { color: #d97706; }.summary-card .success-text { color: #059669; }.summary-card .danger-text { color: #dc2626; }
.oldest-value { gap: 5px; align-items: baseline; }.oldest-value small { color: var(--secondary); font-size: 14.4px; }
.filter-card { gap: 16px; margin-bottom: 20px; padding: 12px 16px; border: 1px solid #edf1f5; border-radius: 14px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .025); }
.filter-label { flex: none; gap: 8px; color: var(--secondary); font-size: 15.6px; font-weight: 700; }.filter-label svg { width: 16px; }
.filter-card input, .filter-card select { height: 38px; padding: 0 12px; border: 1px solid var(--border); border-radius: 10px; outline: none; background: var(--soft); color: var(--body); font-size: 15.6px; }
.filter-card input { min-width: 260px; flex: 1; }.filter-card select { min-width: 160px; }.filter-card input:focus, .filter-card select:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(26, 115, 232, .1); }
.table-shell, .history-shell, .size-table-shell { overflow-x: auto; }
.table-shell { border: 1px solid var(--border); border-radius: 12px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .025); }
table { width: 100%; border-collapse: collapse; }.master-table { min-width: 1080px; }
th { padding: 10px; border-bottom: 1px solid var(--border); background: var(--soft); color: #475569; font-size: 12px; font-weight: 700; letter-spacing: .025em; text-align: left; text-transform: uppercase; }
td { padding: 11px 10px; border-bottom: 1px solid var(--border); color: var(--body); font-size: 14.4px; font-weight: 500; vertical-align: middle; }
.plan-row { transition: background .15s ease; cursor: pointer; }.plan-row:hover, .plan-row.expanded { background: var(--soft); }.plan-row.expanded td { border-bottom: 0; }
.toggle-column, .toggle-cell { width: 34px; text-align: center; }.chevron { width: 16px; height: 16px; fill: none; stroke: var(--secondary); stroke-width: 2; transition: transform .2s ease; }.expanded .chevron { transform: rotate(90deg); }
.plan-link, .document-link { display: inline; padding: 0; border: 0; background: none; color: var(--blue); font: inherit; font-weight: 700; cursor: pointer; }.plan-link { display: block; color: var(--primary); }.document-link:hover, .plan-link:hover { color: #1557b0; text-decoration: underline; }
.identity-secondary, .identity-item, .latest-date { display: block; margin-top: 2px; }.identity-secondary { color: var(--secondary); font-size: 12px; }.identity-item { max-width: 205px; overflow: hidden; color: var(--muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.latest-date { margin-top: 0; color: var(--primary); }
.status-pill, .age-badge { display: inline-flex; align-items: center; justify-content: center; border-radius: 7px; font-size: 12px; font-weight: 700; white-space: nowrap; }.status-pill { padding: 4px 8px; border: 1px solid transparent; }.status-dispatched { border-color: #fde68a; background: #fef3c7; color: #d97706; }.status-fully { border-color: #a7f3d0; background: #d1fae5; color: #059669; }
.age-badge { padding: 3px 7px; }.age-warning { background: #fef3c7; color: #d97706; }.age-danger { background: #fee2e2; color: #dc2626; }.age-critical { background: #dc2626; color: #fff; }
.numeric { text-align: right; }.audit-cell-center { text-align: center !important; }.tabular { font-variant-numeric: tabular-nums; }.dispatched-number, .history-pieces, .size-pieces { color: var(--blue); font-weight: 700; }
.history-panel > td { padding: 0; border-top: 1px dashed var(--border); background: var(--soft); }.history-content { padding: 14px 14px 18px 52px; }.history-content h3 { gap: 7px; margin: 0 0 10px; color: var(--primary); font-size: 14.4px; font-weight: 800; }.history-content h3 svg { width: 14px; color: var(--secondary); }
.history-table { min-width: 760px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }.history-table th { padding: 8px 9px; background: #f1f5f9; font-size: 10.8px; }.history-table td { padding: 8px 9px; border-bottom-color: #f1f5f9; font-size: 13.2px; }.history-table tr:last-child td { border-bottom: 0; }.no-history { padding: 16px; border: 1px solid var(--border); border-radius: 8px; background: #fff; color: var(--secondary); font-size: 14.4px; }
.state-card { display: flex; min-height: 180px; align-items: center; justify-content: center; flex-direction: column; gap: 8px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); color: var(--secondary); text-align: center; }.state-card strong { color: var(--primary); }.empty-state svg { width: 30px; height: 30px; color: var(--muted); }.error-state { border-color: #fecaca; background: #fffafa; color: #b91c1c; }
.loader { width: 22px; height: 22px; border: 3px solid #dbeafe; border-top-color: var(--blue); border-radius: 50%; animation: spin .8s linear infinite; }
.dashboard-footer { display: flex; justify-content: space-between; gap: 14px; padding: 12px 6px 0; color: var(--secondary); font-size: 12px; }
.modal-backdrop { position: fixed; inset: 0; z-index: 1050; display: flex; align-items: center; justify-content: center; padding: 22px; background: rgba(15, 23, 42, .4); backdrop-filter: blur(2px); }.dispatch-modal { width: min(760px, 100%); max-height: calc(100vh - 44px); overflow-y: auto; border: 1px solid var(--border); border-radius: 15px; background: #fff; box-shadow: 0 24px 60px rgba(15, 23, 42, .22); }.modal-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 18px 22px; border-bottom: 1px solid var(--border); }.eyebrow { color: var(--secondary); font-size: 10.8px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }.modal-header h2 { margin: 3px 0 2px; color: var(--primary); font-size: 21.6px; }.modal-document { font-size: 13.2px; }.modal-close { width: 34px; height: 34px; border: 1px solid var(--border); border-radius: 9px; background: #fff; color: var(--secondary); font-size: 24px; line-height: 1; cursor: pointer; }.modal-close:hover { background: var(--soft); color: var(--primary); }.modal-loading { display: flex; min-height: 210px; align-items: center; justify-content: center; gap: 10px; color: var(--secondary); }
.meta-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; padding: 16px 22px; border-bottom: 1px solid var(--border); background: var(--soft); }.meta-grid span { display: block; margin-bottom: 3px; color: var(--secondary); font-size: 10.8px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }.meta-grid strong { color: var(--primary); font-size: 13.2px; }
.size-detail { padding: 18px 22px 22px; }.size-detail-heading { justify-content: space-between; margin-bottom: 10px; }.size-detail-heading h3 { margin: 0; color: var(--primary); font-size: 14.4px; }.size-detail-heading span { color: var(--secondary); font-size: 10.8px; }.size-table { min-width: 560px; border: 1px solid var(--border); border-radius: 9px; }.size-table th { padding: 8px 10px; font-size: 10.8px; }.size-table td { padding: 9px 10px; border-bottom-color: #f1f5f9; font-size: 13.2px; }.size-table tfoot td { border-bottom: 0; background: var(--soft); color: var(--primary); font-weight: 800; }.size-value { color: var(--primary); font-weight: 800; }.muted { color: var(--secondary) !important; }
@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.filter-card { flex-wrap: wrap; }.filter-card input { min-width: 220px; }.filter-card select { flex: 1; }.meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .audit-dashboard { padding-top: 10px; }.dashboard-header { align-items: flex-start; }.dashboard-header h2 { font-size: 24px; }.title-line { align-items: flex-start; }.summary-grid { gap: 9px; }.summary-card { padding: 12px; }.filter-card > * { width: 100%; }.filter-card input, .filter-card select { min-width: 100%; width: 100%; }.dashboard-footer { flex-direction: column; }.history-content { padding-left: 14px; }.meta-grid { grid-template-columns: 1fr; }.modal-backdrop { padding: 10px; } }
</style>
