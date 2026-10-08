import assert from 'node:assert/strict'
import test from 'node:test'

import {
    buildSupplierPendingRequest,
    createLoadingTracker,
    differenceTone,
    normalizeSupplierPendingResponse,
} from './supplier_pending_report_utils.mjs'

test('request validation requires Supplier', () => {
    assert.deepEqual(buildSupplierPendingRequest({ supplier: '', process: 'Cutting' }), {
        error: 'Select a Supplier',
    })
})

test('request validation requires Process', () => {
    assert.deepEqual(buildSupplierPendingRequest({ supplier: 'SUP-001', process: '' }), {
        error: 'Select a Process',
    })
})

test('valid request targets the Supplier Pending endpoint', () => {
    assert.deepEqual(buildSupplierPendingRequest({ supplier: 'SUP-001', process: 'Cutting' }), {
        method: 'production_api.production_api.page.supplier_pending_report.supplier_pending_report.get_supplier_pending_report',
        args: { supplier: 'SUP-001', process: 'Cutting' },
    })
})

test('response normalization returns stable metadata and items', () => {
    assert.deepEqual(normalizeSupplierPendingResponse(), {
        supplier: null,
        supplier_name: null,
        process: null,
        items: [],
    })
    assert.deepEqual(normalizeSupplierPendingResponse({ supplier: 'SUP-001' }), {
        supplier: 'SUP-001',
        supplier_name: null,
        process: null,
        items: [],
    })
})

test('difference tone follows received minus delivered', () => {
    assert.equal(differenceTone(9, 10), 'negative')
    assert.equal(differenceTone(11, 10), 'positive')
    assert.equal(differenceTone(10, 10), 'zero')
})

test('loading tracker stays active until overlapping requests finish', () => {
    const states = []
    const tracker = createLoadingTracker((loading) => states.push(loading))

    tracker.start()
    tracker.start()
    tracker.finish()
    assert.equal(states.at(-1), true)

    tracker.finish()
    assert.equal(states.at(-1), false)
})
