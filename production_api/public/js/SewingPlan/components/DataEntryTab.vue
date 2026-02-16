<template>
    <div class="data-entry-tab">
        <!-- Filter Section -->
        <div class="filter-section">
            <div class="filter-card">
                <div class="filter-title-group">
                    <svg class="filter-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z">
                        </path>
                    </svg>
                    <span class="filter-label">Filter by Lot</span>
                </div>
                <div class="filter-control">
                    <div ref="lot_filter_wrapper"></div>
                </div>
            </div>
        </div>

        <div v-if="items && Object.keys(items).length > 0" class="data-entry-container">
            <div v-for="lot in Object.keys(items)" :key="lot" class="lot-section">
                <div class="lot-header">
                    <div class="lot-accent-dot"></div>
                    <h3 class="lot-title">{{ lot }}</h3>
                </div>
                <div v-for="sewing_plan in Object.keys(items[lot])" :key="sewing_plan" class="plan-card">
                    <div class="plan-header">
                        <div class="plan-info">
                            <h4 class="plan-title">{{ sewing_plan }} - {{ items[lot][sewing_plan]['details']['item'] }}
                            </h4>
                        </div>
                        <div class="action-buttons">
                            <button class="record-btn" @click="openModal(lot, sewing_plan)">
                                <svg class="record-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                        d="M12 4v16m8-8H4"></path>
                                </svg>
                                Record Entry
                            </button>
                            <button class="update-btn" @click="openUpdateModal(lot, sewing_plan)">
                                <svg class="update-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                                </svg>
                                UPDATE
                            </button>
                        </div>
                    </div>

                    <div class="table-wrapper no-scrollbar">
                        <table class="data-table">
                            <thead>
                                <tr class="header-row">
                                    <th class="index-col">#</th>
                                    <th class="colour-col">Colour</th>
                                    <th v-if="items[lot][sewing_plan]['details']['is_set_item']" class="part-col">
                                        {{ items[lot][sewing_plan]['details']['set_attr'] }}
                                    </th>
                                    <th v-for="size in items[lot][sewing_plan]['details']['primary_values']" :key="size"
                                        class="size-col">
                                        {{ size }}
                                    </th>
                                    <th class="total-col">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(colour, idx) in Object.keys(items[lot][sewing_plan]['colours'])"
                                    :key="colour" class="data-row">
                                    <td class="index-cell">{{ idx + 1 }}</td>
                                    <td class="colour-cell">
                                        <span class="colour-badge">{{ colour.split("@")[0] }}</span>
                                    </td>
                                    <td v-if="items[lot][sewing_plan]['details']['is_set_item']" class="part-cell">
                                        <span class="part-pill">{{ items[lot][sewing_plan]['colours'][colour]['part']
                                        }}</span>
                                    </td>
                                    <td v-for="size in items[lot][sewing_plan]['details']['primary_values']" :key="size"
                                        class="size-cell">
                                        {{ items[lot][sewing_plan]['colours'][colour]["values"]?.[size]?.order_qty ?? 0
                                        }}
                                    </td>
                                    <td class="total-cell">
                                        <span class="total-val">{{ items[lot][sewing_plan]['colours'][colour]['qty']
                                        }}</span>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="empty-entry">
            <div class="empty-visual">
                <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z">
                    </path>
                </svg>
            </div>
            <p class="empty-text">No data entry plans found for this warehouse</p>
        </div>

        <!-- Data Entry Modal -->
        <div v-if="show_modal" class="modal-overlay" @click.self="closeModal">
            <div class="modal-content no-scrollbar">
                <div class="modal-header">
                    <div class="modal-title-group">
                        <span class="modal-subtitle">{{ active_lot }}</span>
                        <h2 class="modal-title">{{ active_plan }}</h2>
                    </div>
                    <button class="close-btn" @click="closeModal">
                        <svg class="close-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <div class="modal-body">
                    <div class="form-grid">
                        <div ref="date_field_wrapper"></div>
                        <div ref="time_field_wrapper"></div>
                        <div ref="ws_field_wrapper"></div>
                        <div ref="type_field_wrapper"></div>
                        <div ref="grn_type_field_wrapper"></div>
                    </div>

                    <div class="matrix-container">
                        <div class="modal-table-wrapper no-scrollbar">
                            <table class="modal-table">
                                <thead class="header-row">
                                    <tr>
                                        <th class="sticky-col">Colour</th>
                                        <th v-if="modal_data?.details['is_set_item']" class="part-col">
                                            {{ modal_data?.details['set_attr'] }}
                                        </th>
                                        <th class="type-col">Type</th>
                                        <th v-for="size in modal_data?.details?.primary_values" :key="size">{{ size }}
                                        </th>
                                        <th class="total-col">Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <template v-for="colour in Object.keys(modal_data?.colours)" :key="colour">
                                        <tr class="order-qty-row">
                                            <td rowspan="2" class="colour-name">
                                                <div class="colour-checkbox-group">
                                                    <input type="checkbox" 
                                                        class="fill-checkbox" 
                                                        @change="(e) => fillColourQuantities(colour, e)">
                                                    <span>{{ colour.split("@")[0] }}</span>
                                                </div>
                                            </td>
                                            <td v-if="modal_data?.details['is_set_item']" rowspan="2" class="part-cell">
                                                <span class="part-pill">{{ modal_data?.colours[colour]['part'] }}</span>
                                            </td>
                                            <td class="type-indicator planned">
                                                {{ input_type.display }}
                                                <span class="remaining-badge" v-if="modal_data.colours[colour].values[modal_data?.details?.primary_values[0]]?.[input_type.input_key] > 0">
                                                    (Remaining)
                                                </span>
                                            </td>
                                            <td v-for="size in modal_data?.details?.primary_values" :key="size"
                                                class="matrix-cell planned-val">
                                                {{ modal_data.colours[colour].values[size]?.[input_type.remaining_key] ?? modal_data.colours[colour].values[size]?.[input_type.base_key] ?? 0 }}
                                            </td>
                                            <td class="matrix-cell planned-val total-cell-bold">
                                                {{ getColourTotal(colour, input_type.remaining_key) || getColourTotal(colour, input_type.base_key) }}
                                            </td>
                                        </tr>
                                        <tr class="entry-row">
                                            <td class="type-indicator actual">Issued Qty</td>
                                            <td v-for="size in modal_data?.details?.primary_values" :key="size"
                                                class="matrix-cell">
                                                <div v-if="modal_data.colours[colour].values[size]">
                                                    <input type="number"
                                                        v-model.number="modal_data.colours[colour].values[size].data_entry"
                                                        class="qty-input" placeholder="0">
                                                </div>
                                            </td>
                                            <td class="matrix-cell total-cell-bold">
                                                {{ getColourTotal(colour, 'data_entry') }}
                                            </td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="modal-footer">
                    <button class="cancel-btn" @click="closeModal">Cancel</button>
                    <button class="submit-btn" @click="submitLog">
                        Submit
                    </button>
                </div>
            </div>
        </div>
        <!-- Update Modal -->
        <div v-if="show_update_modal" class="modal-overlay" @click.self="closeUpdateModal">
            <div class="modal-content update-modal no-scrollbar">
                <div class="modal-header">
                    <div class="modal-title-group">
                        <span class="modal-subtitle">{{ active_lot }}</span>
                        <h2 class="modal-title">{{ active_plan }}</h2>
                    </div>
                    <button class="close-btn" @click="closeUpdateModal">
                        <svg class="close-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <div class="modal-body">
                    <div class="inspection-controls-wrapper">
                        <div class="inspection-select-wrapper">
                            <label class="inspection-label">Inspection Type</label>
                            <select @change="handleInspectionTypeChange" v-model="selected_val" class="inspection-select">
                                <option value="pre_final">Prefinal</option>
                                <option value="final_inspection">Final Inspection</option>
                            </select>
                        </div>
                        <div class="cancel-checkbox-wrapper">
                            <input type="checkbox" id="cancel_updates" v-model="cancel_updates" class="cancel-checkbox">
                            <label for="cancel_updates" class="cancel-checkbox-label">Cancel the updates</label>
                        </div>
                    </div>
                    <div class="update-table-wrapper no-scrollbar">
                        <table class="update-table">
                            <thead>
                                <tr>
                                    <th class="checkbox-col">
                                        <input type="checkbox" @change="toggleAllRowSelection" :checked="isAllSelected">
                                    </th>
                                    <th>Colour</th>
                                    <th>{{ selected_inspection_type.split("_").join(" ").toUpperCase() }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="colour in Object.keys(update_modal_data?.colours || {})" :key="colour">
                                    <td class="checkbox-cell">
                                        <input type="checkbox" v-model="selected_rows" :value="colour">
                                    </td>
                                    <td>{{ colour.split("@")[0] }}</td>
                                    <td>{{ update_modal_data.colours[colour]['inspection_total'][selected_inspection_type] }}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="modal-footer">
                    <button class="cancel-btn" @click="closeUpdateModal">Cancel</button>
                    <button class="submit-btn" :disabled="selected_rows.length === 0" @click="submitUpdate">
                        Submit
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, computed } from 'vue'

const items = ref([])
const diff = ref({})
const allowances = ref({})
const diff_key = ref(null)
const show_modal = ref(false)
const show_update_modal = ref(false)
const active_lot = ref('')
const active_plan = ref('')
const modal_data = ref({})
const update_modal_data = ref({})
const selected_lot = ref('')
const selected_rows = ref([])
const inspection_type = ref('')
const selected_inspection_type = ref('')
const selected_val = ref(null)
const cancel_updates = ref(false)
const isAllSelected = computed(() => {
    if (!update_modal_data.value?.colours) return false
    const keys = Object.keys(update_modal_data.value.colours)
    return keys.length > 0 && selected_rows.value.length === keys.length
})

const toggleAllRowSelection = (e) => {
    if (e.target.checked) {
        selected_rows.value = Object.keys(update_modal_data.value.colours)
    } else {
        selected_rows.value = []
    }
}

// Filter ref
const lot_filter_wrapper = ref(null)
let lot_filter_control = null

// Refs for Frappe control wrappers
const date_field_wrapper = ref(null)
const time_field_wrapper = ref(null)
const ws_field_wrapper = ref(null)
const type_field_wrapper = ref(null)
const grn_type_field_wrapper = ref(null)

// Frappe control instances
let date_control = null
let time_control = null
let ws_control = null
let type_control = null
let grn_type_control = null

const emit = defineEmits(['refresh'])

const getColourTotal = (colour, field) => {
    const colourData = modal_data.value.colours[colour]
    if (!colourData) return 0
    return Object.values(colourData.values).reduce((acc, curr) => acc + (curr[field] || 0), 0)
}

const fillColourQuantities = (colour, event) => {
    const isChecked = event.target.checked
    const colourData = modal_data.value.colours[colour]
    if (!colourData) return

    const inputTypeInfo = input_type.value
    Object.keys(colourData.values).forEach(size => {
        if (isChecked) {
            // Use remaining quantity if available, otherwise fall back to base
            const remainingQty = colourData.values[size]?.[inputTypeInfo.remaining_key] ?? 
                                 colourData.values[size]?.[inputTypeInfo.base_key] ?? 0
            colourData.values[size].data_entry = remainingQty
        } else {
            colourData.values[size].data_entry = 0
        }
    })
}

const entry_form = ref({
    date: frappe.datetime.now_date(),
    time: frappe.datetime.now_time(),
    work_station: '',
    input_type: 'Input Qty',
    grn_item_type: 'Accepted',
    quantities: {}
})

const openModal = async (lot, plan) => {
    active_lot.value = lot
    active_plan.value = plan

    modal_data.value = items.value[lot][plan]
    console.log(modal_data.value)
    Object.keys(modal_data.value.colours).forEach(colour => {
        console.log(colour)
        Object.keys(modal_data.value.colours[colour].values).forEach(size => {
            modal_data.value.colours[colour].values[size].data_entry = 0
        })
    })
    show_modal.value = true
    await nextTick()
    initFrappeControls()
}

const openUpdateModal = (lot, plan) => {
    active_lot.value = lot
    active_plan.value = plan
    update_modal_data.value = items.value[lot][plan]
    selected_rows.value = []
    selected_inspection_type.value = inspection_type.value
    selected_val.value = 'pre_final'
    cancel_updates.value = false
    show_update_modal.value = true
}

const handleInspectionTypeChange = (e) => {
    const selectedValue = e.target.value
    if (selectedValue === 'pre_final') {
        selected_inspection_type.value = inspection_type.value
    } else {
        selected_inspection_type.value = 'pre_final'
    }
}

const closeUpdateModal = () => {
    show_update_modal.value = false
    selected_rows.value = []
    selected_inspection_type.value = inspection_type.value
    selected_val.value = 'pre_final'
    cancel_updates.value = false
}

const submitUpdate = () => {
    if (selected_rows.value.length === 0) {
        frappe.msgprint('Please select at least one row')
        return
    }

    const action = cancel_updates.value ? 'revert' : 'update'
    const confirmMessage = cancel_updates.value 
        ? 'Are you sure you want to cancel/revert the updates for the selected rows?' 
        : 'Are you sure you want to update the selected rows?'

    frappe.confirm(
        confirmMessage,
        () => {
            // User confirmed
            const payload = {
                lot: active_lot.value,
                plan: active_plan.value,
                inspection_type: selected_inspection_type.value,
                action: action,
                rows: selected_rows.value.map(colour => {
                    return {
                        colour: colour,
                        qty: update_modal_data.value.colours[colour].values,
                        set_combination: update_modal_data.value.colours[colour].set_combination,
                        part: update_modal_data.value.colours[colour].part
                    }
                })
            }

            frappe.call({
                method: "production_api.production_api.doctype.sewing_plan.sewing_plan.update_sewing_plan_data",
                args: {
                    payload: payload
                },
                callback: (r) => {
                    if (r.message === "Success") {
                        frappe.show_alert({
                            message: __(cancel_updates.value ? 'Updates cancelled successfully' : 'Data updated successfully'),
                            indicator: 'green'
                        })
                        closeUpdateModal()
                        fetchData()
                        emit('refresh')
                    }
                }
            })
        },
        () => {
            // User cancelled the confirmation
            return
        }
    )
}

const initLotFilter = () => {
    if (!lot_filter_wrapper.value) return
    $(lot_filter_wrapper.value).empty()

    lot_filter_control = frappe.ui.form.make_control({
        parent: $(lot_filter_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'lot',
            options: 'Lot',
            label: 'Lot',
            change: () => {
                selected_lot.value = lot_filter_control.get_value()
            }
        },
        render_input: true,
    })
}

onMounted(() => {
    initLotFilter()
})

const initFrappeControls = () => {
    [date_field_wrapper, time_field_wrapper, ws_field_wrapper, type_field_wrapper].forEach(w => {
        if (w.value) $(w.value).empty()
    })

    date_control = frappe.ui.form.make_control({
        parent: $(date_field_wrapper.value),
        df: {
            fieldtype: 'Date',
            fieldname: 'date',
            label: 'Date',
            default: entry_form.value.date,
            change: () => { entry_form.value.date = date_control.get_value() }
        },
        render_input: true,
    })
    date_control.set_value(entry_form.value.date)
    date_control.refresh()

    time_control = frappe.ui.form.make_control({
        parent: $(time_field_wrapper.value),
        df: {
            fieldtype: 'Time',
            fieldname: 'time',
            label: 'Time',
            default: entry_form.value.time,
            change: () => { entry_form.value.time = time_control.get_value() }
        },
        render_input: true,
    })
    time_control.set_value(entry_form.value.time)
    time_control.refresh()

    ws_control = frappe.ui.form.make_control({
        parent: $(ws_field_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'work_station',
            options: 'Work Station',
            label: 'Work Station',
            change: () => { entry_form.value.work_station = ws_control.get_value() }
        },
        render_input: true,
    })

    type_control = frappe.ui.form.make_control({
        parent: $(type_field_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'input_type',
            options: 'Sewing Plan Input Type',
            label: 'Input Type',
            get_query: () => {
                return {
                    filters: {
                        'name': ['!=', 'Order Qty']
                    }
                }
            },
            change: () => { entry_form.value.input_type = type_control.get_value() }
        },
        render_input: true,
    })

    grn_type_control = frappe.ui.form.make_control({
        parent: $(grn_type_field_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'grn_item_type',
            options: 'GRN Item Type',
            label: 'GRN Item Type',
            change: () => { entry_form.value.grn_item_type = grn_type_control.get_value() },
            get_query(){
                return {
                    filters: {
                        'show_in_sewing_plan': 1,
                    }
                }
            }
        },
        render_input: true,
    })
    grn_type_control.set_value(entry_form.value.grn_item_type)
    grn_type_control.refresh()
}

const closeModal = () => {
    show_modal.value = false
}

const input_type = computed(() => {
    const type_val = entry_form.value.input_type
    if (!type_val) return 'Order Qty'
    let x = type_val
    let lower = x.toLowerCase()
    let replaced = lower.replace(/ /g, "_")
    diff_key.value = diff.value[replaced]
    // Store the selected input type key for remaining quantity lookup
    const remaining_key = `${replaced}_remaining`
    return {
        display: diff.value[replaced]?.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') || 'Order Qty',
        base_key: diff.value[replaced],
        remaining_key: remaining_key,
        input_key: replaced
    }
})

const submitLog = () => {
    if (!entry_form.value.date || !entry_form.value.time || !entry_form.value.work_station || !entry_form.value.input_type || !entry_form.value.grn_item_type) {
        frappe.msgprint('Please fill all the required fields')
        return
    }

    // Validation Loop
    let validation_failed = false;
    const inputTypeInfo = input_type.value
    for (const colour of Object.keys(modal_data.value.colours)) {
        if (validation_failed) break;
        for (const size of Object.keys(modal_data.value.colours[colour].values)) {
             const entered_qty = modal_data.value.colours[colour].values[size].data_entry || 0;
             // Use remaining quantity for validation (apply allowance on top)
             const remaining_qty = modal_data.value.colours[colour].values[size]?.[inputTypeInfo.remaining_key] ??
                                   modal_data.value.colours[colour].values[size]?.[inputTypeInfo.base_key] ?? 0;
             const allowance_pct = allowances.value[inputTypeInfo.input_key] || 0;
             const allowed_remaining = remaining_qty * (1 + allowance_pct / 100);

             if (entered_qty > allowed_remaining) {
                 frappe.throw(`Entered quantity cannot be greater than remaining ${inputTypeInfo.display}`);
                 validation_failed = true;
                 return;
             }
        }
    }

    const payload = {
        lot: active_lot.value,
        plan: active_plan.value,
        date: date_control?.get_value() || entry_form.value.date,
        time: time_control?.get_value() || entry_form.value.time,
        work_station: ws_control?.get_value() || entry_form.value.work_station,
        input_type: type_control?.get_value() || entry_form.value.input_type,
        grn_item_type: grn_type_control?.get_value() || entry_form.value.grn_item_type,
        quantities: modal_data.value
    }
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.submit_data_entry_log",
        args: {
             payload: payload
        },
        callback: (r) => {
            if (r.message) {
                frappe.show_alert({
                    message: __('Production entry logged successfully'),
                    indicator: 'green'
                })
                closeModal()
                emit('refresh')
            }
        }
    })
}

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

const fetchData = () => {
    if (!props.selected_supplier) {
        items.value = []
        return
    }
    frappe.call({
        method: "production_api.production_api.doctype.sewing_plan.sewing_plan.get_data_entry_data",
        args: {
            supplier: props.selected_supplier,
            lot: selected_lot.value
        },
        callback: (r) => {
            items.value = r.message.data || []
            diff.value = r.message.diff
            allowances.value = r.message.allowances || {}
            inspection_type.value = r.message.inspection_type
            selected_inspection_type.value = r.message.inspection_type
        }
    })
}

watch(() => [props.selected_supplier, props.refresh_counter, selected_lot.value], fetchData, { immediate: true })
</script>

<style scoped>
@import "../SewingPlan.css";

.data-entry-tab {
    padding: 1rem 0;
}

/* Lot Section Styling */
.lot-section {
    margin-bottom: 10px;
}

.lot-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding-left: 0.25rem;
}

.lot-accent-dot {
    width: 0.6rem;
    height: 0.6rem;
    background-color: var(--primary, #1a73e8);
    border-radius: 50%;
}

.lot-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #111827;
    margin: 0;
}

/* Plan Card Styling */
.plan-card {
    background: white;
    border-radius: 1.5rem;
    padding: 10px;
    border: 1px solid #f1f5f9;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.04);
}

.plan-header {
    margin-bottom: 10px;
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
    font-size: 1rem;
    font-weight: 600;
    color: #334155;
    margin: 0;
}

/* Empty State */
.empty-entry {
    padding: 6rem 2rem;
    text-align: center;
}

.empty-visual {
    width: 4rem;
    height: 4rem;
    background: #f8fafc;
    border-radius: 1.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1.5rem;
    border: 1px solid #f1f5f9;
}

/* Modal Styling */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 900;
    padding: 2rem;
}

.modal-content {
    background: white;
    width: 100%;
    max-width: 1200px;
    max-height: 90vh;
    border-radius: 2rem;
    display: flex;
    flex-direction: column;
    box-shadow: 0 50px 100px -20px rgba(0, 0, 0, 0.25);
    overflow-y: auto;
}

.modal-header {
    padding: 2rem 2.5rem;
    border-bottom: 1px solid #f1f5f9;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.modal-subtitle {
    font-size: 0.75rem;
    font-weight: 500;
    color: #94a3b8;
    display: block;
    margin-bottom: 0.5rem;
}

.modal-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
}

.close-btn {
    padding: 0.5rem;
    color: #94a3b8;
    background: transparent;
    border: none;
    cursor: pointer;
    transition: color 0.2s;
}

.close-btn:hover {
    color: #64748b;
}

.close-icon {
    width: 1.5rem;
    height: 1.5rem;
}

.modal-body {
    padding: 10px;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
    margin-bottom: 20px;
    padding: 10px;
}

.form-grid :deep(.frappe-control) {
    margin-bottom: 0 !important;
}

.form-grid :deep(.control-label) {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #64748b !important;
    margin-bottom: 0.5rem !important;
}

.matrix-container {
    background: #f8fafc;
    border-radius: 1.5rem;
    padding: 15px;
    border: 1px solid #f1f5f9;
}

.matrix-header {
    margin-bottom: 1.5rem;
}

.section-title {
    font-size: 1rem;
    font-weight: 600;
    color: #1e293b;
    margin: 0 0 0.4rem 0;
}

.section-desc {
    font-size: 0.875rem;
    color: #64748b;
    font-weight: 400;
    margin: 0;
}

.modal-table-wrapper {
    overflow-x: auto;
    border-radius: 0.85rem;
    border: 1px solid #e2e8f0;
    background: white;
}

.modal-table {
    width: 100%;
    border-collapse: collapse;
}

.modal-table th {
    background: transparent;
    padding: 8px;
    font-size: 0.75rem;
    font-weight: 700;
    color: #475569;
    border: 1px solid #e2e8f0;
}

.modal-table td {
    padding: 3px;
    border: 1px solid #e2e8f0;
}

.colour-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: #1e293b;
    background: #fdfdfd;
    vertical-align: middle;
    text-align: center;
    padding: 8px !important;
}

.colour-checkbox-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
}

.fill-checkbox {
    width: 16px;
    height: 16px;
    cursor: pointer;
    accent-color: #1a73e8;
}

.qty-input {
    width: 100%;
    min-width: 60px;
    padding: 0.5rem;
    border: 1px solid transparent;
    border-radius: 0.5rem;
    text-align: center;
    font-weight: 500;
    font-size: 0.875rem;
    transition: all 0.2s;
}

.qty-input:focus {
    outline: none;
    background: #eff6ff;
    border-color: #3b82f6;
    color: #1d4ed8;
}

.qty-input::-webkit-inner-spin-button {
    display: none;
}

.total-cell-bold {
    font-weight: 700;
    color: #1e293b;
    text-align: center;
    background: #f8fafc;
}

.modal-footer {
    padding: 1.5rem 2.5rem;
    border-top: 1px solid #f1f5f9;
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    background: #fcfcfd;
}

.cancel-btn {
    padding: 0.75rem 1.5rem;
    border: 1px solid #e2e8f0;
    background: white;
    border-radius: 0.85rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
}

.cancel-btn:hover {
    background: #f8fafc;
    color: #334155;
}

.submit-btn {
    padding: 0.75rem 2rem;
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 0.85rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 10px 20px -5px rgba(26, 115, 232, 0.3);
}

.submit-btn:hover {
    background: #1557b0;
    transform: translateY(-1px);
    box-shadow: 0 15px 25px -5px rgba(26, 115, 232, 0.4);
}

.action-buttons {
    display: flex;
    gap: 0.75rem;
    align-items: center;
}

.update-btn {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 1.25rem;
    background: #ffffff;
    color: #1a73e8;
    border: 1px solid #1a73e8;
    border-radius: 0.85rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.update-btn:hover {
    background: #f8fafc;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(26, 115, 232, 0.1);
}

.update-icon {
    width: 1rem;
    height: 1rem;
}

.update-table-wrapper {
    margin-top: 1rem;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    overflow: hidden;
}

.update-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}

.update-table th {
    background: #f8fafc;
    padding: 12px 1rem;
    text-align: left;
    font-size: 0.75rem;
    font-weight: 700;
    color: #475569;
    border-bottom: 2px solid #e2e8f0;
}

.update-table td {
    padding: 12px 1rem;
    border-bottom: 1px solid #f1f5f9;
    font-size: 0.875rem;
    color: #334155;
}

.checkbox-col, .checkbox-cell {
    width: 50px;
    text-align: center !important;
}

.update-table tr:hover td {
    background: #f8fafc;
}

.update-modal {
    max-width: 600px !important;
}

.inspection-controls-wrapper {
    display: flex;
    gap: 1.5rem;
    align-items: flex-end;
    margin-bottom: 1.5rem;
    padding: 0 1rem;
}

.inspection-select-wrapper {
    flex: 1;
}

.inspection-label {
    display: block;
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    margin-bottom: 0.5rem;
}

.inspection-select {
    width: 100%;
    padding: 0.75rem 1rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: #334155;
    cursor: pointer;
    transition: all 0.2s;
}

.inspection-select:focus {
    outline: none;
    background: white;
    border-color: #1a73e8;
    box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.1);
}

.inspection-select:hover {
    border-color: #cbd5e1;
}

.cancel-checkbox-wrapper {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 0.75rem;
    transition: all 0.2s;
}

.cancel-checkbox-wrapper:hover {
    background: #fee2e2;
    border-color: #fca5a5;
}

.cancel-checkbox {
    width: 18px;
    height: 18px;
    cursor: pointer;
    accent-color: #ef4444;
}

.cancel-checkbox-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: #991b1b;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}
</style>
