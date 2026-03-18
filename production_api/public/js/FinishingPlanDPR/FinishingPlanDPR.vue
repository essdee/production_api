<template>
    <div class="dpr-tab">
        <div class="page-title-bar">Finishing Plan DPR</div>
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
                    <div ref="lot_filter_wrapper"></div>
                </div>
                <div class="filter-control">
                    <div ref="item_filter_wrapper"></div>
                </div>
                <div>
                    <button class="btn btn-primary" @click="fetchData()" style="border-radius: 12px; font-weight: 700;">
                        Get Report
                    </button>
                </div>
            </div>
        </div>

        <div v-if="rows.length > 0" ref="report_section">
            <div class="section-header">
                <div class="section-title-block">
                    <span class="section-title">Finishing Packed Details</span>
                    <span class="section-divider">|</span>
                    <span class="section-title">{{ frappe.datetime.str_to_user(selected_date) }}</span>
                </div>
                <div class="section-actions">
                    <button class="copy-btn" @click="copyToClipboard()" :disabled="copying">
                        <template v-if="copying">
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
                        <span class="total-label">Total Boxes</span>
                        <span class="total-value">{{ grandTotalBoxes }}</span>
                    </div>
                    <div class="section-total-block">
                        <span class="total-label">Total Pieces</span>
                        <span class="total-value">{{ grandTotalPieces }}</span>
                    </div>
                </div>
            </div>

            <div v-for="(row, idx) in rows" :key="row.lot" class="table-wrapper no-scrollbar" style="margin-bottom: 24px;">
                <table class="data-table">
                    <thead>
                        <tr class="header-row">
                            <th class="index-col">#</th>
                            <th>Lot</th>
                            <th>Item</th>
                            <th v-for="size in row.sizes" :key="size" class="size-col">{{ size }}</th>
                            <th class="total-col">Total Boxes</th>
                            <th>Pcs/Box</th>
                            <th class="total-col">Total Pieces</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr class="data-row">
                            <td class="index-cell">{{ idx + 1 }}</td>
                            <td class="colour-cell">{{ row.lot }}</td>
                            <td class="colour-cell">{{ row.item }}</td>
                            <td v-for="size in row.sizes" :key="size" class="size-cell">
                                {{ row.size_qty[size] || '' }}
                            </td>
                            <td class="total-cell">
                                <span class="total-val">{{ row.total_boxes }}</span>
                            </td>
                            <td class="size-cell">{{ row.pieces_per_box }}</td>
                            <td class="total-cell">
                                <span class="total-val">{{ row.total_pieces }}</span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div v-else-if="fetched" class="empty-state">
            <p>No Packed Details for this date</p>
        </div>

        <div v-else class="empty-state">
            <p>Select a date and click "Get Report" to view packing details</p>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import * as htmlToImage from 'html-to-image'

const date_filter_wrapper = ref(null)
const lot_filter_wrapper = ref(null)
const item_filter_wrapper = ref(null)
const report_section = ref(null)
let date_filter_control = null
let lot_control = null
let item_control = null
const selected_date = ref(null)
const rows = ref([])
const all_sizes = ref([])
const copying = ref(false)
const fetched = ref(false)

const initFilter = () => {
    if (!date_filter_wrapper.value) return

    $(date_filter_wrapper.value).empty()

    date_filter_control = frappe.ui.form.make_control({
        parent: $(date_filter_wrapper.value),
        df: {
            fieldtype: 'Date',
            fieldname: 'date',
            label: 'Date',
            placeholder: 'Date',
            change: () => {
                selected_date.value = date_filter_control.get_value()
            }
        },
        render_input: true
    })

    if (lot_filter_wrapper.value) {
        $(lot_filter_wrapper.value).empty()
        lot_control = frappe.ui.form.make_control({
            parent: $(lot_filter_wrapper.value),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'lot',
                label: 'Lot',
                options: 'Lot',
                get_data: function(txt) {
                    return frappe.db.get_link_options('Lot', txt)
                },
            },
            render_input: true,
        })
    }

    if (item_filter_wrapper.value) {
        $(item_filter_wrapper.value).empty()
        item_control = frappe.ui.form.make_control({
            parent: $(item_filter_wrapper.value),
            df: {
                fieldtype: 'MultiSelectList',
                fieldname: 'item',
                label: 'Item',
                options: 'Item',
                get_data: function(txt) {
                    return frappe.db.get_link_options('Item', txt)
                },
            },
            render_input: true,
        })
    }
}

const fetchData = () => {
    if (!selected_date.value) {
        frappe.show_alert({ message: 'Please select a date', indicator: 'orange' })
        return
    }
    frappe.call({
        method: 'production_api.production_api.doctype.finishing_plan.finishing_plan.get_finishing_packed_details',
        args: {
            date: selected_date.value,
            lot_list: lot_control ? lot_control.get_value() : [],
            item_list: item_control ? item_control.get_value() : [],
        },
        freeze: true,
        freeze_message: 'Fetching report...',
        callback: (r) => {
            fetched.value = true
            if (r.message) {
                rows.value = r.message.data
                all_sizes.value = r.message.sizes
            }
        }
    })
}

const getSizeTotal = (size) => {
    let total = 0
    for (const row of rows.value) {
        total += row.size_qty[size] || 0
    }
    return total
}

const grandTotalBoxes = computed(() => {
    return rows.value.reduce((sum, row) => sum + (row.total_boxes || 0), 0)
})

const grandTotalPieces = computed(() => {
    return rows.value.reduce((sum, row) => sum + (row.total_pieces || 0), 0)
})

const copyToClipboard = async () => {
    if (!report_section.value) return
    copying.value = true
    try {
        const blob = await htmlToImage.toBlob(report_section.value, {
            backgroundColor: '#ffffff',
            pixelRatio: 1
        })
        await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob })
        ])
        copying.value = false
        frappe.show_alert({ message: 'Copied to clipboard', indicator: 'green' })
    } catch (err) {
        copying.value = false
        frappe.show_alert({ message: 'Copy failed', indicator: 'red' })
    }
}

onMounted(() => {
    initFilter()
})
</script>

<style scoped>
@import "../SewingPlan/SewingPlan.css";

.page-title-bar {
    text-align: center;
    font-size: 1.5rem;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 1rem;
}

.dpr-tab {
    padding: 1rem;
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
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
}

.section-title {
    font-size: 1.125rem;
    font-weight: 700;
    color: #1e293b;
    margin: 0;
    white-space: nowrap;
}

.section-divider {
    color: #cbd5e1;
    font-size: 1.125rem;
    font-weight: 300;
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
</style>
