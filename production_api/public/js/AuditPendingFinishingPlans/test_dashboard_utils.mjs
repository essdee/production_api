import test from 'node:test'
import assert from 'node:assert/strict'

import {
    ageTone,
    filterPlans,
    sortPlansByAge,
} from './dashboard_utils.mjs'


const plans = [
    { name: 'FP-2', lot: 'LOT-B', item: 'Track Pant', fp_status: 'Dispatched', age_days: 8 },
    { name: 'FP-1', lot: 'LOT-A', item: 'Classic Polo', fp_status: 'Fully Dispatched', age_days: 19 },
    { name: 'FP-3', lot: 'LOT-C', item: 'Kids Tee', fp_status: 'Dispatched', age_days: 15 },
]


test('filters plans by case-insensitive identity search', () => {
    assert.deepEqual(
        filterPlans(plans, { search: 'classic POLO', status: '', age: '' }).map(row => row.name),
        ['FP-1'],
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


test('assigns warning, danger, and critical age tones', () => {
    assert.equal(ageTone(8), 'warning')
    assert.equal(ageTone(18), 'danger')
    assert.equal(ageTone(19), 'critical')
})
