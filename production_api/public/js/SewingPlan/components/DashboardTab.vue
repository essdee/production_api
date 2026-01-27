<template>
    <div class="dashboard-tab">
        <div class="dashboard-grid">
            <div v-for="item in items" :key="item.input_type" class="stat-card">
                <div class="stat-value-container">
                    <span class="stat-value">
                        {{ formatValue(item.qty) }}
                    </span>
                </div>

                <p class="stat-label">
                    {{ item.input_type }}
                </p>

                <div class="shine-effect"></div>
            </div>

            <div v-if="items.length === 0" class="empty-state">
                <div class="empty-icon-wrapper">
                    <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                    </svg>
                </div>
                <p class="empty-text">No production data for this Warehouse</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from 'vue'

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

const formatValue = (num) => {
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'k'
    }
    return num
}

const fetchData = () => {
    if (!props.selected_supplier) {
        items.value = []
        return
    }
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_dashboard_data",
        args: {
            supplier: props.selected_supplier
        },
        callback: (r) => {
            items.value = r.message || []
        }
    })
}

watch(() => [props.selected_supplier, props.refresh_counter], fetchData, { immediate: true })
</script>

<style scoped>
.dashboard-tab {
    padding: 1rem 0;
}

.dashboard-grid {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 2rem;
    width: 100%;
}

.stat-card {
    position: relative;
    background-color: white;
    padding: 5px;
    border-radius: 2.5rem;
    border: 1px solid #F3F4F6;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    transition: all 0.3s ease;
    overflow: hidden;
    width: 100%;
    max-width: 280px;
}

.stat-card:hover {
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
}


/* Typography */
.stat-value-container {
    margin-bottom: 0.75rem;
}

.stat-value {
    font-size: 3rem;
    font-weight: 600;
    color: #111827;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
}

.stat-label {
    font-size: 1rem;
    font-weight: 500;
    color: #64748b;
    margin-top: 0;
}

.shine-effect {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 0.25rem;
    background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.8), transparent);
    transform: translateX(-100%);
    transition: transform 1s ease;
}

.stat-card:hover .shine-effect {
    transform: translateX(100%);
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
