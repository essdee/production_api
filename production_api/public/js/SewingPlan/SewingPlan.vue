<template>
    <div class="sewing-plan-page">
        <!-- Page Header -->
        <div class="page-header">
            <div class="header-container">
                <div class="header-left">
                    <h1 class="page-title">Sewing Plan</h1>
                </div>
            </div>
        </div>

        <div class="page-container">
            <div class="controls-section">
                <div class="controls-flex">
                    <div class="tab-nav no-scrollbar">
                        <button 
                            v-for="tab in tabs" 
                            :key="tab.id"
                            @click="current_tab = tab.id"
                            class="tab-button"
                            :class="{ 'active': current_tab === tab.id }"
                        >
                            <div class="tab-icon-wrapper">
                                <component :is="tab.icon" class="tab-icon" />
                            </div>
                            <span class="tab-label">{{ tab.label }}</span>
                        </button>
                    </div>
                    <div class="supplier-section">
                        <div style="padding-top:22px;">
                            <button 
                                @click="refresh_counter++"
                                class="refresh-btn"
                                title="Refresh Data"
                            >
                                <svg class="refresh-icon" :class="{ 'spinning': is_refreshing }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                                </svg>
                            </button>
                        </div>
                        <div class="supplier-input-flex">
                            <div ref="supplier_field_wrapper" class="supplier-field-container"></div>
                            <div v-if="!selected_supplier" class="search-hint">
                                <svg class="hint-icon pulsate" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                                </svg>
                            </div>
                            
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab Content Area -->
            <div class="content-card">
                <div class="card-inner">
                    <div v-if="selected_supplier">
                        <DashboardTab
                            v-show="current_tab === 'dashboard'"
                            :selected_supplier="selected_supplier"
                            :refresh_counter="refresh_counter"
                        />
                        <StatusSummaryTab 
                            v-show="current_tab === 'status_summary'" 
                            :selected_supplier="selected_supplier" 
                            :refresh_counter="refresh_counter"
                        />
                        <DataEntryTab 
                            v-show="current_tab === 'data_entry'" 
                            :selected_supplier="selected_supplier" 
                            :refresh_counter="refresh_counter"
                            @refresh="refresh_counter++"
                        />
                        <DPRTab v-show="current_tab === 'dpr'" :selected_supplier="selected_supplier" :refresh_counter="refresh_counter" />
                        <SCRTab v-show="current_tab === 'scr'" :selected_supplier="selected_supplier" :refresh_counter="refresh_counter" />
                        <LineTab 
                            v-show="current_tab === 'line'" 
                            :selected_supplier="selected_supplier" 
                            :refresh_counter="refresh_counter"
                            @refresh="refresh_counter++"
                        />
                    </div>
                    <div v-else class="global-empty-state">
                        <div class="empty-state-visual">
                            <img src="/assets/frappe/images/ui-states/list-empty-state.svg" alt="Empty State" class="empty-state-img">
                        </div>
                        <h4 class="empty-state-title">Nothing to show</h4>
                        <p class="empty-state-subtitle">Select a Warehouse to view details</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import DashboardTab from './components/DashboardTab.vue'
import StatusSummaryTab from './components/StatusSummaryTab.vue'
import DataEntryTab from './components/DataEntryTab.vue'
import DPRTab from './components/DPRTab.vue'
import SCRTab from './components/SCRTab.vue'
import LineTab from './components/LineTab.vue'

const IconOverview = () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-full h-full text-current' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2.5', d: 'M4 5a1 1 0 011-1h3a1 1 0 011 1v3a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM15 5a1 1 0 011-1h3a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h3a1 1 0 011 1v3a1 1 0 01-1 1H5a1 1 0 01-1-1v-3zM15 15a1 1 0 011-1h3a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-3z' })])
const IconLinePlan = () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-full h-full text-current' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2.5', d: 'M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2' })])
const IconManpower = () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-full h-full text-current' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2.5', d: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' })])
const IconMaterials = () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-full h-full text-current' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2.5', d: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' })])
const IconQuality = () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-full h-full text-current' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2.5', d: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' })])
const IconHistory = () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-full h-full text-current' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2.5', d: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' })])

const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: IconOverview },
    { id: 'status_summary', label: 'Status Summary', icon: IconHistory },
    { id: 'data_entry', label: 'Data Entry', icon: IconManpower },
    { id: 'dpr', label: 'DPR', icon: IconQuality },
    { id: 'scr', label: 'SCR', icon: IconMaterials },
    { id: 'line', label: 'Entries', icon: IconLinePlan },
]
const current_tab = ref('dashboard')
const selected_supplier = ref(null)
const refresh_counter = ref(0)
const is_refreshing = ref(false)
const supplier_field_wrapper = ref(null)
const sample_doc = ref({})
let supplier = null

onMounted(() => {
    initSupplierField()
})

function initSupplierField() {
    if (supplier_field_wrapper.value && !$(supplier_field_wrapper.value).find(".frappe-control").length) {
        supplier = frappe.ui.form.make_control({
            parent: $(supplier_field_wrapper.value),
            df: {
                fieldtype: "Link",
                fieldname: "supplier",
                label: "",
                options: "Supplier",
                placeholder: "Select Warehouse",
                get_query: () => {
                    return {
                        filters: {
                            is_company_location: 1
                        }
                    }
                },
                change: function() {
                    const val = supplier.get_value()
                    selected_supplier.value = val || null
                },
            },
            doc: sample_doc.value,
            render_input: true,
        })
    }
}
</script>

<style scoped>
@import "./SewingPlan.css";

.sewing-plan-page {
    padding: 2rem;
    background-color: #F9FAFB;
    min-height: 100vh;
    color: #111827;
}

.header-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.header-left {
    display: flex;
}

.page-title {
    font-size: 1.875rem;
    font-weight: 600;
    letter-spacing: -0.025em;
    color: #111827;
    margin: 0;
}

@media (min-width: 640px) {
    .page-title {
        font-size: 2.25rem;
    }
}

.controls-section {
    padding: 0 0.5rem;
}

.controls-flex {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 1.5rem;
}

@media (min-width: 1024px) {
    .controls-flex {
        flex-direction: row;
        align-items: center;
    }
}

/* Tab Navigation */
.tab-nav {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 1rem;
    padding: 0.5rem 0.25rem;
    overflow-x: auto;
}

.tab-button {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.7rem 1.75rem;
    border-radius: 1.25rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid transparent;
    cursor: pointer;
    white-space: nowrap;
    background: transparent;
    color: #94a3b8;
    outline: none;
    position: relative;
}

.tab-button:hover {
    color: #475569;
    background-color: rgba(241, 245, 249, 0.8);
}

.tab-button.active {
    background-color: #ffffff;
    color: var(--primary-color, #1a73e8);
    box-shadow: 0 15px 30px -5px rgba(26, 115, 232, 0.15), 
                0 10px 10px -5px rgba(26, 115, 232, 0.04);
    border-color: #e2e8f0;
    transform: translateY(-1px);
}

.tab-button:active {
    transform: scale(0.96) translateY(0);
}

.tab-icon-wrapper {
    width: 1.1rem;
    height: 1.1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.3s ease;
}

.tab-button:hover .tab-icon-wrapper {
    transform: scale(1.15) rotate(-3deg);
}

.tab-icon {
    width: 100%;
    height: 100%;
    color: #cbd5e1;
    transition: color 0.3s ease;
}

.tab-button.active .tab-icon {
    color: var(--primary-color, #1a73e8);
}

.tab-label {
    font-size: 0.875rem;
    font-weight: 500;
}

.supplier-section {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

@media (min-width: 1024px) {
    .supplier-section {
        width: 22rem;
    }
}

.supplier-input-flex {
    display: flex;
}

.search-hint {
    position: absolute;
    right: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
}

.refresh-btn {
    padding: 0.6rem;
    background: white;
    border: 1px solid #f3f4f6;
    border-radius: 1rem;
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(0,0,0,0.02);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.refresh-btn:hover {
    color: var(--primary-color, #1a73e8);
    border-color: #e2e8f0;
    box-shadow: 0 8px 25px rgba(0,0,0,0.05);
    background-color: #fcfcfd;
}

.refresh-btn:active {
    transform: scale(0.95);
}

.refresh-icon {
    width: 1.25rem;
    height: 1.25rem;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.spinning {
    animation: spin 1s linear infinite;
}

/* Content Card */
.content-card {
    background-color: white;
    border-radius: 3rem;
    box-shadow: 0 30px 70px rgba(0, 0, 0, 0.03);
    border: 1px solid rgba(243, 244, 246, 0.5);
    overflow: hidden;
    transition: all 0.3s ease;
}

.global-empty-state {
    padding: 6rem 0;
    text-align: center;
}

.empty-state-visual {
    width: 3rem;
    height: 3rem;
    background-color: #F9FAFB;
    border-radius: 0.75rem;
    border: 1px solid #F3F4F6;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1.5rem;
    opacity: 0.6;
}

.empty-state-img {
    filter: grayscale(1);
    width: 12.5rem;
    height: 15.625rem;
    margin: 0 auto;
}

.empty-state-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #111827;
    letter-spacing: -0.025em;
    margin-bottom: 0.5rem;
}

.empty-state-subtitle {
    font-size: 0.875rem;
    color: #9CA3AF;
    font-weight: 500;
    margin: 0;
}

/* Frappe Control Overrides */
:deep(.supplier-field-container .frappe-control) {
    margin-bottom: 0 !important;
}

:deep(.supplier-field-container input) {
    background-color: #fff !important;
    border: 1px solid #f3f4f6 !important;
    border-radius: 1.2rem !important;
    height: 30px !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding-left: 1.2rem !important;
    transition: all 0.2s ease !important;
    width: 300px !important;
    box-shadow: 0 4px 15px rgba(0,0,0,0.02);
}

:deep(.supplier-field-container input:focus) {
    border-color: var(--primary-color, #1a73e8) !important;
    box-shadow: 0 0 0 4px rgba(26, 115, 232, 0.1) !important;
}
</style>
