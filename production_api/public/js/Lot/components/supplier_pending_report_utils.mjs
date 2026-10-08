const REPORT_METHOD = 'production_api.production_api.page.supplier_pending_report.supplier_pending_report.get_supplier_pending_report'

export function buildSupplierPendingRequest({ supplier, process } = {}) {
    if (!supplier) {
        return { error: 'Select a Supplier' }
    }
    if (!process) {
        return { error: 'Select a Process' }
    }
    return {
        method: REPORT_METHOD,
        args: { supplier, process },
    }
}

export function normalizeSupplierPendingResponse(response) {
    const payload = response || {}
    return {
        supplier: payload.supplier || null,
        supplier_name: payload.supplier_name || null,
        process: payload.process || null,
        items: Array.isArray(payload.items) ? payload.items : [],
    }
}

export function differenceTone(received, delivered) {
    const difference = Number(received || 0) - Number(delivered || 0)
    if (difference < 0) return 'negative'
    if (difference > 0) return 'positive'
    return 'zero'
}

export function createLoadingTracker(setLoading) {
    let activeRequests = 0
    const update = () => setLoading(activeRequests > 0)
    return {
        start() {
            activeRequests += 1
            update()
        },
        finish() {
            activeRequests = Math.max(0, activeRequests - 1)
            update()
        },
    }
}
