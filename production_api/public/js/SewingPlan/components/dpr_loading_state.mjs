export function createReportLoadingTracker(setLoading) {
    let pendingRequests = 0

    return {
        start() {
            pendingRequests += 1
            setLoading(true)
        },
        finish() {
            pendingRequests = Math.max(0, pendingRequests - 1)
            setLoading(pendingRequests > 0)
        },
    }
}
