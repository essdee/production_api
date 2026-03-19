<template>
    <div ref="root" class="rework-container">
        <h3 style="font-weight:700;margin-bottom:15px;color:#333;text-align:center;">Rework Group Details</h3>
        <div class="input-row">
            <div class="lot-input col-md-2"></div>
            <div class="item-input col-md-2"></div>
            <div class="colour-input col-md-2"></div>
            <div class="show-reworked-input col-md-2"></div>
            <div class="btn-wrapper">
                <button class="btn btn-primary" @click="get_rework_items()">Get Rework Items</button>
            </div>
        </div>

        <template v-if="groups && Object.keys(groups).length > 0">
            <div v-for="(group, groupKey) in groups" :key="groupKey" class="group-card">
                <h4 class="group-header">{{ groupKey }}</h4>
                <div class="table-wrapper">
                    <table class="table table-sm table-sm-bordered">
                        <thead>
                            <tr>
                                <th>Colour</th>
                                <th v-if="group.is_set_item">Part</th>
                                <th>GRN Number</th>
                                <th>Received Type</th>
                                <th>Row</th>
                                <th v-for="size in group.sizes" :key="size">{{ size }}</th>
                                <th>Total</th>
                                <th v-if="!show_reworked_value">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template v-for="(row, rowIdx) in group.rows" :key="rowIdx">
                                <!-- Received row -->
                                <tr>
                                    <td :rowspan="show_reworked_value ? 1 : 3">
                                        {{ row.colour }}
                                    </td>
                                    <td v-if="group.is_set_item" :rowspan="show_reworked_value ? 1 : 3" >
                                        {{ row.part }}
                                    </td>
                                    <td :rowspan="show_reworked_value ? 1 : 3">
                                        <div @click="map_to_grn(row.grn_number)" class="hover-style">{{ row.grn_number }}</div>
                                    </td>
                                    <td :rowspan="show_reworked_value ? 1 : 3">
                                        {{ row.received_type }}
                                    </td>
                                    <td>Received</td>
                                    <td v-for="size in group.sizes" :key="size">
                                        {{ row.received[size] || 0 }}
                                    </td>
                                    <td>{{ rowTotal(row.received, group.sizes) }}</td>
                                    <td v-if="!show_reworked_value" :rowspan="3" class="action-cell">
                                        <div class="action-buttons">
                                            <button class="btn btn-primary btn-xs" @click="updateRejection(row)">Update Rejection Qty</button>
                                            <button class="btn btn-primary btn-xs" @click="updateReworked(row, group)">Update Reworked Piece</button>
                                            <button class="btn btn-primary btn-xs" @click="completeRework(row, group, groupKey, rowIdx)">Complete Rework</button>
                                        </div>
                                    </td>
                                </tr>
                                <!-- Rejection row -->
                                <tr v-if="!show_reworked_value">
                                    <td>Rejection</td>
                                    <td v-for="size in group.sizes" :key="size">
                                        <input type="number" v-model.number="row.rejection_input[size]" class="form-control input-sm" />
                                    </td>
                                    <td>{{ rowTotal(row.rejection_input, group.sizes) }}</td>
                                </tr>
                                <!-- Reworked row -->
                                <tr v-if="!show_reworked_value">
                                    <td>Reworked</td>
                                    <td v-for="size in group.sizes" :key="size">
                                        <input type="number" v-model.number="row.rework_input[size]" class="form-control input-sm" />
                                    </td>
                                    <td>{{ rowTotal(row.rework_input, group.sizes) }}</td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>
        </template>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

let lot_ctrl = null;
let item_ctrl = null;
let colour_ctrl = null;
let show_reworked_ctrl = null;

let root = ref(null);
let sample_doc = ref({});
let groups = ref({});
let show_reworked_value = ref(false);

onMounted(() => {
    let el = root.value;

    $(el).find(".lot-input").html("");
    lot_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".lot-input"),
        df: { fieldname: "lot", fieldtype: "Link", options: "Lot", label: "Lot" },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".item-input").html("");
    item_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: { fieldname: "item", fieldtype: "Link", options: "Item", label: "Item" },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".colour-input").html("");
    colour_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".colour-input"),
        df: { fieldname: "colour", fieldtype: "Data", label: "Colour" },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".show-reworked-input").html("");
    show_reworked_ctrl = frappe.ui.form.make_control({
        parent: $(el).find(".show-reworked-input"),
        df: { fieldname: "show_reworked", fieldtype: "Check", label: "Show Reworked" },
        doc: sample_doc.value,
        render_input: true,
        change() {
            show_reworked_value.value = !!show_reworked_ctrl.get_value();
        }
    });
});

function get_rework_items() {
    frappe.call({
        method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.get_rework_group_items",
        freeze: true,
        freeze_message: "Loading Rework Group Items...",
        args: {
            lot: lot_ctrl.get_value(),
            item: item_ctrl.get_value(),
            colour: colour_ctrl.get_value(),
            show_reworked: show_reworked_ctrl.get_value() ? 1 : 0,
        },
        callback: function (r) {
            if (r.message && r.message.groups) {
                let raw = r.message.groups;
                // Initialize input fields for each row
                for (let gk in raw) {
                    for (let row of raw[gk].rows) {
                        row.rejection_input = {};
                        row.rework_input = {};
                        for (let size of raw[gk].sizes) {
                            row.rejection_input[size] = row.rejection[size] || 0;
                            row.rework_input[size] = 0;
                        }
                    }
                }
                groups.value = raw;
            }
        },
    });
}

function rowTotal(sizeMap, sizes) {
    let total = 0;
    for (let s of sizes) {
        total += (sizeMap[s] || 0);
    }
    return total;
}

function map_to_grn(grn) {
    window.open(`/app/goods-received-note/${grn}`, '_blank');
}

function buildItemsPayload(row, mode) {
    // mode: 'rejection' | 'rework' | 'complete'
    let items = [];
    for (let item of row.items) {
        let entry = Object.assign({}, item);
        if (mode === 'rejection' || mode === 'complete') {
            let size = entry[Object.keys(entry).find(k => !['rework_qty','reworked_qty','rejected','rework','set_combination','row_name','variant','received_type','uom'].includes(k))];
            // Find the size key from the item
            entry.rejected = row.rejection_input[size] !== undefined ? row.rejection_input[size] : entry.rejected;
        }
        if (mode === 'rework') {
            let sizeKey = Object.keys(entry).find(k => !['rework_qty','reworked_qty','rejected','rework','set_combination','row_name','variant','received_type','uom'].includes(k));
            let size = entry[sizeKey];
            entry.rework = row.rework_input[size] !== undefined ? row.rework_input[size] : 0;
        }
        items.push(entry);
    }
    return items;
}

function getLot(row) {
    // Extract lot from the items — items have set_combination but not lot directly
    // We need to find the lot from the parent doc; it's stored in row.lot
    return row.lot;
}

function updateRejection(row) {
    let data = buildItemsPayload(row, 'rejection');
    let hasChange = data.some(d => d.rejected > 0);
    if (!hasChange) {
        frappe.msgprint("There is nothing was changed in this row");
        return;
    }
    frappe.call({
        method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.update_rejected_quantity",
        args: {
            rejection_data: data,
            completed: 0,
            lot: getLot(row),
        },
        callback: function() {
            frappe.show_alert({ message: __("Rejection Quantity Updated"), indicator: "info" });
        }
    });
}

function updateReworked(row, group) {
    let data = buildItemsPayload(row, 'rework');
    let hasChange = data.some(d => d.rework > 0);
    if (!hasChange) {
        frappe.msgprint("No reworked quantities entered");
        return;
    }
    let d = new frappe.ui.Dialog({
        title: "Are you sure want to convert to reworked",
        primary_action_label: "Yes",
        secondary_action_label: "No",
        primary_action() {
            frappe.call({
                method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.update_partial_quantity",
                args: { data: data, lot: getLot(row) },
                callback: function() {
                    frappe.show_alert({ message: __("Reworked Quantity Updated"), indicator: "info" });
                    get_rework_items();
                }
            });
            d.hide();
        },
        secondary_action() { d.hide(); }
    });
    d.show();
}

function completeRework(row, group, groupKey, rowIdx) {
    let data = buildItemsPayload(row, 'complete');
    let d = new frappe.ui.Dialog({
        title: "Are you sure want to final the item",
        primary_action_label: "Yes",
        secondary_action_label: "No",
        primary_action() {
            frappe.call({
                method: "production_api.production_api.doctype.grn_rework_item.grn_rework_item.update_rejected_quantity",
                args: {
                    rejection_data: data,
                    completed: 1,
                    lot: getLot(row),
                },
                callback: function() {
                    frappe.show_alert({ message: __("Rework Completed"), indicator: "info" });
                    // Remove the row from the group
                    group.rows.splice(rowIdx, 1);
                    if (group.rows.length === 0) {
                        delete groups.value[groupKey];
                    }
                }
            });
            d.hide();
        },
        secondary_action() { d.hide(); }
    });
    d.show();
}
</script>

<style scoped>
.rework-container {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 24px;
}

.input-row {
    display: flex;
    align-items: center;
    gap: 12px;
}

.btn-wrapper {
    padding-top: 27px;
}

.group-card {
    margin-top: 24px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

.group-header {
    background-color: #e9ecef;
    padding: 14px 20px;
    margin: 0;
    font-weight: 700;
    font-size: 17px;
    color: #333;
    border-bottom: 1px solid #dee2e6;
}

.table-wrapper {
    overflow-x: clip;
}

.table-sm-bordered {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin-bottom: 0;
}

.table-sm-bordered th,
.table-sm-bordered td {
    border: 1px solid #dee2e6;
    padding: 10px 14px;
    font-size: 15px;
    vertical-align: middle !important;
}

.table-sm-bordered thead th {
    background-color: #f1f3f5;
    font-weight: 700;
    font-size: 15px;
    color: #495057;
    position: sticky;
    top: var(--navbar-height);
    z-index: 11;
}

.action-cell {
    height: 1px;
    padding: 0 10px !important;
}

.action-buttons {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 10px;
    height: 100%;
}

.action-buttons .btn {
    white-space: nowrap;
}

.form-control.input-sm {
    width: 80px;
    padding: 4px 6px;
    font-size: 14px;
    text-align: center;
}

.btn-primary {
    background-color: #007bff;
    border-color: #007bff;
    padding: 6px 14px;
    border-radius: 5px;
    font-size: 13px;
    transition: all 0.2s ease;
}

.btn-primary:hover {
    background-color: #0069d9;
    border-color: #0062cc;
}

.btn-xs {
    padding: 5px 12px;
    font-size: 13px;
}

.hover-style:hover {
    text-decoration: underline;
    cursor: pointer;
}
</style>
