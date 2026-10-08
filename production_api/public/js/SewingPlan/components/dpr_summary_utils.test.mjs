import assert from 'node:assert/strict'

let utils = {}
try {
    utils = await import('./dpr_summary_utils.mjs')
} catch (_error) {
    // The first TDD run intentionally reaches this branch before the module exists.
}

assert.equal(typeof utils.buildDPRRequest, 'function', 'buildDPRRequest must be available')
assert.equal(typeof utils.normalizeDPRReports, 'function', 'normalizeDPRReports must be available')

assert.deepEqual(
    utils.buildDPRRequest({ summaryMode: false, supplier: null, selectedDate: null }),
    { error: 'Select a Warehouse' },
)

assert.deepEqual(
    utils.buildDPRRequest({ summaryMode: false, supplier: 'WAREHOUSE-1', selectedDate: null }),
    { error: 'Select a Date' },
)

{
    const result = utils.buildDPRRequest({
        summaryMode: false,
        supplier: 'WAREHOUSE-1',
        selectedDate: '2026-10-03',
        workStation: null,
        inputType: null,
    })
    assert.deepEqual(result, {
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_sewing_plan_dpr_data',
        args: {
            supplier: 'WAREHOUSE-1',
            dpr_date: '2026-10-03',
            work_station: null,
            input_type: null,
        },
    })
}

{
    const result = utils.buildDPRRequest({
        summaryMode: true,
        supplier: 'WAREHOUSE-1',
        fromDate: '2026-10-01',
        toDate: '2026-10-03',
        workStation: 'LINE-1',
        inputType: 'Line Output',
    })
    assert.deepEqual(result, {
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_sewing_plan_dpr_summary',
        args: {
            supplier: 'WAREHOUSE-1',
            from_date: '2026-10-01',
            to_date: '2026-10-03',
            work_station: 'LINE-1',
            input_type: 'Line Output',
        },
    })
}

assert.deepEqual(
    utils.buildDPRRequest({
        summaryMode: true,
        supplier: 'WAREHOUSE-1',
        fromDate: null,
        toDate: '2026-10-03',
    }),
    { error: 'Select From Date and To Date' },
)

assert.deepEqual(
    utils.buildDPRRequest({
        summaryMode: true,
        supplier: 'WAREHOUSE-1',
        fromDate: '2026-10-04',
        toDate: '2026-10-03',
    }),
    { error: 'From Date cannot be after To Date' },
)

assert.deepEqual(
    utils.normalizeDPRReports({
        summaryMode: false,
        selectedDate: '2026-10-03',
        response: {
            headers: ['Line Output'],
            dpr_data: { 'Line Output': { 'LOT-001': {} } },
        },
    }),
    [
        {
            date: '2026-10-03',
            headers: ['Line Output'],
            dpr_data: { 'Line Output': { 'LOT-001': {} } },
        },
    ],
)

assert.deepEqual(
    utils.normalizeDPRReports({
        summaryMode: true,
        selectedDate: null,
        response: {
            reports: [
                {
                    date: '2026-09-30',
                    headers: ['Line Output'],
                    dpr_data: {},
                },
                {
                    date: '2026-10-01',
                    headers: ['Line Output'],
                    dpr_data: { 'Line Output': { 'LOT-001': {} } },
                },
            ],
        },
    }),
    [
        {
            date: '2026-10-01',
            headers: ['Line Output'],
            dpr_data: { 'Line Output': { 'LOT-001': {} } },
        },
    ],
)

console.log('Sewing DPR summary utility tests passed')
