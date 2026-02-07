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
                <div class="filter-control">
                      <div ref="input_type_filter_wrapper"></div>
                </div>
                <div>
                     <button class="btn btn-primary" @click="fetchDPRData()" style="border-radius: 12px; font-weight: 700;">
                        Fetch
                    </button>
                </div>
            </div>
        </div>
        <div v-if="headers && headers.length > 0">
            <div v-for="header in headers" :key="header">
                <div v-if="data.hasOwnProperty(header)" :ref="el => setSectionRef(el, header)">
                    <div class="section-header">
                        <div class="section-title-block">
                            <h3 class="section-title">{{ header }}</h3>
                        </div>
                        <div class="section-actions">
                            <button class="copy-btn" @click="copyToClipboard(header)" :disabled="copyingHeader === header" title="Copy to Clipboard">
                                <template v-if="copyingHeader === header">
                                    <svg class="copy-icon spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                                    </svg>
                                    Copying...
                                </template>
                                <template v-else>
                                    <svg class="copy-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                                    </svg>
                                    Copy
                                </template>
                            </button>
                            <div class="section-total-block">
                                <span class="total-label">Total Qty</span>
                                <span class="total-value">{{ getHeaderTotal(header) }}</span>
                            </div>
                        </div>
                    </div>
                    <div class="table-wrapper no-scrollbar">
                        <table class="data-table table-with-gap" v-for="lot in Object.keys(data[header])">
                            <thead>
                                <tr class="header-row">
                                    <th class="index-col">#</th>
                                    <th class="colour-col">Lot</th>
                                    <th class="colour-col">Item</th>
                                    <th class="colour-col">Colour</th>
                                    <th v-if="data[header][lot]['is_set_item']" class="part-col">
                                        {{ data[header][lot]['set_attr'] }}
                                    </th>
                                    <th class="colour-col">Line</th>
                                    <th class="colour-col">Type</th>
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
                                            <td class="index-cell">{{ idx + 1 }}</td>
                                            <td class="colour-cell">{{ lot }}</td>
                                            <td class="colour-cell">{{ data[header][lot]['item'] }}</td>
                                            <td class="colour-cell">
                                                <span class="colour-badge">{{ colour.split("@")[0] }}</span>
                                            </td>
                                            <td v-if="data[header][lot]['is_set_item']" class="part-cell">
                                                <span class="part-pill">
                                                    {{ data[header][lot]['details'][ws][received_type][colour]['part']}}
                                                </span>
                                            </td>
                                            <td class="colour-cell">{{ ws }}</td>
                                            <td class="colour-cell">
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
import { ref, onMounted, watch, nextTick } from 'vue'

const props = defineProps({
    selected_supplier: {
        type: String,
        required: true
    },
    refresh_counter: {
        type: Number,
        default: 0
    }
})

const date_filter_wrapper = ref(null)
const ws_filter_wrapper = ref(null)
const input_type_filter_wrapper = ref(null)
let date_filter_control = null
let ws_value = null
let input_type_control = null
const copyingHeader = ref(null)

const selected_date = ref(null)
const selected_ws = ref(null)
const selected_input_type = ref(null)
const headers = ref([])
const data = ref({})
const sectionRefs = ref({})

const setSectionRef = (el, header) => {
    if (el) {
        sectionRefs.value[header] = el
    }
}

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

    if (!input_type_filter_wrapper.value) return

    $(input_type_filter_wrapper.value).empty()

    input_type_control = frappe.ui.form.make_control({
        parent: $(input_type_filter_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'input_type',
            label: 'Input Type',
            options: 'Sewing Plan Input Type',
            placeholder: "Input Type",
            change: () => {
                selected_input_type.value = input_type_control.get_value()
            },
            get_query: () => {
                return {
                    filters: {
                        'name': ['!=', 'Order Qty']
                    }
                }
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
            input_type: selected_input_type.value
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

watch(() => [props.selected_supplier, selected_date.value, selected_ws.value, selected_input_type.value, props.refresh_counter], fetchDPRData)

const getHeaderTotal = (header) => {
    if (!data.value[header]) return 0
    let total = 0
    for (const lot of Object.keys(data.value[header])) {
        const lotData = data.value[header][lot]
        if (lotData.details) {
            for (const ws of Object.keys(lotData.details)) {
                for (const receivedType of Object.keys(lotData.details[ws])) {
                    for (const colour of Object.keys(lotData.details[ws][receivedType])) {
                        total += lotData.details[ws][receivedType][colour].total || 0
                    }
                }
            }
        }
    }
    return total
}

const copyToClipboard = async (header) => {
    const sectionEl = sectionRefs.value[header]
    copyingHeader.value = header
    if (!sectionEl) {
        console.log(`No element found for header: ${header}`)
        return
    }
    if (!sectionEl.id) {
        sectionEl.id = `dpr-section-${header.replace(/\s+/g, '-').toLowerCase()}`
    }
    console.log(`Section ID for "${header}":`, sectionEl.id)
    let ele = document.getElementById(sectionEl.id)
    if (ele) {
        let canvas = await html2canvas(ele);
        canvas.toBlob(async (blob) => {
            await setImageToClipBoard(blob);
        });
    }
}

const setImageToClipBoard = async (blob) => {
  try {
    await navigator.clipboard.write([
      new ClipboardItem({
        'image/png': blob,
      }),
    ])
    copyingHeader.value = null
    frappe.show_alert({
        message: `copied to clipboard`,
        indicator: 'green'
    })
  } catch (err) {
    copyingHeader.value = null
    frappe.show_alert({
        message: `Failed copied to clipboard`,
        indicator: 'red'
    })
  }
}

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

.copy-btn {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}


.copy-btn:hover:not(:disabled) {
    background: #1557b0;
    transform: translateY(-1px);
}

.copy-btn:disabled {
    background: #94a3b8;
    cursor: not-allowed;
}

.copy-icon {
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

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1rem 1.5rem;
    margin-bottom: 1rem;
}

.section-title-block {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.section-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.section-title {
    font-size: 1.125rem;
    font-weight: 700;
    color: #1e293b;
    margin: 0;
}

.section-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.section-total-block {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.25rem;
}

.total-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.total-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1a73e8;
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

.table-with-gap {
    margin-bottom: 24px;
}

.table-with-gap:last-child {
    margin-bottom: 0;
}
</style>
