const DASHBOARD_METHOD = 'production_api.production_api.page.audit_pending_finishing_plans.audit_pending_finishing_plans.get_dashboard_data'


export function buildDashboardRequest(showPartiallyDispatched) {
    return {
        method: DASHBOARD_METHOD,
        args: { show_partially_dispatched: showPartiallyDispatched ? 1 : 0 },
    }
}


export function sortPlansByAge(plans) {
    return [...(plans || [])].sort((left, right) => {
        const ageDifference = Number(right.age_days || 0) - Number(left.age_days || 0)
        return ageDifference || String(left.name || '').localeCompare(String(right.name || ''))
    })
}


export function filterPlans(plans, filters = {}) {
    const planFilter = String(filters.plan || '').trim().toLowerCase()
    const lotFilter = String(filters.lot || '').trim().toLowerCase()
    const itemFilter = String(filters.item || '').trim().toLowerCase()
    return sortPlansByAge(plans).filter((plan) => {
        if (planFilter && !String(plan.name || '').toLowerCase().includes(planFilter)) return false
        if (lotFilter && !String(plan.lot || '').toLowerCase().includes(lotFilter)) return false
        if (itemFilter && !String(plan.item || '').toLowerCase().includes(itemFilter)) return false
        if (filters.status && plan.fp_status !== filters.status) return false

        const age = Number(plan.age_days || 0)
        if (filters.age === '8-14' && (age < 8 || age > 14)) return false
        if (filters.age === '15+' && age < 15) return false
        return true
    })
}


export function resolveSelectedPlanName(plans, selectedName) {
    const visiblePlans = plans || []
    if (visiblePlans.some(plan => plan.name === selectedName)) return selectedName
    return visiblePlans[0]?.name || ''
}


export function totalDispatchBoxes(history) {
    return (history || []).reduce((total, row) => {
        const boxes = Number(row?.boxes || 0)
        return total + (Number.isFinite(boxes) ? boxes : 0)
    }, 0)
}


export function ageTone(ageDays) {
    const age = Number(ageDays || 0)
    if (age >= 19) return 'critical'
    if (age >= 15) return 'danger'
    return 'warning'
}


export function quantityOrDash(value) {
    const quantity = Number(value || 0)
    return quantity === 0 ? '—' : quantity
}


export function pendingCategoryTone(key) {
    return {
        loose_piece: 'loose',
        loose_piece_set: 'loose-set',
        rejected: 'rejected',
        pending: 'rework',
    }[key] || 'neutral'
}


export function needsPendingBreakdown(cache, loadingNames, name) {
    return Boolean(
        name
        && !Object.prototype.hasOwnProperty.call(cache || {}, name)
        && !loadingNames?.has(name)
    )
}


export function isCurrentPendingGeneration(requestGeneration, currentGeneration) {
    return requestGeneration === currentGeneration
}


export function visiblePendingParts(parts) {
    return (parts || [])
        .map(part => ({
            ...part,
            categories: (part.categories || []).filter(category => category.rows?.length),
        }))
        .filter(part => part.categories.length)
}


export function shouldShowPartTabs(parts) {
    const visibleParts = parts || []
    return visibleParts.length > 1 || (visibleParts.length === 1 && visibleParts[0]?.name !== 'Item')
}
