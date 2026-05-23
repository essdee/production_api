<template>
    <div class="duplicate-po-item-table">
        <table v-if="rows.length" class="table table-bordered table-sm align-middle">
            <thead>
                <tr>
                    <th style="width: 40px;">S.No.</th>
                    <th>Item</th>
                    <th>Lot</th>
                    <th v-for="attr in attribute_columns" :key="attr">{{ attr }}</th>
                    <th>Qty</th>
                    <th>Delivery Date</th>
                    <th>Expected Delivery Date</th>
                    <th style="width: 90px;">Actions</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="(row, idx) in rows" :key="row._uid">
                    <td>{{ idx + 1 }}</td>

                    <td v-if="!row._editing">{{ row.item }}</td>
                    <td v-else><div class="cell-control" :ref="(el) => bind_cell(el, row, 'item')"></div></td>

                    <td v-if="!row._editing">{{ row.lot }}</td>
                    <td v-else><div class="cell-control" :ref="(el) => bind_cell(el, row, 'lot')"></div></td>

                    <td v-for="attr in attribute_columns" :key="attr">
                        <template v-if="!row._editing">
                            <span v-if="row.attributes && row.attributes[attr]">{{ row.attributes[attr] }}</span>
                            <span v-else class="text-muted">—</span>
                        </template>
                        <template v-else>
                            <div
                                v-if="(row._attribute_names || []).includes(attr)"
                                class="cell-control"
                                :ref="(el) => bind_cell(el, row, 'attr:' + attr)"
                            ></div>
                            <span v-else class="text-muted">—</span>
                        </template>
                    </td>

                    <td v-if="!row._editing">
                        {{ row.qty }}<span v-if="row.uom"> {{ row.uom }}</span>
                    </td>
                    <td v-else>
                        <input class="form-control input-sm" type="number" step="any" v-model.number="row.qty">
                    </td>

                    <td v-if="!row._editing">{{ row.delivery_date }}</td>
                    <td v-else><div class="cell-control" :ref="(el) => bind_cell(el, row, 'delivery_date')"></div></td>

                    <td v-if="!row._editing">{{ row.expected_delivery_date }}</td>
                    <td v-else><div class="cell-control" :ref="(el) => bind_cell(el, row, 'expected_delivery_date')"></div></td>

                    <td>
                        <template v-if="!row._editing">
                            <span class="cursor-pointer mr-2" title="Edit" @click="enter_edit(row)" v-html="frappe.utils.icon('edit', 'sm')"></span>
                            <span class="cursor-pointer text-danger" title="Delete" @click="remove_row(row)" v-html="frappe.utils.icon('delete', 'sm')"></span>
                        </template>
                        <template v-else>
                            <button class="btn btn-xs btn-primary mr-1" @click="save_edit(row)">Done</button>
                            <button class="btn btn-xs btn-default" @click="cancel_edit(row)">Cancel</button>
                        </template>
                    </td>
                </tr>
            </tbody>
        </table>
        <div v-else class="text-muted text-center py-4">No items.</div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const rows = ref([]);
let _uid_seq = 0;
const _controls = {}; // _controls[row._uid][field] = frappe control

const attribute_columns = computed(() => {
    const seen = new Set();
    const ordered = [];
    for (const r of rows.value) {
        const names = r._attribute_names || [];
        for (const a of names) {
            if (!seen.has(a)) {
                seen.add(a);
                ordered.push(a);
            }
        }
    }
    return ordered;
});

function load_data(new_rows) {
    rows.value = (new_rows || []).map((r) => {
        if (!r._uid) r._uid = ++_uid_seq;
        r._editing = false;
        r.attributes = r.attributes || {};
        r._attribute_names = r._attribute_names || Object.keys(r.attributes);
        return r;
    });
}

function bind_cell(el, row, field) {
    const uid = row._uid;
    if (!el) {
        if (_controls[uid] && _controls[uid][field]) {
            delete _controls[uid][field];
        }
        return;
    }
    if (_controls[uid] && _controls[uid][field]) return;
    _controls[uid] = _controls[uid] || {};

    let ctrl;
    if (field === 'item') {
        ctrl = frappe.ui.form.make_control({
            parent: $(el),
            df: {
                fieldtype: 'Link',
                options: 'Item',
                label: '',
                fieldname: 'item',
                onchange() {
                    const v = ctrl.get_value() || '';
                    if (v === row.item) return;
                    row.item = v;
                    if (v) refetch_attributes(row);
                },
            },
            render_input: true,
        });
        ctrl.set_value(row.item || '');
    } else if (field === 'lot') {
        ctrl = frappe.ui.form.make_control({
            parent: $(el),
            df: {
                fieldtype: 'Link',
                options: 'Lot',
                label: '',
                fieldname: 'lot',
            },
            render_input: true,
        });
        ctrl.set_value(row.lot || '');
    } else if (field === 'delivery_date' || field === 'expected_delivery_date') {
        ctrl = frappe.ui.form.make_control({
            parent: $(el),
            df: {
                fieldtype: 'Date',
                label: '',
                fieldname: field,
            },
            render_input: true,
        });
        ctrl.set_value(row[field] || '');
    } else if (field.startsWith('attr:')) {
        const attr_name = field.slice(5);
        ctrl = frappe.ui.form.make_control({
            parent: $(el),
            df: {
                fieldtype: 'Link',
                options: 'Item Attribute Value',
                label: '',
                fieldname: attr_name,
                only_select: true,
                get_query: () => ({
                    query: 'production_api.production_api.doctype.item.item.get_item_attribute_values',
                    filters: { item: row.item, attribute: attr_name },
                }),
            },
            render_input: true,
        });
        ctrl.set_value((row.attributes && row.attributes[attr_name]) || '');
    }
    if (ctrl) _controls[uid][field] = ctrl;
}

function refetch_attributes(row) {
    frappe.call({
        method: 'production_api.production_api.doctype.item.item.get_attribute_details',
        args: { item_name: row.item },
        callback(r) {
            if (!r.message) return;
            const new_attrs = r.message.attributes || [];
            row._attribute_names = new_attrs;
            const merged = {};
            for (const a of new_attrs) merged[a] = (row.attributes && row.attributes[a]) || '';
            row.attributes = merged;
            row.uom = row.uom || r.message.default_uom || '';
            row.secondary_uom = row.secondary_uom || r.message.secondary_uom || '';
            // controls for attribute fields will re-bind on next render (their <td> v-if changes when _attribute_names changes)
            // existing attribute controls whose name still applies stay bound and reflect updated row.attributes
            const uid = row._uid;
            const ctrls = _controls[uid] || {};
            for (const k of Object.keys(ctrls)) {
                if (!k.startsWith('attr:')) continue;
                const a = k.slice(5);
                if (!new_attrs.includes(a)) {
                    delete ctrls[k];
                } else {
                    ctrls[k].set_value(merged[a] || '');
                }
            }
        },
    });
}

function enter_edit(row) {
    row._backup = {
        item: row.item,
        lot: row.lot,
        qty: row.qty,
        delivery_date: row.delivery_date,
        expected_delivery_date: row.expected_delivery_date,
        attributes: JSON.parse(JSON.stringify(row.attributes || {})),
        _attribute_names: (row._attribute_names || []).slice(),
        uom: row.uom,
        secondary_uom: row.secondary_uom,
    };
    row._editing = true;
}

function save_edit(row) {
    const uid = row._uid;
    const ctrls = _controls[uid] || {};
    if (ctrls.item) row.item = ctrls.item.get_value() || '';
    if (ctrls.lot) row.lot = ctrls.lot.get_value() || '';
    if (ctrls.delivery_date) row.delivery_date = ctrls.delivery_date.get_value() || '';
    if (ctrls.expected_delivery_date) row.expected_delivery_date = ctrls.expected_delivery_date.get_value() || '';
    row.attributes = row.attributes || {};
    for (const k of Object.keys(ctrls)) {
        if (k.startsWith('attr:')) {
            const a = k.slice(5);
            row.attributes[a] = ctrls[k].get_value() || '';
        }
    }
    delete _controls[uid];
    row._editing = false;
    delete row._backup;
}

function cancel_edit(row) {
    if (row._backup) {
        row.item = row._backup.item;
        row.lot = row._backup.lot;
        row.qty = row._backup.qty;
        row.delivery_date = row._backup.delivery_date;
        row.expected_delivery_date = row._backup.expected_delivery_date;
        row.attributes = row._backup.attributes;
        row._attribute_names = row._backup._attribute_names;
        row.uom = row._backup.uom;
        row.secondary_uom = row._backup.secondary_uom;
        delete row._backup;
    }
    delete _controls[row._uid];
    row._editing = false;
}

function remove_row(row) {
    delete _controls[row._uid];
    const idx = rows.value.indexOf(row);
    if (idx >= 0) rows.value.splice(idx, 1);
}

defineExpose({ rows, load_data });
</script>

<style scoped>
.cell-control {
    min-width: 140px;
}
.duplicate-po-item-table .table {
    margin-bottom: 0;
}
.cursor-pointer {
    cursor: pointer;
}
</style>
