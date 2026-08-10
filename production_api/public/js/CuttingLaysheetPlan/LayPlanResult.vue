<template>
    <div v-if="hasData" class="lay-plan-container">
        <div v-if="optimizationStatus === 'Failed'" class="status-banner status-banner-error">
            <i class="fa fa-exclamation-circle"></i>
            <span>{{ errorMessage || 'Lay optimization did not produce a selectable plan.' }}</span>
        </div>
        <!-- Dashboard Header -->
        <div class="dashboard-header">
            <div class="header-main">
                <div class="header-title">
                    <h1>Lay Plan Optimizer</h1>
                    <p class="text-muted">Analysis for Order: {{ totalOrder.toLocaleString() }} pcs</p>
                </div>
                <div class="header-stats">
                    <div class="stat-card">
                        <span class="stat-label">Total Order</span>
                        <span class="stat-value">{{ totalOrder.toLocaleString() }}</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Constraints</span>
                        <span class="stat-value small">{{ params.max_plies }} plies | {{ params.max_pieces }} pcs</span>
                    </div>
                    <div v-if="params.tubular" class="tubular-chip">
                        <i class="fa fa-sync"></i> Tubular
                    </div>
                </div>
            </div>
        </div>

        <!-- Strategy Navigator -->
        <div class="sidebar-layout">
            <div class="strategy-sidebar">
                <div class="section-label">Select Strategy</div>
                <div class="strategy-list">
                    <div v-for="r in allResults" :key="r.strategy" 
                        class="strategy-card"
                        :class="{ 
                            'active': r.strategy === selectedStrategy,
                            'disabled': !r.success,
                            'duplicate': r.deduplicated 
                        }"
                        @click="r.success && selectStrategy(r.strategy)">
                        <div class="strategy-icon" :class="[r.strategy, { 'gray': !r.success }]">
                            <i :class="getStrategyIcon(r.strategy)"></i>
                        </div>
                        <div class="strategy-info">
                            <div class="strategy-title">
                                {{ formatStrategyName(r.strategy) }}
                                <span v-if="r.deduplicated" class="badge-duplicate">Same Plan</span>
                                <span v-else-if="r.dominated" class="badge-dominated">Dominated</span>
                                <span v-else-if="r.pareto_optimal" class="badge-pareto">Pareto</span>
                            </div>
                            <div v-if="r.success" class="strategy-meta">
                                {{ r.summary.total_lays }} Lays |
                                OC {{ r.summary.overcut_pct }}% |
                                UC {{ r.summary.undercut_pct }}%
                            </div>
                            <div v-else class="strategy-meta text-danger">
                                {{ formatOutcome(r) }}
                            </div>
                        </div>
                        <div v-if="r.strategy === selectedStrategy" class="active-indicator"></div>
                    </div>
                </div>
            </div>

            <!-- Main Content Area -->
            <div class="main-content" v-if="selectedResult">
                <div class="content-header">
                    <div class="strategy-badge" :class="selectedResult.strategy">
                        {{ formatStrategyName(selectedResult.strategy) }}
                    </div>
                    <p class="strategy-description">{{ selectedResult.strategy_description }}</p>
                    <p v-if="selectedResult.priority" class="strategy-priority">
                        {{ selectedResult.priority }}
                        <span v-if="selectedResult.duration_s !== undefined"> · {{ selectedResult.duration_s }}s</span>
                    </p>
                </div>

                <!-- Key Metrics Grid -->
                <div class="metrics-grid">
                    <div class="metric-box box-lays">
                        <div class="metric-val">{{ selectedResult.summary.total_lays }}</div>
                        <div class="metric-label">Total Lays</div>
                    </div>
                    <div class="metric-box box-markers">
                        <div class="metric-val">{{ selectedResult.summary.unique_markers }}</div>
                        <div class="metric-label">Unique Markers</div>
                    </div>
                    <div class="metric-box box-density">
                        <div class="metric-val">{{ selectedResult.summary.avg_pieces_per_ply }}</div>
                        <div class="metric-label">Avg Pcs/Ply</div>
                    </div>
                    <div class="metric-box box-overcut" :class="{ 'warning': selectedResult.summary.overcut_pct > 2 }">
                        <div class="metric-val">{{ selectedResult.summary.overcut_pct }}%</div>
                        <div class="metric-label">Total Overcut</div>
                    </div>
                    <div class="metric-box box-undercut" :class="{ 'warning': selectedResult.summary.undercut_pct > 0 }">
                        <div class="metric-val">{{ selectedResult.summary.undercut_pct }}%</div>
                        <div class="metric-label">Total Undercut</div>
                    </div>
                </div>

                <!-- Tables Container -->
                <div class="tables-section">
                    <div class="card table-card">
                        <div class="card-header">
                            <h3>Detailed Lay Sheet</h3>
                        </div>
                        <div class="table-responsive">
                            <table class="premium-table">
                                <thead>
                                    <tr>
                                        <th>Lay</th>
                                        <th>Plies</th>
                                        <th>Pcs</th>
                                        <th v-for="s in sizes" :key="s">{{ s }}</th>
                                        <th class="ratio-col">Ratio (Pcs/Ply)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="lay in selectedLays" :key="lay.lay_no">
                                        <td class="bold">{{ lay.lay_no }}</td>
                                        <td class="ply-cell">{{ lay.plies }}</td>
                                        <td class="total-pcs">{{ lay.total_pieces.toLocaleString() }}</td>
                                        <td v-for="s in sizes" :key="s" :class="{ 'zero-val': lay.cut_per_size[s] === 0 }">
                                            {{ lay.cut_per_size[s] }}
                                        </td>
                                        <td class="ratio-cell">
                                            <span class="ratio-pill">{{ formatRatio(lay.ratio) }}</span>
                                            <span class="density-tag">({{ lay.pieces_per_ply }})</span>
                                        </td>
                                    </tr>
                                </tbody>
                                <tfoot>
                                    <tr class="footer-row cut">
                                        <td colspan="2">TOTAL CUT</td>
                                        <td class="bold">{{ selectedResult.summary.total_cut.toLocaleString() }}</td>
                                        <td v-for="s in sizes" :key="s" class="bold">
                                            {{ selectedResult.per_size[s].cut }}
                                        </td>
                                        <td></td>
                                    </tr>
                                    <tr class="footer-row order">
                                        <td colspan="2">ORDER QTY</td>
                                        <td class="bold">{{ selectedResult.summary.total_order.toLocaleString() }}</td>
                                        <td v-for="s in sizes" :key="s" class="bold text-muted">
                                            {{ selectedResult.per_size[s].order }}
                                        </td>
                                        <td></td>
                                    </tr>
                                    <tr class="footer-row diff">
                                        <td colspan="2">DIFFERENCE</td>
                                        <td class="bold" :class="diffClass(selectedResult.summary.total_cut - selectedResult.summary.total_order)">
                                            {{ formatDiff(selectedResult.summary.total_cut - selectedResult.summary.total_order) }}
                                        </td>
                                        <td v-for="s in sizes" :key="s" :class="diffClass(selectedResult.per_size[s].diff)">
                                            {{ formatDiff(selectedResult.per_size[s].diff) }}
                                        </td>
                                        <td></td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </div>

                    <div class="card heatmap-card">
                        <div class="card-header">
                            <h3>Size Analysis & Deviation</h3>
                        </div>
                        <div class="deviation-grid">
                            <div v-for="s in sizes" :key="s" class="dev-item" :class="deviationCardClass(selectedResult.per_size[s])">
                                <div class="dev-top">
                                    <span class="dev-size-name">{{ s }}</span>
                                    <span class="dev-percentage">{{ selectedResult.per_size[s].pct }}%</span>
                                </div>
                                <div class="dev-progress-bg">
                                    <div class="dev-progress-bar" :style="{ width: progressWidth(selectedResult.per_size[s]) }"></div>
                                </div>
                                <div class="dev-bottom">
                                    <span>{{ selectedResult.per_size[s].cut }} / {{ selectedResult.per_size[s].order }}</span>
                                    <span :class="diffClass(selectedResult.per_size[s].diff)">{{ formatDiff(selectedResult.per_size[s].diff) }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div v-else-if="isProcessing" class="empty-state processing-state">
        <div class="empty-content">
            <div class="empty-icon"><i class="fa fa-spinner fa-spin"></i></div>
            <h2>Optimization {{ optimizationStatus }}</h2>
            <p>The strategy portfolio is running on the long worker. This form will refresh automatically.</p>
        </div>
    </div>
    <div v-else-if="optimizationStatus === 'Failed'" class="empty-state failed-state">
        <div class="empty-content">
            <div class="empty-icon"><i class="fa fa-exclamation-triangle"></i></div>
            <h2>Optimization Failed</h2>
            <p>{{ errorMessage || 'No feasible lay plan was found.' }}</p>
        </div>
    </div>
    <div v-else class="empty-state">
        <div class="empty-content">
            <div class="empty-icon"><i class="fa fa-magic"></i></div>
            <h2>No Lay Plan Generated</h2>
            <p>Click the <strong>Optimize</strong> button in the form header to calculate different strategies.</p>
        </div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
    onSelect: {
        type: Function,
        default: null,
    },
})

const results = ref([])
const failed = ref([])
const selectedStrategy = ref('')
const params = ref({})
const optimizationStatus = ref('Not Started')
const errorMessage = ref('')
const selectingStrategy = ref('')

const hasData = computed(() => results.value.length > 0 || failed.value.length > 0)
const isProcessing = computed(() => ['Queued', 'Running'].includes(optimizationStatus.value))

const allResults = computed(() => {
    // Merge results and deduplicated ones, keep true failures at end
    const successful = [...results.value]
    const deduplicated = failed.value.filter(f => f.deduplicated)
    const infeasible = failed.value.filter(f => !f.deduplicated)
    
    const all = [...successful, ...deduplicated, ...infeasible]

    const order = [
        'direct_integer_search', 'cp_sat', 'milp', 'column_generation',
        'proportional', 'two_lay_dp', 'minimum_deviation', 'balanced',
        'single_marker', 'iterated_greedy',
        'colgen', 'proportional_decomp', 'ilp', 'order_match', 'single_ratio',
    ]
    const rank = strategy => {
        const index = order.indexOf(strategy)
        return index === -1 ? order.length : index
    }
    return all.sort((a, b) => rank(a.strategy) - rank(b.strategy))
})

const sizes = computed(() => {
    if (!results.value.length) return []
    return Object.keys(results.value[0].per_size)
})

const totalOrder = computed(() => {
    if (!results.value.length) return 0
    return results.value[0].summary.total_order
})

const selectedResult = computed(() => {
    // If selected belongs to results, easy. 
    const found = results.value.find(r => r.strategy === selectedStrategy.value)
    if (found) return found
    
    // If selected is a duplicate, find the plan it refers to
    const dup = failed.value.find(f => f.strategy === selectedStrategy.value && f.deduplicated)
    if (dup && dup.same_as) {
        return results.value.find(r => r.strategy === dup.same_as) || null
    }

    const alternative = failed.value.find(
        f => f.strategy === selectedStrategy.value && f.success
    )
    if (alternative) return alternative
    
    return null
})

const selectedLays = computed(() => {
    if (!selectedResult.value) return []
    return selectedResult.value.lays
})

function load_data(data) {
    if (Array.isArray(data)) {
        results.value = data
        failed.value = []
    } else {
        results.value = data.results || []
        failed.value = data.failed || []
    }
    optimizationStatus.value = data.optimization_status || 'Not Started'
    errorMessage.value = data.error_message || ''
    if (results.value.length > 0) {
        params.value = results.value[0].params || {}
        const available = [...results.value, ...failed.value].some(
            item => item.success && item.strategy === selectedStrategy.value
        )
        if (!available) {
            selectedStrategy.value = results.value[0].strategy
        }
    } else {
        params.value = {}
        selectedStrategy.value = ''
    }
}

function set_selected(strategy) {
    selectedStrategy.value = strategy
}

function formatStrategyName(name) {
    if (!name) return ''
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function getStrategyIcon(strategy) {
    const icons = {
        'min_lays': 'fa fa-compress-arrows-alt',
        'min_overcut': 'fa fa-bullseye',
        'direct_integer_search': 'fa fa-search',
        'cp_sat': 'fa fa-sitemap',
        'milp': 'fa fa-calculator',
        'column_generation': 'fa fa-columns',
        'proportional': 'fa fa-percent',
        'two_lay_dp': 'fa fa-clone',
        'minimum_deviation': 'fa fa-bullseye',
        'balanced': 'fa fa-balance-scale',
        'max_density': 'fa fa-layer-group',
        'single_marker': 'fa fa-th',
        'iterated_greedy': 'fa fa-refresh',
        'single_ratio': 'fa fa-th',
    }
    return icons[strategy] || 'fa fa-cog'
}

function formatRatio(ratio) {
    return sizes.value.map(s => ratio[s]).join(':')
}

function formatDiff(val) {
    return val > 0 ? `+${val}` : `${val}`
}

function diffClass(val) {
    if (val > 0) return 'text-over'
    if (val < 0) return 'text-under'
    return 'text-exact'
}

function deviationCardClass(ps) {
    if (ps.pct > (params.value.tolerance_pct ?? 3)) return 'status-danger'
    if (ps.diff > 0) return 'status-warning'
    if (ps.diff < 0) return 'status-info'
    return 'status-success'
}

function progressWidth(perSize) {
    if (!perSize.order) return '0%'
    return `${Math.min(100, (perSize.cut / perSize.order) * 100)}%`
}

function formatOutcome(result) {
    if (result.status === 'timeout') return `Timed out (${result.duration_s || 0}s)`
    if (result.status === 'invalid') return result.error || 'Rejected: invalid plan'
    if (result.status === 'error') return result.error || 'Strategy error'
    return result.error || 'No feasible plan'
}

async function selectStrategy(strategy) {
    if (strategy === selectedStrategy.value || selectingStrategy.value) return
    selectingStrategy.value = strategy
    try {
        if (props.onSelect) {
            await props.onSelect(strategy)
        }
        selectedStrategy.value = strategy
    } finally {
        selectingStrategy.value = ''
    }
}

defineExpose({
    load_data,
    set_selected,
    results,
    failed,
    selectedStrategy,
    optimizationStatus,
})
</script>

<style scoped>
.lay-plan-container {
    background: #fdfdfd;
    padding: 10px;
    font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
    color: #2c3e50;
    min-height: 400px;
}

.status-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 16px;
    font-weight: 600;
}

.status-banner-error {
    color: #9b2c2c;
    background: #fff5f5;
    border: 1px solid #feb2b2;
}

/* Header */
.dashboard-header {
    background: #ffffff;
    color: #1a202c;
    padding: 24px;
    border-radius: 12px;
    margin-bottom: 24px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.header-main {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-title h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #1a202c;
}

.header-title p {
    margin: 4px 0 0;
    color: #718096;
    font-weight: 500;
}

.header-stats {
    display: flex;
    gap: 16px;
    align-items: center;
}

.stat-card {
    background: #f8fafc;
    padding: 10px 18px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    text-align: center;
}

.stat-label {
    display: block;
    font-size: 10px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 2px;
    opacity: 0.8;
}

.stat-value {
    font-size: 18px;
    font-weight: 800;
}

.stat-value.small {
    font-size: 14px;
}

.tubular-chip {
    background: #fff3cd;
    color: #856404;
    padding: 6px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 11px;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* Sidebar Layout */
.sidebar-layout {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 24px;
}

.strategy-sidebar {
    background: #fff;
    border-radius: 12px;
    padding: 16px;
    border: 1px solid #edf2f7;
    height: fit-content;
}

.section-label {
    font-size: 11px;
    font-weight: 800;
    color: #a0aec0;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
    padding-left: 4px;
}

.strategy-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.strategy-card {
    position: relative;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px;
    border-radius: 10px;
    background: #f7fafc;
    border: 1px solid #edf2f7;
    cursor: pointer;
    transition: all 0.2s ease;
}

.strategy-card:hover:not(.disabled) {
    transform: translateX(4px);
    background: #fff;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    border-color: #cbd5e0;
}

.strategy-card.active {
    background: #fff;
    border-color: #3182ce;
    box-shadow: 0 4px 12px rgba(49, 130, 206, 0.15);
}

.strategy-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    color: white;
    background: linear-gradient(135deg, #64748b, #475569);
}

.strategy-icon.min_lays { background: linear-gradient(135deg, #4299e1, #3182ce); }
.strategy-icon.min_overcut { background: linear-gradient(135deg, #48bb78, #38a169); }
.strategy-icon.direct_integer_search { background: linear-gradient(135deg, #2563eb, #1d4ed8); }
.strategy-icon.cp_sat { background: linear-gradient(135deg, #7c3aed, #6d28d9); }
.strategy-icon.milp { background: linear-gradient(135deg, #0891b2, #0e7490); }
.strategy-icon.column_generation { background: linear-gradient(135deg, #0d9488, #0f766e); }
.strategy-icon.proportional { background: linear-gradient(135deg, #ea580c, #c2410c); }
.strategy-icon.two_lay_dp { background: linear-gradient(135deg, #4f46e5, #4338ca); }
.strategy-icon.minimum_deviation { background: linear-gradient(135deg, #16a34a, #15803d); }
.strategy-icon.balanced { background: linear-gradient(135deg, #ed8936, #dd6b20); }
.strategy-icon.max_density { background: linear-gradient(135deg, #9f7aea, #805ad5); }
.strategy-icon.single_marker { background: linear-gradient(135deg, #64748b, #475569); }
.strategy-icon.iterated_greedy { background: linear-gradient(135deg, #db2777, #be185d); }
.strategy-icon.single_ratio { background: linear-gradient(135deg, #718096, #4a5568); }
.strategy-icon.gray { background: #cbd5e0; }

.strategy-info {
    flex: 1;
}

.strategy-title {
    font-weight: 700;
    font-size: 14px;
    color: #2d3748;
    display: flex;
    align-items: center;
    gap: 8px;
}

.badge-duplicate {
    font-size: 9px;
    background: #e2e8f0;
    color: #4a5568;
    padding: 1px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}

.badge-dominated,
.badge-pareto {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}

.badge-dominated {
    background: #fef3c7;
    color: #92400e;
}

.badge-pareto {
    background: #dcfce7;
    color: #166534;
}

.strategy-meta {
    font-size: 11px;
    color: #718096;
    margin-top: 2px;
}

.active-indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #3182ce;
}

.strategy-card.disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.italic { font-style: italic; }

/* Main Content */
.main-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.content-header {
    margin-bottom: 8px;
}

.strategy-badge {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 20px;
    font-weight: 800;
    font-size: 12px;
    text-transform: uppercase;
    color: white;
    margin-bottom: 10px;
}

.strategy-badge.min_lays { background: #3182ce; }
.strategy-badge.min_overcut { background: #38a169; }
.strategy-badge.direct_integer_search { background: #1d4ed8; }
.strategy-badge.cp_sat { background: #6d28d9; }
.strategy-badge.milp { background: #0e7490; }
.strategy-badge.column_generation { background: #0f766e; }
.strategy-badge.proportional { background: #c2410c; }
.strategy-badge.two_lay_dp { background: #4338ca; }
.strategy-badge.minimum_deviation { background: #15803d; }
.strategy-badge.balanced { background: #dd6b20; }
.strategy-badge.max_density { background: #805ad5; }
.strategy-badge.single_marker { background: #475569; }
.strategy-badge.iterated_greedy { background: #be185d; }
.strategy-badge.single_ratio { background: #4a5568; }

.strategy-description {
    font-size: 15px;
    font-weight: 500;
    color: #4a5568;
    margin: 0;
}

.strategy-priority {
    margin: 6px 0 0;
    color: #64748b;
    font-size: 12px;
}

/* Metrics Grid */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 16px;
}

.metric-box {
    background: #fff;
    padding: 20px 16px;
    border-radius: 12px;
    border: 1px solid #edf2f7;
    text-align: center;
    transition: all 0.3s ease;
}

.metric-box:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 20px rgba(0,0,0,0.05);
}

.metric-val {
    font-size: 24px;
    font-weight: 800;
    color: #2d3748;
}

.metric-label {
    font-size: 11px;
    text-transform: uppercase;
    font-weight: 700;
    color: #718096;
    margin-top: 4px;
}

.metric-box.warning .metric-val { color: #e53e3e; }

/* Cards & Tables */
.card {
    background: #fff;
    border-radius: 12px;
    border: 1px solid #edf2f7;
    overflow: hidden;
    margin-bottom: 24px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}

.card-header {
    background: #f8fafc;
    padding: 14px 20px;
    border-bottom: 1px solid #edf2f7;
}

.card-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 800;
}

.premium-table {
    width: 100%;
    border-collapse: collapse;
}

.premium-table th {
    background: #f1f5f9;
    padding: 12px 16px;
    text-align: center;
    font-size: 11px;
    font-weight: 800;
    color: #475569;
    text-transform: uppercase;
    border-bottom: 2px solid #e2e8f0;
}

.premium-table td {
    padding: 12px 16px;
    text-align: center;
    border-bottom: 1px solid #f1f5f9;
    font-variant-numeric: tabular-nums;
}

.premium-table td.bold { font-weight: 700; color: #1e293b; }
.premium-table .ply-cell { font-weight: 700; color: #2563eb; }
.premium-table .ratio-col { text-align: left; }
.premium-table .ratio-cell { text-align: left; white-space: nowrap; }

.ratio-pill {
    background: #f1f5f9;
    padding: 4px 10px;
    border-radius: 4px;
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    color: #1e293b;
    border: 1px solid #e2e8f0;
}

.density-tag {
    font-size: 11px;
    color: #64748b;
    font-weight: 600;
    margin-left: 8px;
}

.zero-val { opacity: 0.3; }

.footer-row { background: #f8fafc; }
.footer-row td { 
    border-top: 2px solid #e2e8f0; 
    border-bottom: none;
    font-size: 12px;
}
.footer-row.cut td { color: #1e293b; }
.footer-row.order td { color: #64748b; }
.footer-row.diff { background: #f1f5f9; }

.text-over { color: #c05621; }
.text-under { color: #c53030; }
.text-exact { color: #38a169; }

/* Heatmap Cards */
.deviation-grid {
    padding: 24px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 16px;
}

.dev-item {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    transition: all 0.2s ease;
}

.dev-item:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.dev-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.dev-size-name {
    font-size: 18px;
    font-weight: 800;
    color: #334155;
}

.dev-percentage {
    font-size: 14px;
    font-weight: 800;
}

.dev-progress-bg {
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
    margin-bottom: 12px;
    overflow: hidden;
}

.dev-progress-bar {
    height: 100%;
    background: #3b82f6;
    border-radius: 3px;
    transition: width 0.6s ease;
}

.dev-bottom {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-weight: 600;
}

.status-success { border-bottom: 4px solid #38a169; }
.status-success .dev-percentage, .status-success .text-over { color: #38a169; }
.status-success .dev-progress-bar { background: #38a169; }

.status-info { border-bottom: 4px solid #3182ce; }
.status-info .dev-progress-bar { background: #3182ce; }

.status-warning { border-bottom: 4px solid #dd6b20; }
.status-warning .dev-progress-bar { background: #dd6b20; }

.status-danger { border-bottom: 4px solid #e53e3e; background: #fff5f5; border-color: #feb2b2; }
.status-danger .dev-percentage { color: #e53e3e; }
.status-danger .dev-progress-bar { background: #e53e3e; }

/* Empty State */
.empty-state {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 60px 20px;
    background: #fff;
    border-radius: 12px;
    border: 2px dashed #e2e8f0;
    text-align: center;
}

.empty-icon {
    font-size: 48px;
    color: #cbd5e0;
    margin-bottom: 20px;
    animation: bounce 2s infinite;
}

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

.empty-content h2 { color: #4a5568; margin-bottom: 10px; }
.empty-content p { color: #718096; max-width: 400px; }

.processing-state .empty-icon { color: #3182ce; animation: none; }
.failed-state { border-color: #feb2b2; background: #fff5f5; }
.failed-state .empty-icon { color: #e53e3e; animation: none; }

</style>
