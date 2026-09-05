<template>
    <div class="dpr-page">
        <nav class="dpr-tabs" role="tablist" aria-label="DPR reports">
            <button
                v-for="tab in tabs"
                :key="tab.id"
                type="button"
                role="tab"
                class="dpr-tab"
                :class="{ active: activeTab === tab.id }"
                :aria-selected="activeTab === tab.id"
                @click="activeTab = tab.id"
            >
                {{ tab.label }}
            </button>
        </nav>

        <section v-show="activeTab === 'cutting'" class="dpr-content">
            <DailyProductionReport />
        </section>

        <section v-show="activeTab === 'sewing'" class="dpr-content">
            <div class="sewing-warehouse-filter">
                <div class="warehouse-control" ref="supplierFieldWrapper"></div>
            </div>
            <DPRTab
                v-if="selectedSupplier"
                :selected_supplier="selectedSupplier"
                :refresh_counter="0"
            />
            <div v-else class="dpr-empty-state">
                Select a warehouse to view the Sewing DPR.
            </div>
        </section>

        <section v-show="activeTab === 'ironing'" class="dpr-content">
            <FinishingPlanIroningReport />
        </section>

        <section v-show="activeTab === 'packing'" class="dpr-content">
            <FinishingPlanDPR />
        </section>
    </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'

import DailyProductionReport from '../CuttingLaySheet/components/DailyProductionReport.vue'
import FinishingPlanDPR from '../FinishingPlanDPR/FinishingPlanDPR.vue'
import DPRTab from '../SewingPlan/components/DPRTab.vue'
import FinishingPlanIroningReport from '../components/FinishingPlanIroningReport.vue'

const tabs = [
    { id: 'cutting', label: 'Cutting' },
    { id: 'sewing', label: 'Sewing' },
    { id: 'ironing', label: 'Ironing' },
    { id: 'packing', label: 'Packing' },
]

const activeTab = ref('cutting')
const selectedSupplier = ref(null)
const supplierFieldWrapper = ref(null)
let supplierControl = null

onMounted(() => {
    nextTick(initSupplierFilter)
})

function initSupplierFilter() {
    if (!supplierFieldWrapper.value || supplierControl) return

    supplierControl = frappe.ui.form.make_control({
        parent: $(supplierFieldWrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'supplier',
            label: 'Warehouse',
            options: 'Supplier',
            placeholder: 'Select Warehouse',
            get_query: () => ({
                filters: {
                    is_company_location: 1,
                },
            }),
            change: () => {
                selectedSupplier.value = supplierControl.get_value() || null
            },
        },
        render_input: true,
    })
}
</script>

<style scoped>
.dpr-page {
    min-height: 70vh;
    padding: 18px;
}

.dpr-tabs {
    display: flex;
    gap: 6px;
    padding: 5px;
    margin-bottom: 16px;
    overflow-x: auto;
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius-lg);
    background: var(--subtle-accent);
}

.dpr-tab {
    min-width: 110px;
    padding: 9px 18px;
    border: 1px solid transparent;
    border-radius: var(--border-radius);
    background: transparent;
    color: var(--text-muted);
    font-weight: 600;
    white-space: nowrap;
}

.dpr-tab:hover {
    color: var(--text-color);
    background: var(--card-bg);
}

.dpr-tab.active {
    border-color: var(--border-color);
    background: var(--card-bg);
    color: var(--text-color);
    box-shadow: var(--shadow-sm);
}

.dpr-content {
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius-lg);
    background: var(--card-bg);
    overflow: hidden;
}

.sewing-warehouse-filter {
    padding: 16px 16px 0;
}

.warehouse-control {
    max-width: 360px;
}

.dpr-empty-state {
    display: grid;
    min-height: 320px;
    place-items: center;
    color: var(--text-muted);
}

@media (max-width: 768px) {
    .dpr-page {
        padding: 10px;
    }

    .dpr-tab {
        min-width: 92px;
        padding-inline: 14px;
    }
}
</style>
