<template>
    <div class="audit-dashboard">
        <header class="dashboard-header">
            <div>
                <div class="title-line">
                    <h2>Audit Pending Finishing Plans</h2>
                    <span v-if="asOf" class="as-of">As of {{ formatDate(asOf) }}</span>
                </div>
            </div>
            <button type="button" class="secondary-button refresh-button" :disabled="loading" @click="refreshDashboard">
                <svg :class="{ spinning: loading }" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M20 11a8.1 8.1 0 0 0-15.5-3M4 4v4h4M4 13a8.1 8.1 0 0 0 15.5 3M20 20v-4h-4" />
                </svg>
                {{ loading ? 'Refreshing' : 'Refresh' }}
            </button>
        </header>

        <section class="summary-grid" :class="{ 'summary-grid--partial': activePartialMode }" aria-label="Audit pending summary">
            <article class="summary-card">
                <span>Overdue Plans</span>
                <strong>{{ summary.overdue || 0 }}</strong>
            </article>
            <article class="summary-card">
                <span>{{ activePartialMode ? 'Partially Dispatched' : 'Dispatched' }}</span>
                <strong class="warning-text">{{ activePartialMode ? (summary.partially_dispatched || 0) : (summary.dispatched || 0) }}</strong>
            </article>
            <article v-if="!activePartialMode" class="summary-card">
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
            <input v-model="filters.plan" class="filter-input" type="search" placeholder="Finishing Plan" aria-label="Filter by Finishing Plan" />
            <input v-model="filters.lot" class="filter-input" type="search" placeholder="Lot" aria-label="Filter by Lot" />
            <input v-model="filters.item" class="filter-input filter-item" type="search" placeholder="Item" aria-label="Filter by Item" />
            <select v-model="filters.status" aria-label="Filter by status">
                <option value="">All Statuses</option>
                <option value="Partially Dispatched">Partially Dispatched</option>
                <option value="Dispatched">Dispatched</option>
                <option value="Fully Dispatched">Fully Dispatched</option>
            </select>
            <select v-model="filters.age" aria-label="Filter by age">
                <option value="">All Ages</option>
                <option value="8-14">8-14 Days</option>
                <option value="15+">15+ Days</option>
            </select>
            <label class="partial-dispatched-toggle">
                <input v-model="showPartiallyDispatched" type="checkbox" />
                <span>Show Partially Dispatched</span>
            </label>
            <button type="button" class="generate-button" :disabled="loading" @click="generateDashboard">
                <span v-if="loading" class="loader generate-loader" aria-hidden="true"></span>
                Generate
            </button>
            <button type="button" class="secondary-button" @click="resetFilters">Reset</button>
        </section>

        <div v-if="errorMessage" class="state-card error-state">
            <strong>Could not load the dashboard</strong>
            <span>{{ errorMessage }}</span>
            <button type="button" class="secondary-button" @click="refreshDashboard">Try again</button>
        </div>

        <div v-else-if="loading && !plans.length" class="state-card loading-state">
            <span class="loader" aria-hidden="true"></span>
            <span>Loading audit-pending plans...</span>
        </div>

        <div v-else class="master-detail-layout">
            <section class="master-panel" aria-label="Audit-pending finishing plans">
                <div v-if="filteredPlans.length" class="master-scroll">
                    <table class="master-table">
                        <thead>
                            <tr>
                                <th class="plan-column">Item / Lot / Finishing Plan</th>
                                <th>Status / Age</th>
                                <th class="numeric">Total Cut</th>
                                <th class="numeric">Sewing Rx</th>
                                <th class="numeric">Packed</th>
                                <th class="numeric">Boxes Dispatched</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="plan in filteredPlans"
                                :key="plan.name"
                                class="plan-row"
                                :class="{ selected: selectedPlan?.name === plan.name }"
                                tabindex="0"
                                @click="selectPlan(plan.name)"
                                @keydown.enter="selectPlan(plan.name)"
                            >
                                <td>
                                    <dl class="plan-identity">
                                        <div><dt>Item</dt><dd class="identity-value identity-value--item">{{ plan.item || '—' }}</dd></div>
                                        <div><dt>Lot</dt><dd class="identity-value identity-value--lot">{{ plan.lot || '—' }}</dd></div>
                                        <div><dt>Plan</dt><dd class="identity-plan"><button type="button" class="plan-link master-plan-link" @click.stop="openDocument('Finishing Plan', plan.name)">{{ plan.name }}</button></dd></div>
                                    </dl>
                                </td>
                                <td>
                                    <div class="status-age">
                                        <span class="status-pill" :class="statusClass(plan.fp_status)">{{ plan.fp_status }}</span>
                                        <span class="age-badge" :class="`age-${ageTone(plan.age_days)}`">{{ plan.age_days }}d</span>
                                    </div>
                                    <span class="identity-secondary">Since {{ formatDate(plan.status_since) }}</span>
                                </td>
                                <td class="numeric tabular">{{ formatNumber(plan.total_cut) }}</td>
                                <td class="numeric tabular">{{ formatNumber(plan.sewing_received) }}</td>
                                <td class="numeric tabular">{{ formatNumber(plan.packed) }}</td>
                                <td class="numeric tabular dispatched-number">{{ formatNumber(totalDispatchBoxes(plan.dispatch_history)) }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div v-else class="state-card empty-state master-empty">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4M8 8l6 6M14 8l-6 6" /></svg>
                    <strong>No overdue plans match these filters</strong>
                    <span>Clear or change the filters to see other pending plans.</span>
                </div>
                <footer class="dashboard-footer">
                    <span>Showing {{ filteredPlans.length }} of {{ plans.length }} overdue plans</span>
                    <span>Last updated: {{ lastUpdated }}</span>
                </footer>
            </section>

            <aside class="detail-panel" aria-label="Selected finishing plan audit snapshot">
                <template v-if="selectedPlan">
                    <header class="detail-header">
                        <div class="detail-title-row">
                            <div class="detail-title-main">
                                <dl class="detail-identity">
                                    <div><dt>Item</dt><dd class="identity-value identity-value--item">{{ selectedPlan.item || '—' }}</dd></div>
                                    <div><dt>Lot</dt><dd class="identity-value identity-value--lot">{{ selectedPlan.lot || '—' }}</dd></div>
                                    <div><dt>Plan</dt><dd class="identity-plan"><button type="button" class="plan-link detail-plan-link" @click="openDocument('Finishing Plan', selectedPlan.name)">{{ selectedPlan.name }}</button></dd></div>
                                </dl>
                            </div>
                            <div class="detail-status">
                                <span class="status-pill" :class="statusClass(selectedPlan.fp_status)">{{ selectedPlan.fp_status }}</span>
                                <span class="age-badge" :class="`age-${ageTone(selectedPlan.age_days)}`">{{ selectedPlan.age_days }} days</span>
                            </div>
                        </div>
                    </header>

                    <div class="detail-scroll">
                        <section class="pending-breakdown" aria-label="Pending quantity breakdown">
                            <div class="pending-heading">
                                <div>
                                    <h3>
                                        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>
                                        Pending Quantity
                                    </h3>
                                </div>
                            </div>

                            <div v-if="isPendingLoading(selectedPlan.name)" class="pending-state">
                                <span class="loader pending-loader" aria-hidden="true"></span>
                                <span>Loading current pending quantities...</span>
                            </div>
                            <div v-else-if="pendingErrors[selectedPlan.name]" class="pending-state pending-error">
                                <span>{{ pendingErrors[selectedPlan.name] }}</span>
                                <button type="button" class="secondary-button" @click="loadPendingBreakdown(selectedPlan.name)">Try again</button>
                            </div>
                            <template v-else-if="selectedPendingParts.length">
                                <div v-if="shouldShowPartTabs(selectedPendingParts)" class="part-tabs" role="tablist" aria-label="Finishing plan parts">
                                    <button
                                        v-for="part in selectedPendingParts"
                                        :key="part.name"
                                        type="button"
                                        role="tab"
                                        :aria-selected="selectedPart?.name === part.name"
                                        :class="{ active: selectedPart?.name === part.name }"
                                        @click="selectPart(part.name)"
                                    >
                                        {{ part.name }}
                                    </button>
                                </div>

                                <div v-if="selectedPart" class="pending-grid">
                                    <article v-for="category in selectedPart.categories" :key="category.key" class="pending-card" :class="`pending-card--${pendingCategoryTone(category.key)}`">
                                        <header class="pending-card-header">
                                            <h4>{{ category.label }}</h4>
                                            <span>{{ formatNumber(category.total) }} pcs</span>
                                        </header>
                                        <div class="pending-table-shell">
                                            <table class="pending-table">
                                                <thead>
                                                    <tr>
                                                        <th>Colour</th>
                                                        <th v-for="size in selectedPart.sizes" :key="size" class="audit-cell-center">{{ size }}</th>
                                                        <th class="numeric">Total</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    <tr v-for="row in category.rows" :key="row.colour">
                                                        <td>{{ row.colour }}</td>
                                                        <td v-for="(value, index) in row.values" :key="selectedPart.sizes[index]" class="audit-cell-center tabular">{{ formatMatrixNumber(value) }}</td>
                                                        <td class="numeric tabular matrix-total">{{ formatNumber(row.total) }}</td>
                                                    </tr>
                                                </tbody>
                                                <tfoot>
                                                    <tr>
                                                        <td>Total</td>
                                                        <td v-for="(value, index) in category.size_totals" :key="selectedPart.sizes[index]" class="audit-cell-center tabular">{{ formatMatrixNumber(value) }}</td>
                                                        <td class="numeric tabular">{{ formatNumber(category.total) }}</td>
                                                    </tr>
                                                </tfoot>
                                            </table>
                                        </div>
                                    </article>
                                </div>
                            </template>
                            <div v-else class="pending-state">No pending quantities are available.</div>
                        </section>

                        <section class="dispatch-history" aria-label="Dispatch history">
                            <h3>
                                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h11v10H3zM14 10h4l3 3v4h-7zM7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM18 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" /></svg>
                                Dispatch History
                            </h3>
                            <div v-if="selectedPlan.dispatch_history.length" class="history-shell">
                                <table class="history-table">
                                    <thead><tr><th>Posting Date</th><th class="numeric">Boxes</th><th class="numeric">Pieces</th><th class="history-action"></th></tr></thead>
                                    <tbody>
                                        <tr
                                            v-for="history in selectedPlan.dispatch_history"
                                            :key="`${history.stock_entry}-${history.source_name}`"
                                            class="history-row"
                                            tabindex="0"
                                            @click="showDispatchDetail(selectedPlan, history)"
                                            @keydown.enter="showDispatchDetail(selectedPlan, history)"
                                        >
                                            <td class="tabular">{{ formatDate(history.posting_date) }}</td>
                                            <td class="numeric tabular">{{ formatNumber(history.boxes) }}</td>
                                            <td class="numeric tabular history-pieces">{{ formatNumber(history.pieces) }}</td>
                                            <td class="history-action"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg></td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                            <div v-else class="no-history">No submitted dispatch history is available.</div>
                        </section>
                    </div>
                </template>
                <div v-else class="state-card detail-empty">
                    <strong>Select a Finishing Plan</strong>
                    <span>Choose a plan from the list to review its pending quantities and dispatches.</span>
                </div>
            </aside>
        </div>

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
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
    ageTone,
    buildDashboardRequest,
    filterPlans,
    isCurrentPendingGeneration,
    needsPendingBreakdown,
    pendingCategoryTone,
    quantityOrDash,
    resolveSelectedPlanName,
    shouldShowPartTabs,
    totalDispatchBoxes,
    visiblePendingParts,
} from './dashboard_utils.mjs'

const DETAIL_METHOD = 'production_api.production_api.page.audit_pending_finishing_plans.audit_pending_finishing_plans.get_dispatch_detail'
const PENDING_METHOD = 'production_api.production_api.page.audit_pending_finishing_plans.audit_pending_finishing_plans.get_pending_breakdown'

const loading = ref(false)
const errorMessage = ref('')
const asOf = ref('')
const summary = ref({})
const plans = ref([])
const selectedPlanName = ref('')
const activePartName = ref('')
const lastUpdated = ref('Never')
const showPartiallyDispatched = ref(false)
const activePartialMode = ref(false)
const filters = reactive({ plan: '', lot: '', item: '', status: '', age: '' })
const detailModal = reactive({ open: false, loading: false, data: {}, history: null })
const pendingBreakdowns = reactive({})
const pendingErrors = reactive({})
const pendingLoading = ref(new Set())
const pendingGeneration = ref(0)

const pendingParts = name => visiblePendingParts(pendingBreakdowns[name]?.parts)
const filteredPlans = computed(() => filterPlans(plans.value, filters))
const selectedPlan = computed(() => {
    const name = resolveSelectedPlanName(filteredPlans.value, selectedPlanName.value)
    return filteredPlans.value.find(plan => plan.name === name) || null
})
const selectedPendingParts = computed(() => selectedPlan.value ? pendingParts(selectedPlan.value.name) : [])
const selectedPart = computed(() => (
    selectedPendingParts.value.find(part => part.name === activePartName.value)
    || selectedPendingParts.value[0]
    || null
))
const formatNumber = value => new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(Number(value || 0))
const formatMatrixNumber = value => {
    const quantity = quantityOrDash(value)
    return quantity === '—' ? quantity : formatNumber(quantity)
}
const formatDate = value => value ? frappe.datetime.str_to_user(value) : '—'
const statusClass = status => {
    if (status === 'Fully Dispatched') return 'status-fully'
    if (status === 'Partially Dispatched') return 'status-partial'
    return 'status-dispatched'
}
const isPendingLoading = name => pendingLoading.value.has(name)

function selectPlan(name) {
    if (!name) return
    selectedPlanName.value = name
    activePartName.value = ''
    loadPendingBreakdown(name)
}

function selectPart(name) {
    activePartName.value = name
}

function loadPendingBreakdown(name) {
    if (!needsPendingBreakdown(pendingBreakdowns, pendingLoading.value, name)) return

    const requestGeneration = pendingGeneration.value
    delete pendingErrors[name]
    pendingLoading.value = new Set([...pendingLoading.value, name])
    frappe.call({
        method: PENDING_METHOD,
        args: { finishing_plan: name },
        callback: (response) => {
            if (!isCurrentPendingGeneration(requestGeneration, pendingGeneration.value)) return
            pendingBreakdowns[name] = response.message || { finishing_plan: name, parts: [] }
        },
        error: () => {
            if (!isCurrentPendingGeneration(requestGeneration, pendingGeneration.value)) return
            pendingErrors[name] = 'Could not load current pending quantities.'
        },
        always: () => {
            if (!isCurrentPendingGeneration(requestGeneration, pendingGeneration.value)) return
            const next = new Set(pendingLoading.value)
            next.delete(name)
            pendingLoading.value = next
        },
    })
}

function clearPendingBreakdowns() {
    pendingGeneration.value += 1
    pendingLoading.value = new Set()
    Object.keys(pendingBreakdowns).forEach(name => delete pendingBreakdowns[name])
    Object.keys(pendingErrors).forEach(name => delete pendingErrors[name])
}

function resetFilters() {
    filters.plan = ''
    filters.lot = ''
    filters.item = ''
    filters.status = ''
    filters.age = ''
}

function openDocument(doctype, name) {
    frappe.set_route('Form', doctype, name)
}

function generateDashboard() {
    filters.status = ''
    loadDashboard(showPartiallyDispatched.value)
}

function refreshDashboard() {
    loadDashboard(activePartialMode.value)
}

function loadDashboard(partialMode = false) {
    const requestedPartialMode = Boolean(partialMode)
    const request = buildDashboardRequest(requestedPartialMode)
    loading.value = true
    errorMessage.value = ''
    clearPendingBreakdowns()
    frappe.call({
        method: request.method,
        args: request.args,
        callback: (response) => {
            const data = response.message || {}
            asOf.value = data.as_of || ''
            summary.value = data.summary || {}
            plans.value = data.plans || []
            activePartialMode.value = requestedPartialMode
            selectedPlanName.value = resolveSelectedPlanName(plans.value, selectedPlanName.value)
            activePartName.value = ''
            loadPendingBreakdown(selectedPlanName.value)
            lastUpdated.value = frappe.datetime.now_time()
        },
        error: (error) => {
            errorMessage.value = error?.message || 'Please refresh and try again.'
        },
        always: () => { loading.value = false },
    })
}

watch(
    () => selectedPlan.value?.name || '',
    (name) => {
        if (!name) return
        if (selectedPlanName.value !== name) selectedPlanName.value = name
        activePartName.value = ''
        loadPendingBreakdown(name)
    },
)

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
    loadDashboard(false)
})
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
.audit-dashboard {
    --border: #e2e8f0;
    --surface: #fff;
    --soft: #f8fafc;
    --primary: #1e293b;
    --body: #334155;
    --secondary: #64748b;
    --muted: #94a3b8;
    --blue: #1a73e8;
    box-sizing: border-box;
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 18px 16px 28px;
    color: var(--body);
}
.dashboard-header, .title-line, .filter-card, .filter-label, .refresh-button, .oldest-value, .status-age, .pending-heading h3, .dispatch-history h3, .size-detail-heading { display: flex; align-items: center; }
.dashboard-header { justify-content: space-between; gap: 18px; margin-bottom: 16px; }
.dashboard-header h2 { margin: 0; color: var(--primary); font-size: 24px; font-weight: 800; }
.title-line { flex-wrap: wrap; gap: 10px; }
.as-of { padding: 4px 8px; border: 1px solid var(--border); border-radius: 7px; background: #f1f5f9; color: var(--secondary); font-size: 13px; }
.secondary-button { min-height: 36px; padding: 7px 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: #475569; font-size: 14px; font-weight: 600; cursor: pointer; }
.secondary-button:hover { background: #f1f5f9; color: var(--primary); }
.secondary-button:disabled { cursor: wait; opacity: .65; }
.refresh-button { gap: 7px; white-space: nowrap; }
.refresh-button svg, .filter-label svg, .pending-heading svg, .dispatch-history h3 svg, .empty-state svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.spinning { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 16px; }
.summary-grid--partial { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.summary-card { padding: 12px 14px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .03); }
.summary-card > span { display: block; margin-bottom: 4px; color: var(--secondary); font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.summary-card strong { color: var(--primary); font-size: 21px; font-variant-numeric: tabular-nums; }
.summary-card .warning-text { color: #d97706; }
.summary-card .success-text { color: #059669; }
.summary-card .danger-text { color: #dc2626; }
.oldest-value { gap: 5px; align-items: baseline; }
.oldest-value small { color: var(--secondary); font-size: 12px; }

.filter-card { gap: 10px; margin-bottom: 18px; padding: 11px 14px; border: 1px solid #edf1f5; border-radius: 14px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .025); }
.filter-label { flex: none; gap: 8px; color: var(--secondary); font-size: 14px; font-weight: 700; }
.filter-label svg { width: 16px; }
.filter-card input[type="search"], .filter-card select { height: 38px; min-width: 0; padding: 0 11px; border: 1px solid var(--border); border-radius: 10px; outline: none; background: var(--soft); color: var(--body); font-size: 14px; }
.filter-card input[type="search"] { flex: 1; }
.filter-card .filter-item { flex: 1.7; }
.filter-card select { width: 150px; flex: none; }
.filter-card input[type="search"]:focus, .filter-card select:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(26, 115, 232, .1); }
.partial-dispatched-toggle { display: inline-flex; flex: none; align-items: center; gap: 7px; height: 38px; margin: 0; color: #475569; font-size: 12px; font-weight: 700; white-space: nowrap; cursor: pointer; }
.partial-dispatched-toggle input { width: 15px; height: 15px; margin: 0; accent-color: var(--blue); }
.generate-button { display: inline-flex; min-height: 36px; align-items: center; justify-content: center; gap: 7px; padding: 7px 15px; border: 1px solid var(--blue); border-radius: 10px; background: var(--blue); color: #fff; font-size: 14px; font-weight: 700; cursor: pointer; }
.generate-button:hover { background: #1557b0; }
.generate-button:disabled { cursor: wait; opacity: .65; }
.generate-loader { width: 14px !important; height: 14px !important; border-width: 2px !important; }

.master-detail-layout { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 18px; height: clamp(540px, calc(100vh - 330px), 760px); min-height: 0; }
.master-panel, .detail-panel { min-width: 0; min-height: 0; overflow: hidden; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); box-shadow: 0 4px 12px rgba(15, 23, 42, .025); }
.master-panel, .detail-panel { display: flex; flex-direction: column; }
.master-scroll, .detail-scroll { min-height: 0; overflow: auto; }
.master-scroll, .detail-scroll, .pending-table-shell, .history-shell, .size-table-shell { scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }
.master-table, .pending-table, .history-table, .size-table { width: 100%; border-collapse: collapse; }
.master-table { min-width: 650px; table-layout: fixed; }
.master-table .plan-column { width: 32%; }
.master-table th, .pending-table th, .history-table th, .size-table th { padding: 9px 8px; border-bottom: 1px solid var(--border); background: var(--soft); color: #475569; font-size: 10.5px; font-weight: 700; letter-spacing: .025em; text-align: left; text-transform: uppercase; }
.master-table td, .pending-table td, .history-table td, .size-table td { padding: 10px 8px; border-bottom: 1px solid var(--border); color: var(--body); font-size: 13px; font-weight: 500; vertical-align: middle; }
.plan-row { transition: background .15s ease; cursor: pointer; }
.plan-row:hover, .plan-row:focus { background: var(--soft); outline: none; }
.plan-row.selected { background: #eff6ff; }
.plan-row.selected td { border-bottom-color: #bfdbfe; }
.plan-link, .document-link { display: inline; padding: 0; border: 0; background: none; color: var(--blue); font: inherit; font-weight: 700; cursor: pointer; }
.plan-link { display: block; color: var(--primary); }
.master-plan-link { color: var(--muted); font-size: 10px; font-weight: 500; line-height: 1.3; }
.document-link:hover, .plan-link:hover { color: #1557b0; text-decoration: underline; }
.identity-secondary { display: block; margin-top: 2px; }
.identity-secondary { color: var(--secondary); font-size: 11px; }
.plan-identity, .detail-identity { display: grid; gap: 2px; margin: 0; }
.plan-identity > div, .detail-identity > div { display: grid; grid-template-columns: 34px minmax(0, 1fr); align-items: start; gap: 6px; }
.plan-identity dt, .detail-identity dt { margin: 1px 0 0; color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: .05em; line-height: 1.3; text-transform: uppercase; }
.identity-value { min-width: 0; margin: 0; color: var(--secondary); font-size: 12.5px; font-weight: 700; line-height: 1.3; overflow-wrap: anywhere; }
.identity-value--item { overflow: visible; color: var(--primary); font-size: 13px; font-weight: 700; text-overflow: clip; white-space: normal; }
.identity-plan { min-width: 0; margin: 0; }
.status-age { flex-wrap: wrap; gap: 6px; }
.status-pill, .age-badge { display: inline-flex; align-items: center; justify-content: center; border-radius: 7px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.status-pill { padding: 4px 8px; border: 1px solid transparent; }
.status-dispatched { border-color: #fde68a; background: #fef3c7; color: #d97706; }
.status-partial { border-color: #fed7aa; background: #fff7ed; color: #c2410c; }
.status-fully { border-color: #a7f3d0; background: #d1fae5; color: #059669; }
.age-badge { padding: 3px 7px; }
.age-warning { background: #fef3c7; color: #d97706; }
.age-danger { background: #fee2e2; color: #dc2626; }
.age-critical { background: #dc2626; color: #fff; }
.numeric { text-align: right !important; }
.audit-cell-center { text-align: center !important; }
.tabular { font-variant-numeric: tabular-nums; }
.dispatched-number, .history-pieces, .size-pieces { color: var(--blue); font-weight: 700; }
.dashboard-footer { display: flex; flex: none; justify-content: space-between; gap: 14px; padding: 9px; border-top: 1px solid var(--border); background: var(--soft); color: var(--secondary); font-size: 11px; }

.detail-header { flex: none; padding: 14px 16px; border-bottom: 1px solid var(--border); background: var(--soft); }
.detail-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.detail-title-main { min-width: 0; flex: 1; }
.detail-plan-link { color: var(--muted); font-size: 10px; font-weight: 500; line-height: 1.3; }
.detail-identity { gap: 4px; }
.detail-identity > div { grid-template-columns: 38px minmax(0, 1fr); }
.detail-identity .identity-value { color: var(--secondary); font-size: 13px; }
.detail-identity .identity-value--item { color: var(--primary); font-size: 15px; font-weight: 700; }
.detail-status { display: flex; align-items: flex-end; flex-direction: column; gap: 5px; }
.detail-scroll { padding: 14px 16px 18px; }
.detail-empty { flex: 1; border: 0; }

.pending-breakdown { margin: 0; }
.pending-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.pending-heading h3, .dispatch-history h3 { gap: 7px; margin: 0; color: var(--primary); font-size: 12px; font-weight: 800; }
.pending-heading h3 svg, .dispatch-history h3 svg { width: 14px; color: var(--secondary); }
.pending-state { display: flex; min-height: 82px; align-items: center; justify-content: center; gap: 9px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--secondary); font-size: 12px; text-align: center; }
.pending-error { border-color: #fecaca; background: #fffafa; color: #b91c1c; }
.pending-loader { width: 17px !important; height: 17px !important; border-width: 2px !important; }
.part-tabs { display: flex; gap: 16px; margin-bottom: 12px; border-bottom: 1px solid var(--border); }
.part-tabs button { padding: 0 0 7px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--secondary); font-size: 12px; font-weight: 700; cursor: pointer; }
.part-tabs button:hover { color: var(--primary); }
.part-tabs button.active { border-bottom-color: var(--blue); color: var(--blue); }
.pending-grid { display: grid; grid-template-columns: 1fr; gap: 11px; }
.pending-card { min-width: 0; overflow: hidden; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); box-shadow: 0 2px 8px rgba(15, 23, 42, .02); }
.pending-card-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 7px 10px; border-bottom: 1px solid var(--border); background: #f1f5f9; }
.pending-card-header h4 { margin: 0; color: var(--primary); font-size: 11px; font-weight: 800; }
.pending-card-header span { padding: 2px 7px; border-radius: 6px; background: #e2e8f0; color: #475569; font-size: 10px; font-weight: 800; white-space: nowrap; }
.pending-card--loose .pending-card-header { border-bottom-color: #bfdbfe; background: #eff6ff; }
.pending-card--loose .pending-card-header h4 { color: #1a73e8; }
.pending-card--loose .pending-card-header span { background: #dbeafe; color: #1557b0; }
.pending-card--loose-set .pending-card-header { border-bottom-color: #cbd5e1; background: #f1f5f9; }
.pending-card--rejected .pending-card-header { border-bottom-color: #fecaca; background: #fff1f2; }
.pending-card--rejected .pending-card-header h4 { color: #b91c1c; }
.pending-card--rejected .pending-card-header span { background: #fee2e2; color: #b91c1c; }
.pending-card--rework .pending-card-header { border-bottom-color: #fde68a; background: #fffbeb; }
.pending-card--rework .pending-card-header h4 { color: #b45309; }
.pending-card--rework .pending-card-header span { background: #fef3c7; color: #b45309; }
.pending-table-shell, .history-shell, .size-table-shell { overflow-x: auto; }
.pending-table { min-width: 560px; }
.pending-table th { padding: 7px 6px; background: #fff; font-size: 9.5px; text-align: center; white-space: nowrap; }
.pending-table td { padding: 7px 6px; border-bottom-color: #f1f5f9; font-size: 11px; text-align: center; }
.pending-table th:first-child, .pending-table td:first-child { min-width: 112px; text-align: left; }
.pending-table tbody tr:last-child td { border-bottom: 0; }
.pending-table tfoot td { border-top: 1px solid var(--border); border-bottom: 0; background: var(--soft); color: var(--primary); font-weight: 800; }
.matrix-total { color: var(--primary); font-weight: 800; }

.dispatch-history { margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--border); }
.dispatch-history h3 { margin-bottom: 8px; }
.history-table { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
.history-table th { padding: 8px 9px; background: #f1f5f9; font-size: 10px; }
.history-table td { padding: 8px 9px; border-bottom-color: #f1f5f9; font-size: 12px; }
.history-table tr:last-child td { border-bottom: 0; }
.history-row { cursor: pointer; }
.history-row:hover, .history-row:focus { outline: none; background: var(--soft); }
.history-row:hover td, .history-row:focus td { color: var(--blue); }
.history-action { width: 28px; text-align: center !important; }
.history-action svg { width: 14px; height: 14px; fill: none; stroke: var(--secondary); stroke-width: 2; }
.no-history { padding: 16px; border: 1px solid var(--border); border-radius: 8px; background: #fff; color: var(--secondary); font-size: 12px; text-align: center; }

.state-card { display: flex; min-height: 180px; align-items: center; justify-content: center; flex-direction: column; gap: 8px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); color: var(--secondary); text-align: center; }
.state-card strong { color: var(--primary); }
.empty-state svg { width: 30px; height: 30px; color: var(--muted); }
.master-empty { flex: 1; border: 0; border-radius: 0; }
.error-state { border-color: #fecaca; background: #fffafa; color: #b91c1c; }
.loader { width: 22px; height: 22px; border: 3px solid #dbeafe; border-top-color: var(--blue); border-radius: 50%; animation: spin .8s linear infinite; }

.modal-backdrop { position: fixed; inset: 0; z-index: 1050; display: flex; align-items: center; justify-content: center; padding: 22px; background: rgba(15, 23, 42, .4); backdrop-filter: blur(2px); }
.dispatch-modal { width: min(760px, 100%); max-height: calc(100vh - 44px); overflow-y: auto; border: 1px solid var(--border); border-radius: 15px; background: #fff; box-shadow: 0 24px 60px rgba(15, 23, 42, .22); }
.modal-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 18px 22px; border-bottom: 1px solid var(--border); }
.eyebrow { color: var(--secondary); font-size: 10.8px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.modal-header h2 { margin: 3px 0 2px; color: var(--primary); font-size: 21.6px; }
.modal-document { font-size: 13.2px; }
.modal-close { width: 34px; height: 34px; border: 1px solid var(--border); border-radius: 9px; background: #fff; color: var(--secondary); font-size: 24px; line-height: 1; cursor: pointer; }
.modal-close:hover { background: var(--soft); color: var(--primary); }
.modal-loading { display: flex; min-height: 210px; align-items: center; justify-content: center; gap: 10px; color: var(--secondary); }
.meta-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; padding: 16px 22px; border-bottom: 1px solid var(--border); background: var(--soft); }
.meta-grid span { display: block; margin-bottom: 3px; color: var(--secondary); font-size: 10.8px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.meta-grid strong { color: var(--primary); font-size: 13.2px; }
.size-detail { padding: 18px 22px 22px; }
.size-detail-heading { justify-content: space-between; margin-bottom: 10px; }
.size-detail-heading h3 { margin: 0; color: var(--primary); font-size: 14.4px; }
.size-detail-heading span { color: var(--secondary); font-size: 10.8px; }
.size-table { min-width: 560px; border: 1px solid var(--border); border-radius: 9px; }
.size-table th { padding: 8px 10px; font-size: 10.8px; }
.size-table td { padding: 9px 10px; border-bottom-color: #f1f5f9; font-size: 13.2px; }
.size-table tfoot td { border-bottom: 0; background: var(--soft); color: var(--primary); font-weight: 800; }
.size-value { color: var(--primary); font-weight: 800; }
.muted { color: var(--secondary) !important; }

@media (max-width: 1100px) {
    .filter-card { flex-wrap: wrap; }
    .filter-card input[type="search"] { min-width: 170px; }
    .master-detail-layout { grid-template-columns: 1fr; height: auto; }
    .master-panel { height: 520px; }
    .detail-panel { height: 720px; }
}
@media (max-width: 900px) {
    .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .filter-card select { flex: 1; }
    .meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 600px) {
    .audit-dashboard { padding-top: 10px; }
    .dashboard-header { align-items: flex-start; }
    .dashboard-header h2 { font-size: 22px; }
    .title-line { align-items: flex-start; }
    .summary-grid { gap: 9px; }
    .summary-card { padding: 11px; }
    .filter-card > * { width: 100%; }
    .filter-card input[type="search"], .filter-card select { width: 100%; min-width: 100%; }
    .master-panel { height: 500px; }
    .detail-panel { height: auto; min-height: 620px; }
    .detail-title-row { flex-direction: column; }
    .detail-status { align-items: flex-start; flex-direction: row; }
    .dashboard-footer { flex-direction: column; }
    .meta-grid { grid-template-columns: 1fr; }
    .modal-backdrop { padding: 10px; }
}
</style>
