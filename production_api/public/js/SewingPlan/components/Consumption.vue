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
                <div class="lot-filter-wrap">
                    <div ref="lot_wrapper" class="filter-control"></div>
                </div>
                <button
                    class="record-btn"
                    :disabled="!selected_supplier || !selected_lot || (!sections.length && !clothAccData.length) || saving"
                    @click="handleSave"
                >
                    <svg class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    {{ saving ? 'Saving...' : 'Save' }}
                </button>
                <button
                    class="record-btn print-btn"
                    :disabled="!selected_ipd || saving"
                    @click="handlePrint"
                >
                    <svg class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 9V2h12v7M6 18H5a2 2 0 01-2-2v-3a2 2 0 012-2h14a2 2 0 012 2v3a2 2 0 01-2 2h-1M6 14h12v8H6z"></path>
                    </svg>
                    Print
                </button>
            </div>
        </div>

        <template v-if="sections.length">
            <div v-for="section in sections" :key="section.item" class="report-wrapper section-wrapper">
                <div class="group-header">
                    <span class="group-item">{{ section.item }}</span>
                </div>
               
                <div class="report-container no-scrollbar">
                    <table class="report-table">
                        <thead>
		                            <tr class="header-row">
		                                <th class="header-cell primary-header sticky-col-sno">S.No</th>
		                                <th
                                        v-for="attr in section.item_attributes"
                                        :key="attr"
                                        class="header-cell primary-header"
                                        :class="columnClass(attr)"
                                    >
		                                    {{ (attr || '').includes('_') ? attr.split('_').slice(1).join('_') : attr }}
		                                </th>
		                                <th class="header-cell primary-header">{{ section.item_bom_uom || 'Nos' }}</th>
		                                <th class="header-cell primary-header"> Consumption Quantity</th>
		                            </tr>
                        </thead>
                        <tbody>
	                            <tr v-for="(row, idx) in section.rows" :key="section.item + '-' + idx" class="data-row">
	                                <td class="data-cell sticky-col-sno">{{ idx + 1 }}</td>
		                                <td
                                        v-for="attr in section.item_attributes"
                                        :key="section.item + '-' + attr + '-' + idx"
                                        class="data-cell item-cell"
                                        :class="columnClass(attr)"
                                    >
		                                    {{ row.values?.[attr] || '-' }}
		                                </td>
		                                <td class="data-cell item-cell">
		                                    {{ row.item_bom_qty ?? 0 }}
	                                </td>
	                                <td class="data-cell quantity-cell">
	                                    <input
	                                        v-model.number="row.quantity"
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

        <template v-if="clothAccData.length">
            <div
                v-for="(group, groupIdx) in clothAccData"
                :key="`cloth-group-${groupIdx}`"
                class="report-wrapper section-wrapper cloth-accessory-wrapper"
            >
                <div class="group-header">
                    <div class="cloth-header-stack">
                        <span class="group-item">
                            Cloth Accessory Consumption
						</span>
						<p v-if="group.accessory_type?.length" class="cloth-accessory-name">
							 {{ group.accessory_type.join(', ') }}
						</p>
                    </div>
                </div>
                <div class="report-container no-scrollbar">
                    <table class="report-table">
                        <thead>
                            <tr class="header-row">
                                <th class="header-cell primary-header sticky-col-sno">S.No</th>
                                <th
                                    v-for="attr in group.attributes || []"
                                    :key="`cloth-header-${groupIdx}-${attr}`"
                                    class="header-cell primary-header"
                                    :class="columnClass(attr)"
                                    >
                                    {{ attr }}
                                </th>
                                <th class="header-cell primary-header">Consumption Weight</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="(row, rowIdx) in group.columns || []"
                                :key="`cloth-row-${groupIdx}-${rowIdx}`"
                                class="data-row"
                            >
                                <td class="data-cell sticky-col-sno">{{ rowIdx + 1 }}</td>
                                <td
                                    v-for="attr in group.attributes || []"
                                    :key="`cloth-cell-${groupIdx}-${rowIdx}-${attr}`"
                                    class="data-cell item-cell"
                                    :class="columnClass(attr)"
                                >
                                    {{ row[attr] || '-' }}
                                </td>
                                <td class="data-cell quantity-cell">
                                    <input
                                        v-model.number="row['Consumption Weight']"
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
const clothAccData = ref([])
const selected_ipd = ref('')
const selected_lot = ref('')
const saving = ref(false)

const lot_wrapper = ref(null)
const sample_doc = ref({})

let lotCtrl = null

const getSelectedLot = () => {
    const value = lotCtrl ? lotCtrl.get_value() : null
    return value || null
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
    clothAccData.value = []
    selected_ipd.value = ''
    selected_lot.value = getSelectedLot() || ''
}

const formatNumber = (value) => {
    if (value === null || value === undefined || value === '') {
        return '-'
    }
    return new Intl.NumberFormat().format(value)
}

const normalizeColumnName = (attr) => {
    const value = (attr || '').includes('_') ? attr.split('_').slice(1).join('_') : attr
    return String(value || '').trim().toLowerCase()
}

const columnClass = (attr) => {
    const name = normalizeColumnName(attr)
    if (!name) return ''
    if (name === 's.no') return 'col-sno'
    if (name === 'colour' || name === 'color') return 'col-colour'
    if (name === 'part') return 'col-part'
    if (name === 'name') return 'col-name'
    if (name === 'accessory') return 'col-accessory'
    if (name === 'dia') return 'col-dia'
    if (name === 'weight') return 'col-weight'
    if (name === 'qty') return 'col-qty'
    if (name.includes('consumption')) return 'col-consumption'
    return 'col-generic'
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
            clothAccData.value = r.message?.cloth_acc_data || []
            selected_ipd.value = r.message?.ipd || ''
            selected_lot.value = lot
        }
    })
}

const syncLotSelection = () => {
    if (!lotCtrl) return

    selected_lot.value = getSelectedLot() || ''
}

const initControls = () => {
    if (lot_wrapper.value && !lotCtrl) {
        lotCtrl = frappe.ui.form.make_control({
            parent: $(lot_wrapper.value),
            df: {
                fieldtype: 'Link',
                fieldname: 'lot',
                label: '',
                placeholder: 'Select Lot',
                options: 'Lot',
                get_query: () => ({
                    query: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_supplier_lots',
                    filters: {
                        supplier: props.selected_supplier
                    }
                }),
                change: () => {
                    syncLotSelection()
                    loadBomItemsFromLot()
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
    if (!props.selected_supplier || !selected_lot.value || (!sections.value.length && !clothAccData.value.length)) {
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
            cloth_acc_data: JSON.stringify(clothAccData.value),
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

const handlePrint = () => {
    if (!selected_ipd.value) {
        frappe.msgprint('Please load the Consumption rows first')
        return
    }

    const printUrl = `/printview?doctype=Item%20Production%20Detail&name=${encodeURIComponent(selected_ipd.value)}&format=Sewing%20Consumption&no_letterhead=1&lot=${encodeURIComponent(selected_lot.value || '')}`
    window.open(printUrl, '_blank')
}

onMounted(() => {
    initControls()
})

watch(() => [props.selected_supplier, props.refresh_counter], () => {
    if (lotCtrl) {
        lotCtrl.set_value('')
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
    padding: 0.5rem 0;
}

.filter-control {
    min-width: 250px;
}

.lot-filter-wrap {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
}

.selected-lot-note {
    font-size: 0.85rem;
    color: #475569;
    font-weight: 600;
    padding-left: 0.25rem;
}

.selected-lot-note span {
    color: #2563eb;
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
    border-radius: 2rem;
    padding: 0.75rem;
    border: 1px solid #f3f4f6;
    box-shadow: 0 40px 100px -20px rgba(0, 0, 0, 0.04);
}

.section-wrapper {
    margin-bottom: 0.6rem;
}

.group-header {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.25rem 0.25rem 0.45rem;
}

.group-item {
    font-size: 1rem;
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
    border-radius: 1rem;
}

.filter-section {
    margin-bottom: 0.6rem;
}

.filter-card {
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
}

.report-wrapper.section-wrapper:first-of-type {
    margin-top: 0.15rem;
}

.report-wrapper.section-wrapper.cloth-accessory-wrapper {
    margin-top: 0.25rem;
}

.cloth-accessory-wrapper .group-header {
    padding-bottom: 0.25rem;
}

.cloth-header-stack {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
}

.cloth-accessory-name {
    margin: 0;
    font-size: 0.78rem;
    line-height: 1.1;
    color: #475569;
    font-weight: 600;
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
    padding: 6px 8px;
    text-align: left;
    font-size: 0.8rem;
    font-weight: 700;
    color: #475569;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
    line-height: 1.15;
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
    min-width: 62px;
}

.data-cell {
    padding: 3px 6px;
    font-size: 0.8rem;
    font-weight: 500;
    color: #4B5563;
    white-space: nowrap;
    line-height: 1.15;
    vertical-align: middle;
}

.data-row:hover {
    background-color: #f8fafc;
}

.item-cell {
    font-weight: 600;
    color: #111827;
}

.quantity-cell {
    min-width: 120px;
}

.quantity-input {
    width: 100%;
    min-height: 26px;
    border: 1px solid #e5e7eb;
    border-radius: 0.45rem;
    background: #f8fafc;
    padding: 0.2rem 0.5rem;
    color: #111827;
    font-weight: 500;
    font-size: 0.8rem;
    line-height: 1.1;
    outline: none;
}

.quantity-input:focus {
    border-color: #60a5fa;
    box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.15);
}

.empty-state {
    padding: 6rem 0;
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
