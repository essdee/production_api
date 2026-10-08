import assert from 'node:assert/strict'

let loadingState = {}
try {
    loadingState = await import('./dpr_loading_state.mjs')
} catch (_error) {
    // The first TDD run intentionally reaches this branch before the module exists.
}

assert.equal(
    typeof loadingState.createReportLoadingTracker,
    'function',
    'createReportLoadingTracker must be available',
)

const transitions = []
const tracker = loadingState.createReportLoadingTracker((loading) => {
    transitions.push(loading)
})

tracker.start()
tracker.start()
tracker.finish()
tracker.finish()
tracker.finish()

assert.deepEqual(
    transitions,
    [true, true, true, false, false],
    'loading must stay active until all overlapping report requests finish',
)

console.log('Sewing DPR loading-state tests passed')
