<template>
    <div>
        <div v-if="received_matrix && received_matrix.groups && received_matrix.groups.length > 0" style="margin-bottom:16px;">
            <h3>Received from Other Finishing Plans</h3>
            <MatrixTable :matrix="received_matrix" counterpart-label="Source FP / Lot" />
        </div>
        <div v-if="given_matrix && given_matrix.groups && given_matrix.groups.length > 0" style="margin-bottom:16px;">
            <h3>Given to Other Finishing Plans</h3>
            <MatrixTable :matrix="given_matrix" counterpart-label="Destination FP / Lot" />
        </div>
        <div v-if="lt_list && Object.keys(lt_list).length > 0" style="width:40%;">
            <h3>Lot Transfer List</h3>
            <table class="table table-sm table-sm-bordered bordered-table">
                <thead class="dark-border">
                    <tr>
                        <th>Lot Transfer</th>
                        <th>Date Time</th>
                        <th>Cancel</th>
                    </tr>
                </thead>
                <tbody class="dark-border">
                    <tr v-for="(date, lt) in lt_list">
                        <td style="cursor: pointer;" @click="redirect_to('Lot Transfer', lt)">{{ lt }}</td>
                        <td>{{ date }}</td>
                        <td>
                            <button class="btn btn-primary" @click="cancel_doc('Lot Transfer', lt)">Cancel</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div style="display:flex;">
            <div v-if="show_fetch_button">
                <button class="btn btn-success" @click="fetch_items()">Fetch Items</button>
            </div>
            <div style="padding-left:20px;">
                <button class="btn btn-success" @click="lot_transfer()">Lot Transfer</button>
            </div>
        </div>
        <div style="margin-top:20px;"></div>
        <div v-for="row in items" :key="row.lot" class="old-lot-group">
            <h3>{{ row.lot }} <span class="group-sub">— {{ row.warehouse_name }}</span></h3>
            <table class="table table-sm bordered-table old-lot-table">
                <thead>
                    <tr>
                        <th style="width:36px;">#</th>
                        <th style="width:120px;">Colour</th>
                        <th style="width:150px;">Set Colour</th>
                        <th v-if="row.is_set_item" style="width:90px;">{{ row['set_attr'] }}</th>
                        <th style="width:110px;">Bucket</th>
                        <th v-for="size in row.primary_values" :key="size">{{ size }}</th>
                        <th style="width:60px;">Total</th>
                    </tr>
                </thead>
                <tbody v-for="(colour, idx) in visible_colours(row)" :key="colour">
                    <template v-for="bucket in visible_buckets(row, colour)" :key="bucket.key">
                        <tr :class="{'no-balance-row': bucket.colour_total === 0}">
                            <td v-if="bucket.first" :rowspan="bucket.rowspan">{{ idx + 1 }}</td>
                            <td v-if="bucket.first" :rowspan="bucket.rowspan">
                                <span class="colour-pill">{{ colour }}</span>
                            </td>
                            <td v-if="bucket.first" :rowspan="bucket.rowspan">
                                <select v-model="row['old_lot_inward']['data'][colour]['set_combination']" class="form-control form-control-sm">
                                    <option v-for="opt in colours" :key="opt" :value="opt">{{ opt }}</option>
                                </select>
                            </td>
                            <td v-if="bucket.first && row.is_set_item" :rowspan="bucket.rowspan">
                                <span class="part-pill">{{ row['old_lot_inward']['data'][colour]['part'] }}</span>
                            </td>
                            <td class="bucket-label">
                                <span :class="['bucket-chip', bucket.tone]">{{ bucket.label }}</span>
                            </td>
                            <td v-for="size in row.primary_values" :key="size" class="cell-stack">
                                <div class="cell-wrap" v-if="bucket.balance_of(size) > 0">
                                    <span class="bal-badge">{{ bucket.balance_of(size) }}</span>
                                    <input type="number"
                                        class="form-control form-control-sm transfer-input"
                                        :max="bucket.balance_of(size)"
                                        min="0"
                                        v-model.number="row['old_lot_inward']['data'][colour]['values'][size][bucket.transfer_field]" />
                                </div>
                                <div v-else class="cell-empty">—</div>
                            </td>
                            <td class="totals-cell">
                                <div class="bal-total">{{ bucket.colour_total }}</div>
                                <div class="xfer-total">{{ colour_total_transfer(row, colour, bucket.transfer_field) }}</div>
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';

import { h } from 'vue'

let items = ref([])
let colours = ref([])
let given_matrix = ref({ primary_values: [], groups: [] })
let received_matrix = ref({ primary_values: [], groups: [] })
let lt_list = JSON.parse(cur_frm.doc.lot_transfer_list || "{}");

const MatrixTable = {
    props: { matrix: Object, counterpartLabel: String },
    setup(props) {
        return () => {
            const sizes = props.matrix.primary_values || []
            return h('table', { class: 'table table-sm bordered-table old-lot-table' }, [
                h('thead', {}, h('tr', {}, [
                    h('th', { style: 'width:36px;' }, '#'),
                    h('th', { style: 'width:180px;' }, props.counterpartLabel),
                    h('th', { style: 'width:120px;' }, 'Colour'),
                    h('th', { style: 'width:80px;' }, 'Part'),
                    h('th', { style: 'width:110px;' }, 'Bucket'),
                    ...sizes.map(s => h('th', { key: s }, s)),
                    h('th', { style: 'width:60px;' }, 'Total'),
                    h('th', { style: 'width:160px;' }, 'Lot Transfers'),
                ])),
                h('tbody', {}, props.matrix.groups.flatMap((g, idx) => {
                    const rows = []
                    const buckets = []
                    if (g.lp_total > 0) buckets.push({ key:'lp', label:'Loose Piece', tone:'tone-lp', map:g.lp, total:g.lp_total })
                    if (g.lps_total > 0) buckets.push({ key:'lps', label:'Loose Piece Set', tone:'tone-lps', map:g.lps, total:g.lps_total })
                    buckets.forEach((b, bi) => {
                        const first = bi === 0
                        rows.push(h('tr', { key: `${idx}-${b.key}` }, [
                            first ? h('td', { rowspan: buckets.length }, String(idx + 1)) : null,
                            first ? h('td', { rowspan: buckets.length, class: 'fp-cell' }, [
                                h('a', { href: '#', onClick: (e) => { e.preventDefault(); redirect_to('Finishing Plan', g.fp) }, class: 'fp-link' }, g.fp),
                                h('div', { class: 'lot-sub' }, g.lot),
                            ]) : null,
                            first ? h('td', { rowspan: buckets.length }, h('span', { class: 'colour-pill' }, g.colour)) : null,
                            first ? h('td', { rowspan: buckets.length }, g.part ? h('span', { class: 'part-pill' }, g.part) : '—') : null,
                            h('td', { class: 'bucket-label' }, h('span', { class: `bucket-chip ${b.tone}` }, b.label)),
                            ...sizes.map(s => h('td', { key: s, class: 'qty-cell' }, (b.map[s] || 0) > 0 ? String(b.map[s]) : h('span', { class: 'cell-empty' }, '—'))),
                            h('td', { class: 'totals-cell' }, h('div', { class: 'xfer-total' }, String(b.total))),
                            first ? h('td', { rowspan: buckets.length, class: 'lt-cell' }, (g.lts || []).map(lt =>
                                h('div', {}, h('a', { href: '#', onClick: (e) => { e.preventDefault(); redirect_to('Lot Transfer', lt) }, class: 'fp-link' }, lt))
                            )) : null,
                        ].filter(Boolean)))
                    })
                    return rows
                })),
            ])
        }
    },
}

// Hide "Fetch Items" button when this FP is OCR Completed, or when items are already fetched/pending action.
const show_fetch_button = computed(() => {
    if (cur_frm.doc.fp_status === "OCR Completed") return false
    if (items.value && items.value.length > 0) return false
    return true
})

// Hydrate from persisted onload payload so reload shows the previously fetched rows.
const onload = cur_frm.doc.__onload || {}
if (onload.old_lot_data) {
    items.value = onload.old_lot_data.data || []
    colours.value = onload.old_lot_data.colours || []
}
if (onload.old_lot_given_matrix) {
    given_matrix.value = onload.old_lot_given_matrix
}
if (onload.old_lot_received_matrix) {
    received_matrix.value = onload.old_lot_received_matrix
}

function fetch_items(){
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan.finishing_plan.fetch_from_old_lot",
        args: {
            "doc_name": cur_frm.doc.name,
        },
        freeze: true,
        freeze_message: "Fetching from OCR Completed Finishing Plan",
        callback: function(r){
            items.value = r.message.data || [];
            colours.value = r.message.colours || []
            if (!items.value.length) {
                frappe.show_alert({ message: "No transferable items found in any OCR Completed plan for this item.", indicator: "orange" })
            }
        }
    })
}

function cancel_doc(doctype, docname){
    let d = new frappe.ui.Dialog({
        title: `Are you sure want to cancel this ${doctype}`,
        primary_action_label: 'Yes',
        secondary_action_label: "No",
        primary_action(){
            d.hide()
            frappe.call({
                method: "production_api.production_api.doctype.finishing_plan.finishing_plan.cancel_document",
                args: {
                    "doctype": doctype,
                    "docname": docname,
                },
                freeze: true,
                freeze_message: `Cancelling ${doctype}`,
                callback: function(){
                    frappe.show_alert("Cancelled Successfully")
                }
            })
        },
        secondary_action(){
            d.hide()
        }
    })
    d.show()
}

function redirect_to(doctype, docname){
    frappe.open_in_new_tab = true;
    frappe.set_route("Form", doctype, docname);
}

function lot_transfer() {
    let check = check_set_colour()
    if (check) {
        let d = new frappe.ui.Dialog({
            title: "Are you sure want to transfer the items",
            primary_action_label: "Yes",
            secondary_action_label: "No",
            primary_action(){
                d.hide()
                frappe.call({
                    method: "production_api.production_api.doctype.finishing_plan.finishing_plan.create_lot_transfer",
                    args: {
                        "data": items.value,
                        "item_name": cur_frm.doc.item,
                        "ipd": cur_frm.doc.production_detail,
                        "lot": cur_frm.doc.lot,
                        "doc_name": cur_frm.doc.name
                    },
                    freeze: true,
                    freeze_message: "Transferring Items....",
                    callback: function(){
                        frappe.msgprint("Items Transferred")
                    }
                })
            },
            secondary_action(){
                d.hide()
            }   
        })
        d.show()
    }
}

function check_set_colour() {
    for (let i = 0; i < items.value.length; i++) {
        let row = items.value[i]
        for (let colour of Object.keys(row['old_lot_inward']['data'])) {
            let check = false
            for (let size of Object.keys(row['old_lot_inward']['data'][colour]['values'])) {
                const c = row['old_lot_inward']['data'][colour]['values'][size]
                const tlp = Number(c['transfer_loose_piece'] || 0)
                const tlps = Number(c['transfer_loose_piece_set'] || 0)
                if (tlp > Number(c['balance_loose_piece'] || 0)) {
                    frappe.msgprint(`Transfer Loose Piece (${tlp}) exceeds available (${c['balance_loose_piece']}) for ${colour} / ${size}`)
                    return false
                }
                if (tlps > Number(c['balance_loose_piece_set'] || 0)) {
                    frappe.msgprint(`Transfer Loose Piece Set (${tlps}) exceeds available (${c['balance_loose_piece_set']}) for ${colour} / ${size}`)
                    return false
                }
                if (tlp > 0 || tlps > 0) {
                    check = true
                }
            }
            if (check && !row['old_lot_inward']['data'][colour]['set_combination']) {
                frappe.msgprint("Please mention Set Colour")
                return false
            }
        }
    }
    return true
}

function colour_total_transfer(row, colour, field) {
    let total = 0
    for (let size of Object.keys(row['old_lot_inward']['data'][colour]['values'])) {
        total += Number(row['old_lot_inward']['data'][colour]['values'][size][field] || 0)
    }
    return total
}

function visible_colours(row) {
    // order preserved by backend; just return the keys that have any balance
    return Object.keys(row['old_lot_inward']['data']).filter(colour => {
        const ct = row['old_lot_inward']['data'][colour]['colour_total']
        return (ct.balance_loose_piece || 0) + (ct.balance_loose_piece_set || 0) > 0
    })
}

function visible_buckets(row, colour) {
    const ct = row['old_lot_inward']['data'][colour]['colour_total']
    const lp_total = ct.balance_loose_piece || 0
    const lps_total = ct.balance_loose_piece_set || 0
    const vals = row['old_lot_inward']['data'][colour]['values']
    const buckets = []
    if (lp_total > 0) {
        buckets.push({
            key: 'lp',
            label: 'Loose Piece',
            tone: 'tone-lp',
            transfer_field: 'transfer_loose_piece',
            balance_of: (size) => Number(vals[size].balance_loose_piece || 0),
            colour_total: lp_total,
        })
    }
    if (lps_total > 0) {
        buckets.push({
            key: 'lps',
            label: 'Loose Piece Set',
            tone: 'tone-lps',
            transfer_field: 'transfer_loose_piece_set',
            balance_of: (size) => Number(vals[size].balance_loose_piece_set || 0),
            colour_total: lps_total,
        })
    }
    if (!buckets.length) return []
    buckets[0].first = true
    buckets[0].rowspan = buckets.length
    return buckets
}


</script>

<style scoped>
.small-width {
    width: 40%;
}

.bordered-table {
    width: 100%;
    border: 1px solid #ccc;
    border-collapse: collapse;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}

.dark-border{
    border: 2px solid black;
}

.old-lot-group h3 {
    margin: 14px 0 8px 0;
    font-size: 16px;
    color: #0f172a;
}
.group-sub {
    color: #64748b;
    font-weight: 400;
    font-size: 13px;
    margin-left: 6px;
}
.old-lot-table th {
    background: #f1f5f9 !important;
    font-size: 12px;
    color: #334155;
    font-weight: 600;
    letter-spacing: .2px;
}
.old-lot-table td {
    vertical-align: middle;
    font-size: 13px;
}
.old-lot-table .colour-pill {
    display: inline-block;
    padding: 3px 10px;
    background: #eef2ff;
    color: #3730a3;
    border-radius: 9999px;
    font-weight: 600;
}
.old-lot-table .part-pill {
    display: inline-block;
    padding: 3px 8px;
    background: #ecfeff;
    color: #155e75;
    border-radius: 6px;
    font-weight: 600;
    font-size: 12px;
}
.bucket-label { text-align: left !important; padding-left: 10px !important; }
.bucket-chip {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .3px;
    text-transform: uppercase;
}
.tone-lp  { background: #fef3c7; color: #92400e; }
.tone-lps { background: #dcfce7; color: #166534; }
.cell-stack .cell-wrap {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 2px;
}
.cell-stack .bal-badge {
    display: inline-block;
    background: #f1f5f9;
    color: #475569;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    padding: 1px 0;
}
.cell-stack .transfer-input {
    height: 26px;
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    padding: 0 4px;
    border: 1px solid transparent;
    border-radius: 4px;
    background: #fff;
    color: #0f172a;
    box-shadow: none;
    transition: border-color .12s ease, background .12s ease;
}
.cell-stack .transfer-input:hover {
    border-color: #e2e8f0;
}
.cell-stack .transfer-input:focus {
    outline: none;
    border-color: #6366f1;
    background: #f8fafc;
    box-shadow: 0 0 0 3px rgba(99,102,241,.15);
}
/* kill number-input spinners */
.cell-stack .transfer-input::-webkit-inner-spin-button,
.cell-stack .transfer-input::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
.cell-stack .transfer-input[type=number] {
    -moz-appearance: textfield;
    appearance: textfield;
}
/* placeholder zero is easier to distinguish */
.cell-stack .transfer-input:placeholder-shown,
.cell-stack .transfer-input[value="0"] { color: #cbd5e1; }
.cell-stack .cell-empty {
    color: #cbd5e1;
    font-weight: 600;
}
.totals-cell .bal-total {
    font-size: 12px;
    color: #64748b;
}
.totals-cell .xfer-total {
    font-weight: 700;
    color: #0f172a;
}
.no-balance-row td { opacity: .55; }
.fp-cell { text-align: left !important; padding-left: 10px !important; }
.fp-link { color: #4f46e5; font-weight: 600; }
.fp-link:hover { text-decoration: underline; }
.lot-sub { color: #64748b; font-size: 12px; margin-top: 2px; }
.qty-cell { font-weight: 600; color: #0f172a; }
.lt-cell { text-align: left !important; padding-left: 10px !important; font-size: 12px; }
</style>