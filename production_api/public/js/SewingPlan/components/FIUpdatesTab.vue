<template>
    <div class="fi-updates-tab">
        <div class="results-container" v-if="hasData">
            <div class="results-header">
                <h3 class="results-title">FI Update Details</h3>
                <div class="results-actions">
                    <span class="results-count">{{ totalCount }} entries</span>
                    <button class="btn btn-primary update-btn" @click="updateData()" :disabled="updating">
                        <template v-if="updating">
                            <svg class="btn-icon spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                            </svg>
                            Updating...
                        </template>
                        <template v-else>
                            <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                            </svg>
                            Update
                        </template>
                    </button>
                </div>
            </div>
            
            <div v-for="lot in lotKeys" :key="lot" class="lot-section">
                <div class="lot-header">
                    <div class="lot-accent-dot"></div>
                    <div class="lot-info">
                        <h3 class="lot-title">{{ lot }}</h3>
                        <span class="lot-item">{{ groupedItems[lot].item }}</span>
                    </div>
                    <span class="lot-count">{{ groupedItems[lot].items.length }} entries</span>
                </div>
                <div class="table-wrapper no-scrollbar">
                    <table class="data-table">
                        <thead>
                            <tr class="header-row">
                                <th class="index-col">#</th>
                                <th class="colour-col">Colour</th>
                                <th v-if="groupedItems[lot].is_set_item" class="part-col">{{ groupedItems[lot].set_attr }}</th>
                                <th class="date-col">Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(item, idx) in groupedItems[lot].items" :key="`${lot}-${idx}`" class="data-row">
                                <td class="index-cell">{{ idx + 1 }}</td>
                                <td class="colour-cell">
                                    <span class="colour-badge">{{ item.colour }}</span>
                                </td>
                                <td v-if="groupedItems[lot].is_set_item" class="part-cell">
                                    <span class="part-pill">{{ item.part }}</span>
                                </td>
                                <td class="date-cell">
                                    <div :id="`date-field-${lot}-${idx}`" class="date-field-wrapper"></div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div v-else-if="props.selected_supplier" class="empty-state">
            <div class="empty-icon-wrapper">
                <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                </svg>
            </div>
            <p class="empty-text">No pending FI dates to update</p>
        </div>
        
        <div v-else class="empty-state">
            <p>Select a Warehouse to view the details</p>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'

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

const items = ref([])
const updating = ref(false)
const dateControls = ref({})

const clearDateControls = () => {
    Object.values(dateControls.value).forEach(control => {
        if (control && control.$wrapper) {
            control.$wrapper.remove()
        }
    })
    dateControls.value = {}
}

const initDateControls = () => {
    clearDateControls()
    
    lotKeys.value.forEach(lot => {
        const lotData = groupedItems.value[lot]
        
        lotData.items.forEach((item, idx) => {
            const fieldId = `date-field-${lot}-${idx}`
            const wrapper = document.getElementById(fieldId)
            if (!wrapper) return
            
            $(wrapper).empty()
            
            const control = frappe.ui.form.make_control({
                parent: $(wrapper),
                df: {
                    fieldtype: 'Date',
                    fieldname: `date_${lot}_${idx}`,
                    label: '',
                    change: () => {
                        item.date = control.get_value() || ''
                    }
                },
                render_input: true
            })
            
            if (item.date) {
                control.set_value(item.date)
            }
            
            const controlKey = `${lot}-${idx}`
            dateControls.value[controlKey] = control
        })
    })
}

const groupedItems = computed(() => {
    const grouped = {}
    items.value.forEach(item => {
        const lot = item.lot
        if (!grouped[lot]) {
            grouped[lot] = {
                items: [],
                item: item.item,
                is_set_item: item.is_set_item,
                set_attr: item.set_attr
            }
        }
        grouped[lot].items.push(item)
    })
    return grouped
})

const lotKeys = computed(() => {
    return Object.keys(groupedItems.value)
})

const hasData = computed(() => {
    return lotKeys.value.length > 0
})

const totalCount = computed(() => {
    return items.value.length
})

const fetchData = () => {
    if (!props.selected_supplier) {
        items.value = []
        clearDateControls()
        return
    }
    
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_fi_updates_data",
        args: {
            supplier: props.selected_supplier
        },
        callback: async (r) => {
            if (r.message) {
                items.value = (r.message.data || []).map(item => ({
                    ...item,
                    date: ''
                }))
                await nextTick()
                initDateControls()
            }
        }
    })
}

const updateData = () => {
    if (items.value.length === 0) return
    
    // Filter only items with dates set
    const data_to_update = items.value.filter(item => item.date).map(item => ({
        colour: item.colour,
        part: item.part,
        date: item.date,
        sewing_plan: item.sewing_plan,
        lot: item.lot
    }))
    
    if (data_to_update.length === 0) {
        frappe.show_alert({
            message: 'No dates to update',
            indicator: 'orange'
        })
        return
    }
    
    updating.value = true
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.update_fi_dates",
        args: {
            data: data_to_update
        },
        callback: (r) => {
            updating.value = false
            if (r.message === 'Success') {
                frappe.show_alert({
                    message: 'FI Dates updated successfully',
                    indicator: 'green'
                })
                // Refresh data to show only remaining pending items
                fetchData()
            }
        },
        error: () => {
            updating.value = false
        }
    })
}

onMounted(() => {
    fetchData()
})

watch(() => [props.selected_supplier, props.refresh_counter], () => {
    items.value = []
    clearDateControls()
    fetchData()
})
</script>

<style scoped>
@import "../SewingPlan.css";

.fi-updates-tab {
    padding: 1.5rem;
}

.results-container {
    background: white;
    border-radius: 1rem;
    padding: 1.5rem;
    border: 1px solid #e2e8f0;
    margin-top: 1rem;
    width: 50%;
}

.results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e2e8f0;
}

.results-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #334155;
    margin: 0;
}

.results-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.results-count {
    font-size: 0.875rem;
    font-weight: 500;
    color: #64748b;
    background: #f1f5f9;
    padding: 0.25rem 0.75rem;
    border-radius: 0.5rem;
}

.update-btn {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
}

.update-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
}

.btn-icon {
    width: 1rem;
    height: 1rem;
}

.spin {
    animation: spin 1s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

/* Lot Section Styling */
.lot-section {
    margin-bottom: 2rem;
}

.lot-section:last-child {
    margin-bottom: 0;
}

.lot-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    margin-bottom: 1rem;
}

.lot-accent-dot {
    width: 0.5rem;
    height: 0.5rem;
    background-color: var(--primary, #1a73e8);
    border-radius: 50%;
}

.lot-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
}

.lot-title {
    font-size: 1rem;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
}

.lot-item {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
}

.lot-count {
    font-size: 0.75rem;
    font-weight: 500;
    color: #64748b;
    background: #fff;
    padding: 0.25rem 0.6rem;
    border-radius: 0.5rem;
}

.data-table {
    border-collapse: collapse;
    font-size: 0.875rem;
}

.header-row th {
    background: #f8fafc;
    padding: 12px;
    text-align: left;
    font-size: 0.875rem;
    font-weight: 700;
    color: #475569;
    border: 1px solid #e2e8f0;
}

.data-row {
    transition: background-color 0.15s ease;
}

.data-row:hover {
    background-color: #f8fafc;
}

.index-cell,
.colour-cell,
.part-cell,
.date-cell {
    padding: 10px;
    border: 1px solid #e2e8f0;
    color: #334155;
    font-weight: 500;
}

.index-cell {
    width: 50px;
    text-align: center;
    color: #94a3b8;
}

.date-cell {
    width: 150px;
}

.colour-badge {
    color: #1e293b;
    font-weight: 500;
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

.date-field-wrapper :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.date-field-wrapper :deep(input) {
    background-color: #fff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 0.5rem !important;
    height: 36px !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 0 0.75rem !important;
    width: 100% !important;
}

.date-field-wrapper :deep(input:focus) {
    border-color: #1a73e8 !important;
    box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.1) !important;
}

.date-field-wrapper :deep(.control-label) {
    display: none !important;
}

.empty-state {
    text-align: center;
    color: #94a3b8;
    padding: 3rem 0;
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
