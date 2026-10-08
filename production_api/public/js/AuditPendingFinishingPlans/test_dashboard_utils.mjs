import test from 'node:test'
import assert from 'node:assert/strict'
import * as dashboardUtils from './dashboard_utils.mjs'

import {
    ageTone,
    buildDashboardRequest,
    filterPlans,
    isCurrentPendingGeneration,
    needsPendingBreakdown,
    pendingCategoryTone,
    quantityOrDash,
    shouldShowPartTabs,
    sortPlansByAge,
    visiblePendingParts,
} from './dashboard_utils.mjs'


const plans = [
    { name: 'FP-2', lot: 'LOT-B', item: 'Track Pant', fp_status: 'Dispatched', age_days: 8 },
    { name: 'FP-1', lot: 'LOT-A', item: 'Classic Polo', fp_status: 'Fully Dispatched', age_days: 19 },
    { name: 'FP-3', lot: 'LOT-C', item: 'Kids Tee', fp_status: 'Dispatched', age_days: 15 },
]


test('builds dashboard requests for the selected report mode', () => {
    assert.deepEqual(buildDashboardRequest(false), {
        method: 'production_api.production_api.page.audit_pending_finishing_plans.audit_pending_finishing_plans.get_dashboard_data',
        args: { show_partially_dispatched: 0 },
    })
    assert.deepEqual(buildDashboardRequest(true), {
        method: 'production_api.production_api.page.audit_pending_finishing_plans.audit_pending_finishing_plans.get_dashboard_data',
        args: { show_partially_dispatched: 1 },
    })
})


test('filters plans independently by case-insensitive plan, lot, and item values', () => {
    assert.deepEqual(
        filterPlans(plans, { plan: 'fp-2' }).map(row => row.name),
        ['FP-2'],
    )
    assert.deepEqual(
        filterPlans(plans, { lot: 'lot-a' }).map(row => row.name),
        ['FP-1'],
    )
    assert.deepEqual(
        filterPlans(plans, { item: 'kids TEE' }).map(row => row.name),
        ['FP-3'],
    )
    assert.deepEqual(
        filterPlans(plans, { plan: 'fp', lot: 'lot-c', item: 'kids', status: 'Dispatched' }).map(row => row.name),
        ['FP-3'],
    )
})


test('combines status and age filters', () => {
    assert.deepEqual(
        filterPlans(plans, { search: '', status: 'Dispatched', age: '15+' }).map(row => row.name),
        ['FP-3'],
    )
    assert.deepEqual(
        filterPlans(plans, { search: '', status: '', age: '8-14' }).map(row => row.name),
        ['FP-2'],
    )
})


test('sorts by descending age without mutating the source list', () => {
    assert.deepEqual(sortPlansByAge(plans).map(row => row.age_days), [19, 15, 8])
    assert.deepEqual(plans.map(row => row.age_days), [8, 19, 15])
})


test('keeps the selected plan when visible and falls back to the first filtered plan', () => {
    assert.equal(typeof dashboardUtils.resolveSelectedPlanName, 'function')
    assert.equal(dashboardUtils.resolveSelectedPlanName(plans, 'FP-2'), 'FP-2')
    assert.equal(dashboardUtils.resolveSelectedPlanName(plans, 'FP-MISSING'), 'FP-2')
    assert.equal(dashboardUtils.resolveSelectedPlanName([], 'FP-2'), '')
})


test('totals dispatched boxes from submitted history rows', () => {
    assert.equal(typeof dashboardUtils.totalDispatchBoxes, 'function')
    assert.equal(dashboardUtils.totalDispatchBoxes([{ boxes: 2 }, { boxes: '3' }, { boxes: null }]), 5)
    assert.equal(dashboardUtils.totalDispatchBoxes(), 0)
})


test('assigns warning, danger, and critical age tones', () => {
    assert.equal(ageTone(8), 'warning')
    assert.equal(ageTone(18), 'danger')
    assert.equal(ageTone(19), 'critical')
})


test('formats zero matrix quantities as dashes without hiding non-zero values', () => {
    assert.equal(quantityOrDash(0), '—')
    assert.equal(quantityOrDash(null), '—')
    assert.equal(quantityOrDash('12.5'), 12.5)
    assert.equal(quantityOrDash(-2), -2)
})


test('assigns stable semantic tones to pending quantity categories', () => {
    assert.equal(pendingCategoryTone('loose_piece'), 'loose')
    assert.equal(pendingCategoryTone('loose_piece_set'), 'loose-set')
    assert.equal(pendingCategoryTone('rejected'), 'rejected')
    assert.equal(pendingCategoryTone('pending'), 'rework')
})


test('loads a pending breakdown only when the plan is neither cached nor loading', () => {
    assert.equal(needsPendingBreakdown({}, new Set(), 'FP-1'), true)
    assert.equal(needsPendingBreakdown({ 'FP-1': { parts: [] } }, new Set(), 'FP-1'), false)
    assert.equal(needsPendingBreakdown({}, new Set(['FP-1']), 'FP-1'), false)
    assert.equal(needsPendingBreakdown({}, new Set(), ''), false)
})


test('rejects pending responses from an invalidated refresh generation', () => {
    assert.equal(isCurrentPendingGeneration(4, 4), true)
    assert.equal(isCurrentPendingGeneration(3, 4), false)
})


test('hides empty pending categories and parts', () => {
    const parts = [
        {
            name: 'Top',
            categories: [
                { key: 'loose_piece', rows: [] },
                { key: 'rejected', rows: [{ colour: 'Navy', values: [2] }] },
            ],
        },
        {
            name: 'Bottom',
            categories: [
                { key: 'loose_piece', rows: [] },
                { key: 'pending', rows: [] },
            ],
        },
    ]

    assert.deepEqual(visiblePendingParts(parts), [
        {
            name: 'Top',
            categories: [
                { key: 'rejected', rows: [{ colour: 'Navy', values: [2] }] },
            ],
        },
    ])
    assert.equal(parts[0].categories.length, 2)
})


test('shows part tabs for set-item parts but not for a single ordinary item', () => {
    assert.equal(shouldShowPartTabs([{ name: 'Item' }]), false)
    assert.equal(shouldShowPartTabs([{ name: 'Top' }]), true)
    assert.equal(shouldShowPartTabs([{ name: 'Top' }, { name: 'Bottom' }]), true)
    assert.equal(shouldShowPartTabs([]), false)
})
