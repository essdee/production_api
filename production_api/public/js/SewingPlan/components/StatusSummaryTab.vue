<template>
    <div class="status-summary-tab">
        <div class="report-wrapper">
            <div class="report-container no-scrollbar">
                <table class="report-table">
                    <thead>
                        <tr class="header-row">
                            <th v-for="header in items['header1']" :key="header" class="header-cell primary-header">
                                {{ header }}
                            </th>
                            <th v-for="header in items['header2']" :key="header" class="header-cell primary-header">
                                {{ header }}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(row, idx) in items['data']" :key="idx" class="data-row">
                            <template v-if="idx == 0">
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td class="data-cell"></td>
                                <td v-for="header in items['header2']" :key="header" class="data-cell numeric-cell">
                                    {{ formatNumber(row[header]) }}
                                </td>
                            </template>
                            <template v-else>
                                <td class="data-cell item-cell">{{ row['item'] }}</td>
                                <td class="data-cell">
                                    <span class="lot-pill">{{ row['lot'] }}</span>
                                </td>
                                <td class="data-cell item-cell">{{ row['attr_details'][row['pack_attr']] }}</td>
                                <td class="data-cell item-cell">{{ row['attr_details'][row['set_attr']] }}</td>
                                <td v-for="header in items['header2']" :key="header" class="data-cell numeric-cell">
                                    {{ formatNumber(row[header]) }}
                                </td>
                            </template>    
                        </tr>
                    </tbody>
                </table>
                
                <div v-if="items['data'].length === 0" class="empty-report">
                    <div class="empty-visual">
                        <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                    </div>
                    <p class="empty-text">No production data available for this Warehouse</p>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from "vue"

const props = defineProps({
    selected_supplier: {
        type: String,
        default: null
    },
    refresh_counter: {
        type: Number,
        default: 0
    }
})

const items = ref({
    "header1": [],
    "header2": [],
    "data": []
})

const formatNumber = (val) => {
    if (!val && val !== 0) return '-'
    return new Intl.NumberFormat().format(val)
}

const fetchData = () => {
    if (!props.selected_supplier) {
        items.value = { "header1": [], "header2": [], "data": [] }
        return
    }
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_sp_status_summary",
        args: {
            supplier: props.selected_supplier
        },
        callback: (r) => {
            if (r.message) {
                items.value = {
                    header1: r.message.header1 || [],
                    header2: r.message.header2 || [],
                    data: r.message.data || []
                }
            }
        }
    })
}

watch(() => [props.selected_supplier, props.refresh_counter], fetchData, { immediate: true })
</script>

<style scoped>
.status-summary-tab {
    padding: 1rem 0;
}

.report-wrapper {
    background: white;
    border-radius: 3rem;
    padding: 1rem;
    border: 1px solid #f3f4f6;
    box-shadow: 0 40px 100px -20px rgba(0, 0, 0, 0.04);
}

.report-container {
    overflow: auto;
    max-height: 65vh;
    border-radius: 2.2rem;
    position: relative;
}

.report-table {
    width: 100%;
    border-collapse: collapse;
    border-spacing: 0;
}

/* Header Row */
.header-row th {
    position: sticky;
    top: 0;
    z-index: 20;
    background: transparent;
    padding: 15px;
    text-align: left;
    font-size: 0.875rem;
    font-weight: 700;
    color: #475569;
    border: 1px solid #e2e8f0;
}

.primary-header {
    color: #374151 !important;
}

.data-cell {
    padding: 5px;
    border: 1px solid #e2e8f0;
    font-size: 0.875rem;
    font-weight: 500;
    color: #4B5563;
    white-space: nowrap;
    transition: all 0.2s ease;
}

.data-row {
    transition: background-color 0.2s ease;
}

.data-row:hover {
    background-color: #f8fafc;
}

.data-row:hover .data-cell {
    color: #111827;
}

.item-cell {
    font-weight: 600;
    color: #111827;
    font-size: 0.875rem;
}

.lot-pill {
    background: #eff6ff;
    color: #2563eb;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-block;
}

.attr-cell {
    color: #9CA3AF;
    font-size: 0.8rem;
}

.numeric-cell {
    text-align: right;
    font-weight: 600;
    font-size: 1rem;
    color: #111827;
}

/* Empty State Styling */
.empty-report {
    padding: 10rem 2rem;
    text-align: center;
}

.empty-visual {
    width: 5rem;
    height: 5rem;
    background: #fdfdfd;
    border-radius: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 2rem;
    border: 1px solid #f3f4f6;
}

.empty-icon {
    width: 2.5rem;
    height: 2.5rem;
    color: #e5e7eb;
}

.empty-text {
    font-size: 0.875rem;
    font-weight: 500;
    color: #9CA3AF;
    margin: 0;
}

/* Scrollbar Utility */
.no-scrollbar::-webkit-scrollbar {
    display: none;
}
.no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
</style>
