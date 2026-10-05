export function sortPlansByAge(plans) {
    return [...(plans || [])].sort((left, right) => {
        const ageDifference = Number(right.age_days || 0) - Number(left.age_days || 0)
        return ageDifference || String(left.name || '').localeCompare(String(right.name || ''))
    })
}


export function filterPlans(plans, filters = {}) {
    const search = String(filters.search || '').trim().toLowerCase()
    return sortPlansByAge(plans).filter((plan) => {
        const identity = [plan.name, plan.lot, plan.item].filter(Boolean).join(' ').toLowerCase()
        if (search && !identity.includes(search)) return false
        if (filters.status && plan.fp_status !== filters.status) return false

        const age = Number(plan.age_days || 0)
        if (filters.age === '8-14' && (age < 8 || age > 14)) return false
        if (filters.age === '15+' && age < 15) return false
        return true
    })
}


export function ageTone(ageDays) {
    const age = Number(ageDays || 0)
    if (age >= 19) return 'critical'
    if (age >= 15) return 'danger'
    return 'warning'
}
