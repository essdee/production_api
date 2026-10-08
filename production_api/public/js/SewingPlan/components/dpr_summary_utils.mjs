const DAILY_METHOD = 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_sewing_plan_dpr_data'
const SUMMARY_METHOD = 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_sewing_plan_dpr_summary'

export function buildDPRRequest({
    summaryMode,
    supplier,
    selectedDate = null,
    fromDate = null,
    toDate = null,
    workStation = null,
    inputType = null,
}) {
    if (!supplier) {
        return { error: 'Select a Warehouse' }
    }
    if (!summaryMode) {
        if (!selectedDate) {
            return { error: 'Select a Date' }
        }
        return {
            method: DAILY_METHOD,
            args: {
                supplier,
                dpr_date: selectedDate,
                work_station: workStation,
                input_type: inputType,
            },
        }
    }
    if (!fromDate || !toDate) {
        return { error: 'Select From Date and To Date' }
    }
    if (fromDate > toDate) {
        return { error: 'From Date cannot be after To Date' }
    }
    return {
        method: SUMMARY_METHOD,
        args: {
            supplier,
            from_date: fromDate,
            to_date: toDate,
            work_station: workStation,
            input_type: inputType,
        },
    }
}

export function normalizeDPRReports({ summaryMode, selectedDate, response }) {
    if (summaryMode) {
        return (response.reports || []).filter(report => {
            const data = report && report.dpr_data
            return data && Object.keys(data).length > 0
        })
    }
    const data = response.dpr_data || {}
    if (Object.keys(data).length === 0) {
        return []
    }
    return [{
        date: selectedDate,
        headers: response.headers || [],
        dpr_data: data,
    }]
}
