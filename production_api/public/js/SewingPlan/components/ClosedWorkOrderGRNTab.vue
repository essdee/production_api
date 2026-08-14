<template>
    <div class="closed-wo-grn-tab">
        <div class="filter-card">
            <div class="filter-copy">
                <h3>Closed Work Order GRN</h3>
                <p>Select a closed Work Order for the chosen warehouse and create its GRN.</p>
            </div>
            <div ref="work_order_wrapper" class="work-order-control"></div>
            <button
                class="btn btn-primary create-button"
                :disabled="!selected_work_order || loading"
                @click="openGRNDialog"
            >
                {{ loading ? 'Loading...' : 'Create GRN' }}
            </button>
        </div>

        <div class="notice-card">
            <div class="notice-icon">i</div>
            <div>
                <strong>Closed Work Orders only</strong>
                <p>
                    Material stock was already adjusted while closing the Work Order.
                    This GRN receives the finished items without consuming those materials again.
                </p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
    selected_supplier: {
        type: String,
        default: null,
    },
    refresh_counter: {
        type: Number,
        default: 0,
    },
})

const work_order_wrapper = ref(null)
const selected_work_order = ref(null)
const loading = ref(false)
let workOrderControl = null

const callServer = (method, args, freeze = false, freezeMessage = null) => {
    return new Promise((resolve, reject) => {
        frappe.call({
            method,
            args,
            freeze,
            freeze_message: freezeMessage,
            callback: (response) => resolve(response.message),
            error: (error) => reject(error),
        })
    })
}

const initializeWorkOrderControl = () => {
    if (!work_order_wrapper.value || workOrderControl) return

    workOrderControl = frappe.ui.form.make_control({
        parent: $(work_order_wrapper.value),
        df: {
            fieldtype: 'Link',
            fieldname: 'closed_work_order',
            label: 'Work Order',
            options: 'Work Order',
            placeholder: 'Select a closed Work Order',
            get_query: () => ({
                query: 'production_api.production_api.page.sewing_details.sewing_details.get_closed_sewing_work_orders',
                filters: {
                    supplier: props.selected_supplier,
                },
            }),
            change: () => {
                selected_work_order.value = workOrderControl.get_value() || null
            },
        },
        render_input: true,
    })
}

const resetWorkOrder = () => {
    selected_work_order.value = null
    if (workOrderControl) {
        workOrderControl.set_value('')
    }
}

const showCreatedMessage = (name) => {
    const safeName = frappe.utils.escape_html(name)
    frappe.msgprint({
        title: 'GRN Created',
        indicator: 'green',
        message: `Goods Received Note <a href="/app/goods-received-note/${encodeURIComponent(name)}"><b>${safeName}</b></a> was created and submitted.`,
    })
}

const hasReceivedQuantity = (itemDetails) => {
    return (itemDetails || []).some((group) => {
        return (group.items || []).some((item) => {
            return Object.values(item.values || {}).some((value) => {
                let receivedTypes = value.types || {}
                if (typeof receivedTypes === 'string') {
                    receivedTypes = JSON.parse(receivedTypes || '{}')
                }
                return Object.values(receivedTypes).some((quantity) => flt(quantity) > 0)
            })
        })
    })
}

const openCalculateDialog = async (details, itemEditor) => {
    const calculationItems = await callServer(
        'production_api.production_api.page.sewing_details.sewing_details.get_closed_work_order_calculation_items',
        {
            work_order: details.work_order,
            supplier: props.selected_supplier,
        },
        true,
        'Fetching Work Order calculation items...'
    )

    if (!calculationItems || !calculationItems.length) {
        frappe.msgprint('No calculated Work Order items are available.')
        return
    }

    let calculationEditor = null
    const calculationDialog = new frappe.ui.Dialog({
        title: `Calculate Receivables - ${details.work_order}`,
        size: 'extra-large',
        fields: [
            {
                fieldname: 'received_type',
                fieldtype: 'Link',
                options: 'GRN Item Type',
                label: 'Received Type',
                reqd: 1,
            },
            {
                fieldname: 'calculated_items_html',
                fieldtype: 'HTML',
            },
        ],
        primary_action_label: 'Calculate',
        primary_action: async (values) => {
            calculationDialog.disable_primary_action()
            try {
                const currentItemDetails = itemEditor.get_items()[0]
                const enteredCalculationItems = calculationEditor.get_work_order_items()
                const updatedItemDetails = await callServer(
                    'production_api.production_api.page.sewing_details.sewing_details.calculate_closed_work_order_receivables',
                    {
                        work_order: details.work_order,
                        supplier: props.selected_supplier,
                        calculation_items: enteredCalculationItems,
                        item_details: currentItemDetails,
                        received_type: values.received_type,
                    },
                    true,
                    'Calculating receivables...'
                )
                itemEditor.load_data({ items: updatedItemDetails }, true)
                calculationDialog.hide()
                frappe.show_alert({ message: 'Receivables calculated', indicator: 'green' })
            } finally {
                calculationDialog.enable_primary_action()
            }
        },
    })

    calculationEditor = new frappe.production.ui.WorkOrderItemView(
        calculationDialog.fields_dict.calculated_items_html.wrapper
    )
    calculationEditor.load_data(calculationItems)
    calculationEditor.create_input_attributes()
    calculationDialog.$wrapper.on('hidden.bs.modal', () => {
        if (calculationEditor) {
            calculationEditor.destroy()
            calculationEditor = null
        }
    })
    calculationDialog.show()
}

const openGRNDialog = async () => {
    if (!props.selected_supplier || !selected_work_order.value || loading.value) return

    loading.value = true
    try {
        const details = await callServer(
            'production_api.production_api.page.sewing_details.sewing_details.get_closed_work_order_grn_details',
            {
                work_order: selected_work_order.value,
                supplier: props.selected_supplier,
            },
            true,
            'Fetching closed Work Order details...'
        )

        if (!details.has_pending_items || !details.item_details?.length) {
            frappe.msgprint({
                title: 'Nothing Pending',
                indicator: 'orange',
                message: 'This Work Order has no pending receivable quantity.',
            })
            return
        }

        const today = frappe.datetime.get_today()
        let itemEditor = null
        const dialog = new frappe.ui.Dialog({
            title: `Create GRN - ${details.work_order}`,
            size: 'extra-large',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'work_order_summary',
                    options: `
                        <div class="closed-wo-summary">
                            <span><b>Work Order:</b> ${frappe.utils.escape_html(details.work_order)}</span>
                            <span><b>Unit:</b> ${frappe.utils.escape_html(details.supplier || '-')}</span>
                            <span><b>Item:</b> ${frappe.utils.escape_html(details.item || '-')}</span>
                            <span><b>Lot:</b> ${frappe.utils.escape_html(details.lot || '-')}</span>
                            <span><b>Process:</b> ${frappe.utils.escape_html(details.process || '-')}</span>
                        </div>
                    `,
                },
                {
                    fieldtype: 'Section Break',
                    label: 'GRN Details',
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'posting_date',
                    label: 'Posting Date',
                    default: today,
                    reqd: 1,
                },
                {
                    fieldtype: 'Time',
                    fieldname: 'posting_time',
                    label: 'Posting Time',
                    default: frappe.datetime.now_time(),
                    reqd: 1,
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'delivery_date',
                    label: 'Delivery Date',
                    default: today,
                    reqd: 1,
                },
                {
                    fieldtype: 'Column Break',
                },
                {
                    fieldtype: 'Data',
                    fieldname: 'supplier_document_no',
                    label: 'Supplier Document Number',
                    reqd: 1,
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'supplier_document_date',
                    label: 'Supplier Document Date',
                    default: today,
                },
                {
                    fieldtype: 'Data',
                    fieldname: 'vehicle_no',
                    label: 'Vehicle Number',
                    reqd: 1,
                },
                {
                    fieldtype: 'Section Break',
                    label: 'Received Items',
                },
                {
                    fieldtype: 'Button',
                    fieldname: 'calculate_receivables',
                    label: 'Calculate',
                    click: () => openCalculateDialog(details, itemEditor),
                },
                {
                    fieldtype: 'HTML',
                    fieldname: 'item_editor',
                },
                {
                    fieldtype: 'Section Break',
                },
                {
                    fieldtype: 'Data',
                    fieldname: 'dc_no',
                    label: 'DC No',
                },
                {
                    fieldtype: 'Column Break',
                },
                {
                    fieldtype: 'Small Text',
                    fieldname: 'comments',
                    label: 'Comments',
                },
            ],
            primary_action_label: 'Create & Submit GRN',
            primary_action: async (values) => {
                const itemDetails = itemEditor.get_items()[0]
                if (!hasReceivedQuantity(itemDetails)) {
                    frappe.msgprint('Enter a received quantity for at least one item.')
                    return
                }

                dialog.disable_primary_action()
                try {
                    const headerValues = {
                        posting_date: values.posting_date,
                        posting_time: values.posting_time,
                        delivery_date: values.delivery_date,
                        supplier_document_no: values.supplier_document_no,
                        supplier_document_date: values.supplier_document_date,
                        vehicle_no: values.vehicle_no,
                        dc_no: values.dc_no,
                        comments: values.comments,
                    }
                    const result = await callServer(
                        'production_api.production_api.page.sewing_details.sewing_details.create_closed_work_order_grn',
                        {
                            work_order: details.work_order,
                            supplier: props.selected_supplier,
                            values: headerValues,
                            item_details: itemDetails,
                        },
                        true,
                        'Creating and submitting GRN...'
                    )
                    dialog.hide()
                    resetWorkOrder()
                    showCreatedMessage(result.name)
                } finally {
                    dialog.enable_primary_action()
                }
            },
        })

        dialog.show()
        itemEditor = new frappe.production.ui.GRNWorkOrder(
            dialog.fields_dict.item_editor.wrapper
        )
        itemEditor.load_data(
            {
                supplier: details.supplier,
                against: 'Work Order',
                against_id: details.work_order,
                docstatus: 0,
                items: details.item_details,
            },
            true
        )
        dialog.$wrapper.on('hidden.bs.modal', () => {
            if (itemEditor) {
                itemEditor.destroy()
                itemEditor = null
            }
        })
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    nextTick(initializeWorkOrderControl)
})

watch(
    () => props.selected_supplier,
    () => resetWorkOrder()
)

watch(
    () => props.refresh_counter,
    () => resetWorkOrder()
)
</script>

<style scoped>
.closed-wo-grn-tab {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.filter-card {
    display: grid;
    grid-template-columns: minmax(240px, 1fr) minmax(280px, 420px) auto;
    gap: 1.25rem;
    align-items: end;
    padding: 1.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    background: #fff;
}

.filter-copy h3 {
    margin: 0 0 0.35rem;
    color: #111827;
    font-size: 1.1rem;
    font-weight: 600;
}

.filter-copy p,
.notice-card p {
    margin: 0;
    color: #6b7280;
    line-height: 1.5;
}

.work-order-control {
    min-width: 0;
}

.create-button {
    min-height: 38px;
    white-space: nowrap;
}

.notice-card {
    display: flex;
    gap: 0.8rem;
    padding: 1rem 1.25rem;
    border: 1px solid #bfdbfe;
    border-radius: 0.75rem;
    background: #eff6ff;
    color: #1e3a8a;
}

.notice-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 24px;
    width: 24px;
    height: 24px;
    border-radius: 999px;
    background: #2563eb;
    color: white;
    font-weight: 700;
}

.notice-card strong {
    display: block;
    margin-bottom: 0.2rem;
}

@media (max-width: 900px) {
    .filter-card {
        grid-template-columns: 1fr;
        align-items: stretch;
    }
}

:global(.closed-wo-summary) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1.5rem;
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    background: #f3f4f6;
}
</style>
