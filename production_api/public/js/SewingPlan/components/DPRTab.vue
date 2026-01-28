<template>
    <div class="dpr-tab">
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                    </svg>
                    <span class="filter-label">Filter by Date</span>
                </div>
                <div class="filter-control">
                    <div ref="date_filter_wrapper"></div>
                </div>
                <div class="filter-control">
                     <div ref="ws_filter_wrapper"></div>
                </div>
                <div>
                     <button class="btn btn-primary" @click="fetchDPRData()" style="border-radius: 12px; font-weight: 700;">
                        Fetch
                    </button>
                </div>
            </div>
        </div>
        <div v-if="headers && headers.length > 0">
            <div v-for="header in headers">
                <div v-if="data.hasOwnProperty(header)">
                    <h3 class="plan-title" style="margin-bottom: 10px;">{{ header }}</h3>
                    <div class="table-wrapper no-scrollbar" style="margin-bottom: 20px;">
                        <table class="data-table" v-for="lot in Object.keys(data[header])">
                            <thead>
                                <tr class="header-row">
                                    <th class="sticky-col index-col">#</th>
                                    <th class="sticky-col colour-col">Lot</th>
                                    <th class="sticky-col colour-col">Item</th>
                                    <th class="sticky-col colour-col">Colour</th>
                                    <th v-if="data[header][lot]['is_set_item']" class="part-col">
                                        {{ data[header][lot]['set_attr'] }}
                                    </th>
                                    <th class="sticky-col colour-col">Line</th>
                                    <th class="sticky-col colour-col">Type</th>
                                    <th v-for="size in data[header][lot]['primary_values']" :key="size"
                                        class="size-col">
                                        {{ size }}
                                    </th>
                                    <th class="total-col">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template v-for="(ws, idx) in Object.keys(data[header][lot]['details'])"
                                    :key="ws">
                                    <template v-for="(received_type, idx) in Object.keys(data[header][lot]['details'][ws])"
                                        :key="received_type">
                                        <tr v-for="colour in Object.keys(data[header][lot]['details'][ws][received_type])" class="data-row">
                                            <td class="sticky-col index-cell">{{ idx + 1 }}</td>
                                            <td class="sticky-col colour-cell">{{ lot }}</td>
                                            <td class="sticky-col colour-cell">{{ data[header][lot]['item'] }}</td>
                                            <td class="sticky-col colour-cell">
                                                <span class="colour-badge">{{ colour.split("@")[0] }}</span>
                                            </td>
                                            <td v-if="data[header][lot]['is_set_item']" class="part-cell">
                                                <span class="part-pill">
                                                    {{ data[header][lot]['details'][ws][received_type][colour]['part']}}
                                                </span>
                                            </td>
                                            <td class="sticky-col colour-cell">{{ ws }}</td>
                                            <td class="sticky-col colour-cell">
                                                <span class="colour-badge">{{ received_type }}</span>
                                            </td>
                                            <td v-for="size in data[header][lot]['primary_values']" :key="size"
                                                class="size-cell">
                                                {{ data[header][lot]['details'][ws][received_type][colour]['values'][size] }}
                                            </td>
                                            <td class="total-cell">
                                                <span class="total-val">
                                                    {{ data[header][lot]['details'][ws][received_type][colour]['total'] }}
                                                </span>
                                            </td>
                                        </tr>
                                    </template>        
                                </template>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="empty-state">
            <p>Select a Date to view the report</p>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
    selected_supplier: {
        type: String,
        required: true
    }
})

const date_filter_wrapper = ref(null)
const ws_filter_wrapper = ref(null)
let date_filter_control = null
let ws_value = null

const selected_date = ref(null)
const selected_ws = ref(null)
const headers = ref([])
const data = ref({})

const initFilter = () => {
    if (!date_filter_wrapper.value) return

    $(date_filter_wrapper.value).empty()

    date_filter_control = frappe.ui.form.make_control({
        parent: $(date_filter_wrapper.value),
        df: {
            fieldtype: 'Date',
            fieldname: 'date',
            label: 'Date',
            default: selected_date.value,
            placeholder: "Date",
            change: () => {
                selected_date.value = date_filter_control.get_value()
            }
        },
        render_input: true
    })
    if (!ws_filter_wrapper.value) return

    $(ws_filter_wrapper.value).empty()

    ws_value = frappe.ui.form.make_control({
        parent: $(ws_filter_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'work_station',
            label: 'Work Station',
            options: 'Work Station',
            placeholder: "Work Station",
            change: () => {
                selected_ws.value = ws_value.get_value()
            }
        },
        render_input: true
    })
}

const fetchDPRData = () => {
    if (!props.selected_supplier || !selected_date.value) return
    frappe.call({
        method: 'production_api.production_api.doctype.sewing_plan.sewing_plan.get_sewing_plan_dpr_data',
        args: {
            supplier: props.selected_supplier,
            dpr_date: selected_date.value,
            work_station: selected_ws.value ,
        },
        callback: (r) => {
            headers.value = r.message.headers
            data.value = r.message.dpr_data
        }
    })
}

onMounted(() => {
    initFilter()
})

watch(() => [props.selected_supplier, selected_date.value, selected_ws.value], fetchDPRData)

</script>
    
<style scoped>
@import "../SewingPlan.css";

.dpr-tab {
    padding: 1rem;
}

.plan-card {
    background: white;
    border-radius: 1.5rem;
    padding: 10px;
    border: 1px solid #f1f5f9;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.04);
}

.plan-header {
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
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

.colour-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: #1e293b;
    background: #fdfdfd;
    vertical-align: middle;
    text-align: center;
}

.part-cell {
    vertical-align: middle;
    text-align: center;
}
</style>