<template>
    <div class="placeholder-tab">
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filters</span>
                </div>
                <div class="filter-control">
                    <div ref="inputTypeWrapper"></div>
                </div>
                <div class="filter-control">
                    <div ref="workStationWrapper"></div>
                </div>
                <div class="filter-control">
                    <div ref="lotWrapper"></div>
                </div>
                <div>
                     <button class="btn btn-primary" @click="fetchData()" style="border-radius: 12px; font-weight: 700;">
                        Fetch
                    </button>
                </div>
            </div>
        </div>
        <div v-if="items && Object.keys(items).length > 0">
            <div v-for="sp_name in Object.keys(items)">
                <div class="plan-header">
                    <div class="plan-main">
                        <h3 class="plan-title">
                            {{ items[sp_name].item_name }}
                        </h3>
                        <div class="meta-row">
                            <span class="meta-pill">
                                LOT: {{ items[sp_name].lot }}
                            </span>
                            <span class="meta-pill">
                                {{ items[sp_name].work_station }}
                            </span>
                            <span class="meta-pill">
                                {{ items[sp_name].input_type }}
                            </span>
                            <span class="meta-pill">
                                {{ items[sp_name].received_type }}
                            </span>
                        </div>
                    </div>
                    <div style="padding-top:45px; padding-right:20px;">
                        <button class="record-btn" @click="open_popup(sp_name)">
                            <svg class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                    d="M12 4v16m8-8H4"></path>
                            </svg>
                            Cancel Entry
                        </button>
                    </div>
                </div>
                <div class="table-wrapper no-scrollbar">
                    <table class="data-table">
                        <thead>
                            <tr class="header-row">
                                <th class="sticky-col index-col">#</th>
                                <th class="sticky-col size-col">Colour</th>
                                <th v-if="items[sp_name]['is_set_item']" class="part-col">
                                    {{ items[sp_name]['set_attr'] }}
                                </th>
                                <th v-for="size in items[sp_name]['primary_values']" :key="size"
                                    class="size-col">
                                    {{ size }}
                                </th>
                                <th class="total-col">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(colour, idx) in Object.keys(items[sp_name]['details'])" class="data-row">
                                <td class="sticky-col index-cell">{{ idx + 1 }}</td>
                                <td class="sticky-col size-cell">
                                    <span class="colour-badge">{{ colour.split("@")[0] }}</span>
                                </td>
                                <td v-if="items[sp_name]['is_set_item']" class="part-cell">
                                    <span class="part-pill">
                                        {{ items[sp_name]['details'][colour]['part']}}
                                    </span>
                                </td>
                                <td v-for="size in items[sp_name]['primary_values']" :key="size"
                                    class="size-cell">
                                    {{ items[sp_name]['details'][colour]['values'][size] }}
                                </td>
                                <td class="total-cell">
                                    <span class="total-val">
                                        {{ items[sp_name]['details'][colour]['total'] }}
                                    </span>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>    
        </div>
        <div v-else class="empty-state">
            <div class="empty-icon-wrapper">
                <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                </svg>
            </div>
            <p class="empty-text">No production data for this Warehouse</p>
        </div>
    </div>
</template>

<script setup>

import { ref, watch, onMounted } from 'vue'

const items = ref(null)
const props = defineProps({
    selected_supplier: {
        type: String,
        default: null
    },
})

const inputTypeWrapper = ref(null)
const workStationWrapper = ref(null)
const lotWrapper = ref(null)

const inputTypeControl = ref(null)
const workStationControl = ref(null)
const lotControl = ref(null)

onMounted(() => {
    inputTypeControl.value = frappe.ui.form.make_control({
        parent: inputTypeWrapper.value,
        df: {
            fieldtype: 'Link',
            options: 'Sewing Plan Input Type',
            placeholder: 'Input Type',
            fieldname: 'input_type',
            only_select: true
        },
        render_input: true
    })

    workStationControl.value = frappe.ui.form.make_control({
        parent: workStationWrapper.value,
        df: {
            fieldtype: 'Link',
            options: 'Work Station',
            placeholder: 'Work Station',
            fieldname: 'work_station',
            only_select: true
        },
        render_input: true
    })

    lotControl.value = frappe.ui.form.make_control({
        parent: lotWrapper.value,
        df: {
            fieldtype: 'Link',
            options: 'Lot',
            placeholder: 'Lot',
            fieldname: 'lot',
            only_select: true
        },
        render_input: true
    })
})

const fetchData = () => {
    if (!props.selected_supplier ) {
        items.value = null
        return
    }
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_sewing_plan_entries",
        args: {
            supplier: props.selected_supplier,
            input_type: inputTypeControl.value?.get_value(),
            work_station: workStationControl.value?.get_value(),
            lot_name: lotControl.value?.get_value(),
        },
        callback: (r) => {
            items.value = r.message
            frappe.show_alert({
                message: "Data Fetched Successfully",
                indicator: "green"
            })
        }
    })
}

function open_popup(sp_name){
    let d = new frappe.ui.Dialog({
        title: "Are you sure want to cancel the entry",
        primary_action_label: "Yes",
        secondary_action_label: "No",
        primary_action(){
            frappe.call({
                method: "production_api.production_api.doctype.sewing_plan.sewing_plan.cancel_sewing_plan_entry",
                args: {
                    "doc_id": sp_name,
                },
                callback: function(r){
                    d.hide()
                    delete items.value[sp_name]
                }
            })
        },
        secondary_action(){
            d.hide()
        }
    })
    d.show()
}

watch(
    () => props.selected_supplier,
    fetchData,
    { immediate: true }
)

</script>

<style scoped>
.placeholder-tab {
    padding: 1.5rem;
}

.filter-section {
    margin-bottom: 2rem;
    position: relative;
    z-index: 50;
    text-align: left;
}

.filter-card {
    background: white;
    padding: 1rem 1.5rem;
    border-radius: 1rem;
    border: 1px solid #f1f5f9;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
    display: flex;
    align-items: center;
    gap: 2rem;
    min-width: 400px;
    width: fit-content;
}

.filter-title-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    color: #64748b;
}

.filter-icon {
    width: 1.1rem;
    height: 1.1rem;
}

.filter-label {
    font-size: 0.875rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    white-space: nowrap;
}

.filter-control {
    flex: 1;
    min-width: 200px;
}

.filter-control :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.filter-control :deep(.control-label) {
    display: none !important;
}

.filter-control :deep(.input-with-feedback) {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 0.75rem !important;
    height: 38px !important;
    font-weight: 500 !important;
}

.plan-card {
    background: white;
    border-radius: 1.5rem;
    padding: 1.5rem;
    border: 1px solid #f1f5f9;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.04);
    margin-bottom: 2rem;
}

.plan-header {
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top:10px;
}

.plan-info {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.plan-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #94a3b8;
    background: #f8fafc;
    padding: 0.25rem 0.75rem;
    border-radius: 0.5rem;
}

.plan-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #334155;
    margin: 0;
}

.record-btn {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 1.25rem;
    background: #f85d46;
    color: white;
    border: none;
    border-radius: 0.85rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 4px 12px rgba(26, 115, 232, 0.2);
}

.record-btn:hover {
    background: #1557b0;
    transform: translateY(-1px);
    box-shadow: 0 6px 15px rgba(26, 115, 232, 0.3);
}

.record-btn:active {
    transform: translateY(0) scale(0.98);
}

.record-icon {
    width: 1rem;
    height: 1rem;
}

/* Data Table Styling */
.table-wrapper {
    overflow-x: auto;
    border-radius: 0.75rem;
    border: 1px solid #e2e8f0;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

/* Header Row */
.header-row th {
    background: transparent;
    padding: 5px;
    text-align: center;
    font-size: 0.875rem;
    font-weight: 600;
    color: #475569;
    border: 1px solid #e2e8f0;
}

.header-row th:last-child {
    border-right: 1px solid #e2e8f0;
}

.index-col,
.colour-col,
.part-col {
    text-align: center !important;
}

.sticky-col {
    position: sticky;
    left: 0;
    z-index: 10;
    background: white;
}

/* Data Rows */
.data-row {
    transition: background-color 0.15s ease;
}

.data-row:hover {
    background-color: #f8fafc;
}

.data-cell,
.index-cell,
.colour-cell,
.part-cell,
.size-cell,
.total-cell {
    padding: 10px;
    border: 1px solid #e2e8f0;
    color: #334155;
    font-weight: 500;
    white-space: nowrap;
    text-align: center;
}

.header-row th {
    font-weight: 700;
}

.data-row:last-child td {
    border-bottom: none;
}

.total-cell {
    border-right: none;
}

.index-cell,
.colour-cell {
    text-align: center;
}

.index-cell {
    color: #cbd5e1;
    font-weight: 400;
    width: 30px;
}

.colour-badge {
    color: #1e293b;
    font-weight: 500;
    font-size: 0.875rem;
}

.part-cell {
    text-align: center;
}

.part-pill {
    color: #1a73e8;
    background: #eff6ff;
    padding: 0.25rem 0.6rem;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid #dbeafe;
}

.size-cell {
    color: #1e293b;
    font-weight: 500;
    min-width: 60px;
}

.total-cell {
    background-color: transparent;
    color: #2563eb;
    font-weight: 600;
    font-size: 0.875rem;
    text-align: right;
}

.colour-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: #1e293b;
    background: #fdfdfd;
    vertical-align: middle;
    text-align: center;
}

.type-indicator {
    font-size: 0.75rem;
    font-weight: 600;
    text-align: center;
    padding: 0.25rem 0.5rem;
    border: 1px solid transparent;
}

.type-indicator.planned {
    color: #64748b;
    background: #f8fafc;
}

.type-indicator.actual {
    color: #1a73e8;
    background: #eff6ff;
}

.planned-val {
    background: #fdfdfd;
    color: #94a3b8;
    font-size: 0.875rem;
    font-weight: 500;
    text-align: center;
}

.part-cell {
    vertical-align: middle;
    text-align: center;
}

.empty-state {
    text-align: center;
    color: #94a3b8;
    padding: 3rem 0;
}

/* Scrollbar Utility */
.no-scrollbar::-webkit-scrollbar {
    height: 6px;
    width: 6px;
}

.no-scrollbar::-webkit-scrollbar-track {
    background: transparent;
}

.no-scrollbar::-webkit-scrollbar-thumb {
    background: #e2e8f0;
    border-radius: 10px;
}

.no-scrollbar::-webkit-scrollbar-thumb:hover {
    background: #cbd5e1;
}

/* Meta Row Styling */
.meta-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    flex-wrap: wrap;
}

.meta-pill {
    font-size: 0.75rem;
    font-weight: 500;
    color: #64748b;
    background-color: #f1f5f9;
    padding: 0.25rem 0.6rem;
    border-radius: 0.5rem;
    white-space: nowrap;
    border: 1px solid #e2e8f0;
}

.empty-state {
    grid-column: 1 / -1;
    padding: 8rem 0;
    text-align: center;
}

.empty-icon-wrapper {
    width: 4rem;
    height: 4rem;
    background-color: #F9FAFB;
    border-radius: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1.5rem;
    opacity: 0.4;
}

.empty-icon {
    width: 2rem;
    height: 2rem;
    color: #D1D5DB;
}

.empty-text {
    color: #9CA3AF;
    font-weight: 500;
    font-size: 0.875rem;
    margin: 0;
}
</style>
