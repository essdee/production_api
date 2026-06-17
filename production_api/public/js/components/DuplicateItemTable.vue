<template>
    <div class="duplicate-item-table">
        <table v-if="rows.length" class="table table-bordered table-sm align-middle">
            <thead>
                <tr>
                    <th style="width: 40px;">S.No.</th>
                    <th>Item</th>
                    <th>Lot</th>
                    <th v-for="attr in attribute_columns" :key="attr">{{ attr }}</th>
                    <th v-for="col in columns" :key="col.key">{{ col.label }}</th>
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

                    <td v-for="col in columns" :key="col.key">
                        <template v-if="!row._editing">
                            <span v-if="col.type === 'check'" :class="row[col.key] ? 'text-success' : 'text-muted'">
                                {{ row[col.key] ? 'Yes' : 'No' }}
                            </span>
                            <template v-else>
                                <span v-if="row[col.key] !== null && row[col.key] !== undefined && row[col.key] !== ''">{{ row[col.key] }}</span>
                                <span v-else class="text-muted">—</span>
                            </template>
                        </template>
                        <template v-else>
                            <input v-if="col.type === 'number'" class="form-control input-sm" type="number" step="any" v-model.number="row[col.key]">
                            <input v-else-if="col.type === 'check'" type="checkbox" v-model="row[col.key]">
                            <input v-else-if="col.type === 'data'" class="form-control input-sm" type="text" v-model="row[col.key]">
                            <div v-else-if="col.type === 'link'" class="cell-control" :ref="(el) => bind_cell(el, row, 'col:' + col.key)"></div>
                            <span v-else>{{ row[col.key] }}</span>
                        </template>
                    </td>

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

// `columns` describes the editable per-row fields that follow the common
// Item / Lot / attribute columns. Each column: { key, label, type, options? }
// where type is one of 'number' | 'data' | 'check' | 'link'. For 'link',
// `options` is the target DocType.
const props = defineProps({
    columns: { type: Array, default: () => [] },
});

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

function default_for(col) {
    if (col.type === 'check') return false;
    if (col.type === 'number') return 0;
    return '';
}

function load_data(new_rows) {
    rows.value = (new_rows || []).map((r) => {
        if (!r._uid) r._uid = ++_uid_seq;
        r._editing = false;
        r.attributes = r.attributes || {};
        r._attribute_names = r._attribute_names || Object.keys(r.attributes);
        for (const col of props.columns) {
            if (!(col.key in r) || r[col.key] === null || r[col.key] === undefined) {
                r[col.key] = default_for(col);
            }
        }
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
    } else if (field.startsWith('col:')) {
        const key = field.slice(4);
        const col = props.columns.find((c) => c.key === key);
        if (!col) return;
        ctrl = frappe.ui.form.make_control({
            parent: $(el),
            df: {
                fieldtype: 'Link',
                options: col.options,
                label: '',
                fieldname: key,
            },
            render_input: true,
        });
        ctrl.set_value(row[key] || '');
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
    const backup = {
        item: row.item,
        lot: row.lot,
        attributes: JSON.parse(JSON.stringify(row.attributes || {})),
        _attribute_names: (row._attribute_names || []).slice(),
        uom: row.uom,
        secondary_uom: row.secondary_uom,
    };
    for (const col of props.columns) backup[col.key] = row[col.key];
    row._backup = backup;
    row._editing = true;
}

function save_edit(row) {
    const uid = row._uid;
    const ctrls = _controls[uid] || {};
    if (ctrls.item) row.item = ctrls.item.get_value() || '';
    if (ctrls.lot) row.lot = ctrls.lot.get_value() || '';
    row.attributes = row.attributes || {};
    for (const k of Object.keys(ctrls)) {
        if (k.startsWith('attr:')) {
            const a = k.slice(5);
            row.attributes[a] = ctrls[k].get_value() || '';
        } else if (k.startsWith('col:')) {
            const key = k.slice(4);
            row[key] = ctrls[k].get_value() || '';
        }
    }
    // number / data / check columns are bound live via v-model; nothing to pull.
    delete _controls[uid];
    row._editing = false;
    delete row._backup;
}

function cancel_edit(row) {
    if (row._backup) {
        row.item = row._backup.item;
        row.lot = row._backup.lot;
        row.attributes = row._backup.attributes;
        row._attribute_names = row._backup._attribute_names;
        row.uom = row._backup.uom;
        row.secondary_uom = row._backup.secondary_uom;
        for (const col of props.columns) row[col.key] = row._backup[col.key];
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
/* Native inputs (qty/rate/remarks) are Bootstrap form-control (width:100%); give
   them a floor so they don't collapse inside the narrow Qty/Rate columns. */
.duplicate-item-table td input[type="number"].form-control {
    min-width: 80px;
}
.duplicate-item-table td input[type="text"].form-control {
    min-width: 140px;
}
.duplicate-item-table .table {
    margin-bottom: 0;
}
.cursor-pointer {
    cursor: pointer;
}
</style>
