<template>
    <div class="consumption-tab">
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filters</span>
                </div>
                <div ref="lot_wrapper" class="filter-control"></div>
                <button
                    class="record-btn"
                    :disabled="!selected_supplier || !selected_lot || !sections.length || saving"
                    @click="handleSave"
                >
                    <svg class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    {{ saving ? 'Saving...' : 'Save' }}
                </button>
            </div>
        </div>

        <template v-if="sections.length">
            <div v-for="section in sections" :key="section.item" class="report-wrapper section-wrapper">
                <div class="group-header">
                    <span class="group-item">{{ section.item }}</span>
                    <span class="group-lot-pill">{{ selected_lot }}</span>
                </div>
                <p v-if="selected_ipd" class="meta-text">IPD: {{ selected_ipd }}</p>
               
                <div class="report-container no-scrollbar">
                    <table class="report-table">
                        <thead>
                            <tr class="header-row">
                                <th class="header-cell primary-header sticky-col-sno">S.No</th>
                                <th v-for="attr in section.item_attributes" :key="attr" class="header-cell primary-header">{{ attr }}</th>
                                <th class="header-cell primary-header">Quantity</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(row, idx) in section.rows" :key="section.item + '-' + idx" class="data-row">
                                <td class="data-cell sticky-col-sno">{{ idx + 1 }}</td>
                                <td v-for="attr in section.item_attributes" :key="section.item + '-' + attr + '-' + idx" class="data-cell item-cell">
                                    {{ row.values[attr] || '-' }}
                                </td>
                                <td class="data-cell quantity-cell">
                                    <input
                                        v-model="row.quantity"
                                        type="number"
                                        min="0"
                                        step="0.001"
                                        class="quantity-input"
                                    >
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </template>

        <div v-else class="report-wrapper">
            <div class="empty-state">
                <div class="empty-icon-wrapper">
                    <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h10M7 12h10m-7 5h7M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z"></path>
                    </svg>
                </div>
                <p class="empty-text">{{ helperText }}</p>
                <p v-if="selected_ipd" class="meta-text">IPD: {{ selected_ipd }}</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

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

const lotOptions = ref([])
const sections = ref([])
const selected_ipd = ref('')
const selected_lot = ref('')
const saving = ref(false)

const lot_wrapper = ref(null)
const sample_doc = ref({})

let lotCtrl = null

const getSelectedLot = () => {
    const value = lotCtrl ? lotCtrl.get_value() : []
    return Array.isArray(value) ? value[0] || null : value || null
}

const helperText = computed(() => {
    if (!props.selected_supplier) {
        return 'Select a Warehouse to load lots'
    }
    if (!selected_lot.value) {
        return 'Select a Lot to load Stitching items from Item BOM'
    }
    return 'No Stitching Item BOM mapping rows found for the selected Lot'
})

const clearBomItems = () => {
    sections.value = []
    selected_ipd.value = ''
    selected_lot.value = getSelectedLot() || ''
}

const formatNumber = (value) => {
    if (value === null || value === undefined || value === '') {
        return '-'
    }
    return new Intl.NumberFormat().format(value)
}

const loadBomItemsFromLot = () => {
    clearBomItems()

    const lot = getSelectedLot()
    if (!lot) {
        return
    }

    frappe.call({
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_consumption_mapping_data',
        args: {
            lot,
            supplier: props.selected_supplier
        },
        callback: (r) => {
            sections.value = r.message?.sections || []
            selected_ipd.value = r.message?.ipd || ''
            selected_lot.value = lot
        }
    })
}

const syncLotSelection = () => {
    if (!lotCtrl) return

    const value = lotCtrl.get_value() || []
    if (Array.isArray(value) && value.length > 1) {
        lotCtrl.set_value([value[value.length - 1]])
    }

    selected_lot.value = getSelectedLot() || ''
}

const initControls = () => {
    if (lot_wrapper.value && !lotCtrl) {
        lotCtrl = frappe.ui.form.make_control({
            parent: $(lot_wrapper.value),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'lot',
                label: '',
                placeholder: 'Select Lot',
                change: () => {
                    syncLotSelection()
                    loadBomItemsFromLot()
                },
                get_data: function(txt) {
                    return lotOptions.value
                        .filter(row => !txt || row.lot.toLowerCase().includes(txt.toLowerCase()))
                        .map(row => ({ value: row.lot, description: '' }))
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
}

const loadLots = () => {
    if (!props.selected_supplier) {
        lotOptions.value = []
        clearBomItems()
        return
    }

    frappe.call({
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_the_lot',
        args: { supplier: props.selected_supplier },
        callback: (r) => {
            lotOptions.value = r.message?.lots || []
        }
    })
}

const handleSave = () => {
    if (!props.selected_supplier || !selected_lot.value || !sections.value.length) {
        frappe.msgprint('Please select a Lot and load Consumption rows first')
        return
    }

    saving.value = true

    frappe.call({
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.save_consumption_data',
        args: {
            supplier: props.selected_supplier,
            lot: selected_lot.value,
            sections: JSON.stringify(sections.value),
        },
        callback: (r) => {
            saving.value = false
            const spNames = r.message?.sewing_plans || []
            if (spNames.length === 1) {
                frappe.msgprint(`Saved to Sewing Plan ${spNames[0]}`)
                return
            }
            if (spNames.length > 1) {
                frappe.msgprint(`Saved to ${spNames.length} Sewing Plans`)
                return
            }
            frappe.msgprint('Consumption details saved')
        },
        error: () => {
            saving.value = false
        }
    })
}

onMounted(() => {
    initControls()
})

watch(() => [props.selected_supplier, props.refresh_counter], () => {
    if (lotCtrl) {
        lotCtrl.set_value([])
    }
    lotOptions.value = []
    selected_lot.value = ''
    clearBomItems()
    loadLots()
}, { immediate: true })
</script>

<style scoped>
@import "../SewingPlan.css";

.consumption-tab {
    padding: 1rem 0;
}

.filter-control {
    min-width: 250px;
}

.filter-control :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.filter-control :deep(.control-label) {
    display: none !important;
}

.filter-control :deep(.control-input-wrapper) {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 0.75rem !important;
    min-height: 38px !important;
    font-weight: 500 !important;
}

.filter-control :deep(.control-input) {
    background: transparent !important;
    border: none !important;
}

.filter-control :deep(.input-with-feedback) {
    background: transparent !important;
    border: none !important;
    font-weight: 500 !important;
}

.record-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
    box-shadow: none !important;
}

.report-wrapper {
    background: white;
    border-radius: 3rem;
    padding: 1rem;
    border: 1px solid #f3f4f6;
    box-shadow: 0 40px 100px -20px rgba(0, 0, 0, 0.04);
}

.section-wrapper {
    margin-bottom: 1.5rem;
}

.group-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 0.5rem 1rem;
}

.group-item {
    font-size: 1.1rem;
    font-weight: 700;
    color: #111827;
}

.group-lot-pill {
    background: #eff6ff;
    color: #2563eb;
    padding: 0.3rem 0.9rem;
    border-radius: 1rem;
    font-size: 0.8rem;
    font-weight: 600;
}

.report-container {
    overflow: auto;
    border-radius: 1.5rem;
}

.report-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-top: 1px solid #e2e8f0;
    border-left: 1px solid #e2e8f0;
}

.header-row th {
    background: white;
    padding: 15px;
    text-align: left;
    font-size: 0.875rem;
    font-weight: 700;
    color: #475569;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
}

.primary-header {
    color: #374151 !important;
}

.report-table th,
.report-table td {
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
}

.sticky-col-sno {
    min-width: 80px;
}

.data-cell {
    padding: 10px 12px;
    font-size: 0.875rem;
    font-weight: 500;
    color: #4B5563;
    white-space: nowrap;
}

.data-row:hover {
    background-color: #f8fafc;
}

.item-cell {
    font-weight: 600;
    color: #111827;
}

.quantity-cell {
    min-width: 220px;
}

.quantity-input {
    width: 100%;
    min-height: 38px;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    background: #f8fafc;
    padding: 0.55rem 0.8rem;
    color: #111827;
    font-weight: 600;
    outline: none;
}

.quantity-input:focus {
    border-color: #60a5fa;
    box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.15);
}

.empty-state {
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

.meta-text {
    color: #6B7280;
    font-size: 0.875rem;
    margin: 0 0 1rem;
}

.meta-inline {
    margin-top: -0.35rem;
}

.no-scrollbar::-webkit-scrollbar {
    display: none;
}

.no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
</style>
