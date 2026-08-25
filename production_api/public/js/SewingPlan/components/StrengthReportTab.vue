<template>
    <div class="strength-report-tab">
        <div class="sp-filter-section">
            <div class="filter-card strength-filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filters</span>
                </div>
                <div ref="report_date_wrapper" class="filter-control"></div>
                <div ref="from_time_wrapper" class="filter-control"></div>
                <div ref="to_time_wrapper" class="filter-control"></div>
                <button class="record-btn" :disabled="!canFetch" @click="fetchReport">
                    <svg v-if="loading" class="record-icon spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                    </svg>
                    <svg v-else class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                    </svg>
                    {{ loading ? 'Fetching...' : 'Fetch Report' }}
                </button>
            </div>
        </div>

        <div v-if="loading" class="report-state loading-state">
            <div class="spinner"></div>
            <h4>Fetching Workers Strength Report from HR...</h4>
            <p>Please wait while the latest employee punch and strength data is prepared.</p>
        </div>

        <div v-else-if="errorMessage" class="report-state error-state">
            <h4>Unable to load the Workers Strength Report.</h4>
            <p>{{ errorMessage }}</p>
        </div>

        <template v-else-if="fetched">
            <div class="success-banner">
                <div>
                    <strong>Report fetched successfully.</strong>
                    {{ employeePunches.length }} active employees and {{ summaryRows.length }} summary rows returned.
                </div>
                <div class="shift-list"><strong>Shifts:</strong> {{ shifts.join(', ') || '-' }}</div>
            </div>

            <div class="report-grid">
                <section class="report-panel employee-panel">
                    <div class="panel-heading">
                        <div>
                            <h3>Employee First Punch</h3>
                            <p>First check-in inside the selected time window</p>
                        </div>
                        <div class="panel-actions">
                            <span class="count-badge">{{ punchedEmployeeCount }}/{{ filteredEmployeePunches.length }}</span>
                            <button
                                class="excel-btn"
                                :disabled="!filteredEmployeePunches.length"
                                @click="downloadEmployeePunches"
                            >
                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v12m0 0l-4-4m4 4l4-4M5 20h14"></path>
                                </svg>
                                Excel
                            </button>
                        </div>
                    </div>
                    <div class="local-filters employee-filter-grid">
                        <div class="search-field">
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                            </svg>
                            <input
                                v-model="employeeFilterInput"
                                type="text"
                                placeholder="Filter by employee name"
                                @input="scheduleEmployeeFilters"
                            >
                        </div>
                        <div class="search-field">
                            <input
                                v-model="employeeDepartmentFilterInput"
                                type="text"
                                placeholder="Department"
                                @input="scheduleEmployeeFilters"
                            >
                        </div>
                        <div class="search-field">
                            <input
                                v-model="employeeDesignationFilterInput"
                                type="text"
                                placeholder="Designation"
                                @input="scheduleEmployeeFilters"
                            >
                        </div>
                    </div>
                    <div v-if="filteredEmployeePunches.length" class="table-scroll">
                        <table class="strength-table">
                            <thead>
                                <tr>
                                    <th>Employee</th>
                                    <th>Department</th>
                                    <th>Designation</th>
                                    <th>Shift</th>
                                    <th>First Punch</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="employee in filteredEmployeePunches" :key="employee.employee">
                                    <td>
                                        <div class="employee-name">{{ employee.employee_name || employee.employee }}</div>
                                        <div class="employee-id">{{ employee.employee }}</div>
                                    </td>
                                    <td>{{ employee.department || '-' }}</td>
                                    <td>{{ employee.designation || '-' }}</td>
                                    <td>{{ employee.shift_type || '-' }}</td>
                                    <td class="punch-time" :class="{ missing: !employee.first_punch }">
                                        {{ employee.first_punch || '-' }}
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <div v-else class="panel-empty">No active employees match the employee filter.</div>
                </section>

                <section class="report-panel summary-panel">
                    <div class="panel-heading">
                        <div>
                            <h3>Workers Strength Summary</h3>
                            <p>Department, designation and manpower-agent summary</p>
                        </div>
                        <div class="panel-actions">
                            <span class="count-badge">{{ filteredSummaryRows.length }}</span>
                            <button
                                class="excel-btn"
                                :disabled="!filteredSummaryRows.length"
                                @click="downloadStrengthSummary"
                            >
                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v12m0 0l-4-4m4 4l4-4M5 20h14"></path>
                                </svg>
                                Excel
                            </button>
                        </div>
                    </div>
                    <div class="local-filters summary-filter-grid">
                        <div class="search-field">
                            <input
                                v-model="departmentFilterInput"
                                type="text"
                                placeholder="Department"
                                @input="scheduleSummaryFilters"
                            >
                        </div>
                        <div class="search-field">
                            <input
                                v-model="designationFilterInput"
                                type="text"
                                placeholder="Designation"
                                @input="scheduleSummaryFilters"
                            >
                        </div>
                        <div class="search-field">
                            <input
                                v-model="manpowerAgentFilterInput"
                                type="text"
                                placeholder="Manpower Agent"
                                @input="scheduleSummaryFilters"
                            >
                        </div>
                    </div>
                    <div v-if="filteredSummaryRows.length" class="table-scroll">
                        <table class="strength-table summary-table">
                            <thead>
                                <tr>
                                    <th
                                        v-for="column in visibleColumns"
                                        :key="column.fieldname"
                                        :class="{ 'employee-list-column': isEmployeeListColumn(column) }"
                                    >
                                        {{ column.label || column.fieldname }}
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr
                                    v-for="(row, rowIndex) in filteredSummaryRows"
                                    :key="rowIndex"
                                    :class="{ 'total-row': isTotalRow(row) }"
                                >
                                    <td
                                        v-for="column in visibleColumns"
                                        :key="column.fieldname"
                                        :class="{
                                            numeric: isNumericColumn(column),
                                            'employee-list-column': isEmployeeListColumn(column),
                                        }"
                                    >
                                        {{ formatValue(row[column.fieldname]) }}
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <div v-else class="panel-empty">No strength rows match the summary filters.</div>
                </section>
            </div>
        </template>

        <div v-else class="report-state initial-state">
            <h4>Workers Strength Report</h4>
            <p>Select the date and time window, then click Fetch Report.</p>
        </div>
    </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as XLSX from 'xlsx'

const report_date_wrapper = ref(null)
const from_time_wrapper = ref(null)
const to_time_wrapper = ref(null)
const reportDate = ref(frappe.datetime.now_date())
const fromTime = ref(null)
const toTime = ref(null)
const loading = ref(false)
const fetched = ref(false)
const errorMessage = ref('')
const columns = ref([])
const summaryRows = ref([])
const employeePunches = ref([])
const shifts = ref([])
const addTotalRow = ref(false)
const sample_doc = ref({})
const employeeFilterInput = ref('')
const employeeFilter = ref('')
const employeeDepartmentFilterInput = ref('')
const employeeDesignationFilterInput = ref('')
const employeeDepartmentFilter = ref('')
const employeeDesignationFilter = ref('')
const departmentFilterInput = ref('')
const designationFilterInput = ref('')
const manpowerAgentFilterInput = ref('')
const departmentFilter = ref('')
const designationFilter = ref('')
const manpowerAgentFilter = ref('')

let reportDateControl = null
let fromTimeControl = null
let toTimeControl = null
let employeeFilterTimer = null
let summaryFilterTimer = null

const visibleColumns = computed(() => columns.value.filter(column => !column.hidden))
const canFetch = computed(() => Boolean(
    reportDate.value && fromTime.value && toTime.value && !loading.value
))
const filteredEmployeePunches = computed(() => {
    if (
        !employeeFilter.value
        && !employeeDepartmentFilter.value
        && !employeeDesignationFilter.value
    ) return employeePunches.value
    return employeePunches.value.filter(employee => (
        matchesFilter(employee.employee_name || employee.employee, employeeFilter.value)
        && matchesFilter(employee.department, employeeDepartmentFilter.value)
        && matchesFilter(employee.designation, employeeDesignationFilter.value)
    ))
})
const filteredSummaryRows = computed(() => summaryRows.value.filter(row => (
    matchesFilter(row.department, departmentFilter.value)
    && matchesFilter(row.designation, designationFilter.value)
    && matchesFilter(row.manpower_agent, manpowerAgentFilter.value)
)))
const punchedEmployeeCount = computed(() => (
    filteredEmployeePunches.value.filter(employee => employee.first_punch).length
))

function normalizeSearchValue(value) {
    return String(value || '').trim().toLocaleLowerCase()
}

function matchesFilter(value, filter) {
    return !filter || normalizeSearchValue(value).includes(filter)
}

function scheduleEmployeeFilters() {
    clearTimeout(employeeFilterTimer)
    employeeFilterTimer = setTimeout(() => {
        employeeFilter.value = normalizeSearchValue(employeeFilterInput.value)
        employeeDepartmentFilter.value = normalizeSearchValue(employeeDepartmentFilterInput.value)
        employeeDesignationFilter.value = normalizeSearchValue(employeeDesignationFilterInput.value)
    }, 1000)
}

function scheduleSummaryFilters() {
    clearTimeout(summaryFilterTimer)
    summaryFilterTimer = setTimeout(() => {
        departmentFilter.value = normalizeSearchValue(departmentFilterInput.value)
        designationFilter.value = normalizeSearchValue(designationFilterInput.value)
        manpowerAgentFilter.value = normalizeSearchValue(manpowerAgentFilterInput.value)
    }, 1000)
}

function fetchReport() {
    if (!canFetch.value) return
    loading.value = true
    fetched.value = true
    errorMessage.value = ''

    frappe.call({
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_worker_strength_report',
        args: {
            report_date: reportDate.value,
            from_time: fromTime.value,
            to_time: toTime.value,
        },
        callback: response => {
            const report = response.message || {}
            columns.value = report.columns || []
            summaryRows.value = report.rows || []
            employeePunches.value = report.employee_punches || []
            shifts.value = report.shifts || []
            addTotalRow.value = Boolean(report.add_total_row)
            loading.value = false
        },
        error: response => {
            loading.value = false
            errorMessage.value = response?.message || 'Check the HR settings and try again.'
        },
    })
}

function isNumericColumn(column) {
    return ['Int', 'Float', 'Currency', 'Percent'].includes(column.fieldtype)
}

function isEmployeeListColumn(column) {
    return ['absent_employees', 'leave_employees'].includes(column.fieldname)
}

function isTotalRow(row) {
    return Boolean(
        addTotalRow.value
        && summaryRows.value.length
        && row === summaryRows.value[summaryRows.value.length - 1]
    )
}

function formatValue(value) {
    if (value === null || value === undefined || value === '') return '-'
    if (Array.isArray(value)) return value.join(', ')
    if (typeof value === 'object') return JSON.stringify(value)
    return value
}

function downloadExcel(filename, sheetName, headers, rows) {
    const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows])
    worksheet['!cols'] = headers.map((header, columnIndex) => {
        const contentWidth = rows.reduce((width, row) => (
            Math.max(width, String(row[columnIndex] ?? '').length)
        ), 0)
        return { wch: Math.min(60, Math.max(String(header).length, contentWidth) + 2) }
    })
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
    XLSX.writeFile(workbook, filename)
}

function downloadEmployeePunches() {
    const headers = [
        'Employee ID',
        'Employee Name',
        'Department',
        'Designation',
        'Manpower Agent',
        'Shift',
        'First Punch',
    ]
    const rows = filteredEmployeePunches.value.map(employee => [
        employee.employee || '',
        employee.employee_name || employee.employee || '',
        employee.department || '',
        employee.designation || '',
        employee.manpower_agent || '',
        employee.shift_type || '',
        employee.first_punch || '-',
    ])
    downloadExcel(
        `Employee_First_Punch_${reportDate.value}.xlsx`,
        'Employee First Punch',
        headers,
        rows,
    )
}

function downloadStrengthSummary() {
    const headers = visibleColumns.value.map(column => column.label || column.fieldname)
    const rows = filteredSummaryRows.value.map(row => (
        visibleColumns.value.map(column => formatValue(row[column.fieldname]))
    ))
    downloadExcel(
        `Workers_Strength_Summary_${reportDate.value}.xlsx`,
        'Strength Summary',
        headers,
        rows,
    )
}

function createControl(wrapper, definition) {
    return frappe.ui.form.make_control({
        parent: $(wrapper),
        df: definition,
        doc: sample_doc.value,
        render_input: true,
    })
}

onMounted(() => {
    reportDateControl = createControl(report_date_wrapper.value, {
        fieldtype: 'Date',
        fieldname: 'strength_report_date',
        label: '',
        placeholder: 'Date',
        change: () => {
            reportDate.value = reportDateControl.get_value() || null
        },
    })
    reportDateControl.set_value(reportDate.value)

    fromTimeControl = createControl(from_time_wrapper.value, {
        fieldtype: 'Time',
        fieldname: 'strength_report_from_time',
        label: '',
        placeholder: 'From Time',
        change: () => {
            fromTime.value = fromTimeControl.get_value() || null
        },
    })

    toTimeControl = createControl(to_time_wrapper.value, {
        fieldtype: 'Time',
        fieldname: 'strength_report_to_time',
        label: '',
        placeholder: 'To Time',
        change: () => {
            toTime.value = toTimeControl.get_value() || null
        },
    })
})

onBeforeUnmount(() => {
    clearTimeout(employeeFilterTimer)
    clearTimeout(summaryFilterTimer)
})
</script>

<style scoped>
@import "../SewingPlan.css";

.strength-report-tab {
    padding: 1rem 0;
}

.strength-filter-card {
    width: 100%;
    min-width: 0;
    flex-wrap: wrap;
}

.strength-filter-card .filter-control {
    min-width: 150px;
}

.record-btn:disabled {
    cursor: not-allowed;
    opacity: 0.55;
    transform: none;
}

.spin {
    animation: spin 0.9s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.report-state {
    min-height: 360px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #64748b;
}

.report-state h4 {
    color: #334155;
    font-size: 1rem;
    font-weight: 700;
    margin: 0 0 0.5rem;
}

.report-state p {
    margin: 0;
}

.spinner {
    width: 2.25rem;
    height: 2.25rem;
    border: 3px solid #dbeafe;
    border-top-color: #1a73e8;
    border-radius: 50%;
    animation: spin 0.9s linear infinite;
    margin-bottom: 1rem;
}

.error-state {
    color: #b91c1c;
}

.error-state h4 {
    color: #991b1b;
}

.success-banner {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
    padding: 0.8rem 1rem;
    border: 1px solid #bbf7d0;
    border-radius: 0.8rem;
    background: #f0fdf4;
    color: #166534;
    font-size: 0.8rem;
}

.shift-list {
    text-align: right;
}

.report-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
    gap: 1rem;
    align-items: start;
}

.report-panel {
    min-width: 0;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    background: #fff;
}

.panel-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.1rem;
    border-bottom: 1px solid #e2e8f0;
}

.panel-actions {
    display: flex;
    align-items: center;
    gap: 0.55rem;
}

.excel-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.38rem 0.65rem;
    border: 1px solid #bbf7d0;
    border-radius: 0.55rem;
    background: #f0fdf4;
    color: #15803d;
    font-size: 0.7rem;
    font-weight: 700;
    cursor: pointer;
}

.excel-btn:hover {
    border-color: #86efac;
    background: #dcfce7;
}

.excel-btn:disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.excel-btn svg {
    width: 0.9rem;
    height: 0.9rem;
}

.panel-heading h3 {
    margin: 0;
    color: #1e293b;
    font-size: 0.95rem;
    font-weight: 700;
}

.panel-heading p {
    margin: 0.25rem 0 0;
    color: #94a3b8;
    font-size: 0.72rem;
}

.count-badge {
    flex: 0 0 auto;
    padding: 0.3rem 0.6rem;
    border-radius: 999px;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 0.72rem;
    font-weight: 700;
}

.local-filters {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #e2e8f0;
    background: #fbfdff;
}

.employee-filter-grid,
.summary-filter-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(125px, 1fr));
    gap: 0.55rem;
}

.search-field {
    position: relative;
}

.search-field svg {
    position: absolute;
    top: 50%;
    left: 0.65rem;
    width: 0.9rem;
    height: 0.9rem;
    color: #94a3b8;
    transform: translateY(-50%);
    pointer-events: none;
}

.search-field input {
    width: 100%;
    height: 34px;
    padding: 0.4rem 0.65rem;
    border: 1px solid #dbe3ee;
    border-radius: 0.6rem;
    outline: none;
    background: #fff;
    color: #334155;
    font-size: 0.72rem;
}

.search-field svg + input {
    padding-left: 2rem;
}

.search-field input:focus {
    border-color: #93c5fd;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.table-scroll {
    max-height: 65vh;
    overflow: auto;
}

.strength-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.76rem;
}

.strength-table th {
    position: sticky;
    top: 0;
    z-index: 2;
    padding: 0.7rem 0.75rem;
    border-bottom: 1px solid #cbd5e1;
    background: #f8fafc;
    color: #475569;
    font-weight: 700;
    text-align: left;
    white-space: nowrap;
}

.strength-table td {
    padding: 0.7rem 0.75rem;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
    vertical-align: middle;
}

.strength-table tbody tr:hover td {
    background: #f8fafc;
}

.employee-name {
    font-weight: 600;
}

.employee-id {
    margin-top: 0.15rem;
    color: #94a3b8;
    font-size: 0.68rem;
}

.punch-time {
    color: #047857 !important;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    white-space: nowrap;
}

.punch-time.missing {
    color: #94a3b8 !important;
}

.summary-table {
    min-width: 760px;
}

.summary-table td.numeric {
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.summary-table .employee-list-column {
    width: 130px;
    min-width: 130px;
    max-width: 130px;
    white-space: normal;
    word-break: break-word;
}

.summary-table .total-row td {
    background: #f8fafc;
    font-weight: 700;
}

.panel-empty {
    padding: 4rem 1rem;
    color: #94a3b8;
    text-align: center;
}

@media (max-width: 1100px) {
    .report-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 700px) {
    .success-banner {
        flex-direction: column;
    }

    .shift-list {
        text-align: left;
    }

    .employee-filter-grid,
    .summary-filter-grid {
        grid-template-columns: 1fr;
    }

    .panel-heading {
        align-items: flex-start;
        flex-direction: column;
    }
}
</style>
