<template>
    <div ref="root" style="padding:20px;">
        <h3 style="text-align:center;padding-top:15px;">Work In Progress Report</h3>
        <div style="display:flex;">
            <div class="category-input col-md-2"></div>
            <div class="lot-status-input col-md-2"></div>
            <div class="lot-input col-md-3"></div>
            <div class="item-input col-md-3"></div>
            <div style="padding-top:27px;">
                <button class="btn btn-primary" @click="get_work_in_progress_report()">Show Report</button>
            </div>
            <div style="padding-top:27px;padding-left:10px;">
                <button class="btn btn-primary" @click="get_list_items()">Paste</button>
            </div>
        </div>
        <multi-process-report ref="multiReport"/>
        <div v-if="items && Object.keys(items).length > 0" class="table-container">
            <table class="table table-md table-sm-bordered bordered-table">
                <tr>
                    <th>Style</th>
                    <th>Lot No</th>
                    <th v-for="col in Object.keys(items['columns']['cut_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['against_cut_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['sew_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['against_sew_columns'])">{{ col }}</th>
                    <th v-for="col in Object.keys(items['columns']['finishing_columns'])">{{ col }}</th>
                    <th>Cut Last Date</th>
                    <th>Sewing Sent Date</th>
                    <th>Finishing Inward Date</th>
                </tr>
                <tr class="filter-row">
                    <th><input type="text" class="filter-input" v-model="columnFilters.style"/></th>
                    <th><input type="text" class="filter-input" v-model="columnFilters.lot"/></th>
                    <th v-for="col in Object.keys(items['columns']['cut_columns'])" :key="'cf-cut-'+col">
                        <input type="text" class="filter-input" v-model="columnFilters['cut:'+col]"/>
                    </th>
                    <th v-for="col in Object.keys(items['columns']['against_cut_columns'])" :key="'cf-agcut-'+col">
                        <input type="text" class="filter-input" v-model="columnFilters['against_cut:'+col]"/>
                    </th>
                    <th v-for="col in Object.keys(items['columns']['sew_columns'])" :key="'cf-sew-'+col">
                        <input type="text" class="filter-input" v-model="columnFilters['sew:'+col]"/>
                    </th>
                    <th v-for="col in Object.keys(items['columns']['against_sew_columns'])" :key="'cf-agsew-'+col">
                        <input type="text" class="filter-input" v-model="columnFilters['against_sew:'+col]"/>
                    </th>
                    <th v-for="col in Object.keys(items['columns']['finishing_columns'])" :key="'cf-fin-'+col">
                        <input type="text" class="filter-input" v-model="columnFilters['finishing:'+col]"/>
                    </th>
                    <th><input type="text" class="filter-input" v-model="columnFilters.last_cut_date"/></th>
                    <th><input type="text" class="filter-input" v-model="columnFilters.sew_sent_date"/></th>
                    <th><input type="text" class="filter-input" v-model="columnFilters.finishing_inward_date"/></th>
                </tr>

                <tr v-for="row in filteredRows">
                    <td>{{ row['style'] }}</td>
                    <td>{{ row['lot'] }}</td>
                    <td v-for="col in items['columns']['cut_columns']"
                        :style="get_cell_style(row, 'cut_details', col)"
                        :class="{ 'clickable-quantity': can_open_inhouse_report(row, 'cut_details', col) }"
                        :title="get_inhouse_title(row, 'cut_details', col)"
                        @click="open_inhouse_quantity_report(row, 'cut_details', col)"
                        >
                        {{ row['cut_details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['against_cut_columns']"
                        :style="get_cell_style(row, 'against_cut_details', col)"
                        :class="{ 'clickable-quantity': can_open_inhouse_report(row, 'against_cut_details', col) }"
                        :title="get_inhouse_title(row, 'against_cut_details', col)"
                        @click="open_inhouse_quantity_report(row, 'against_cut_details', col)"
                        >
                        {{ row['against_cut_details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['sew_columns']"
                        :style="get_cell_style(row, 'sewing_details', col)"
                        :class="{ 'clickable-quantity': can_open_inhouse_report(row, 'sewing_details', col) }"
                        :title="get_inhouse_title(row, 'sewing_details', col)"
                        @click="open_inhouse_quantity_report(row, 'sewing_details', col)"
                        >
                        {{ row['sewing_details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['against_sew_columns']"
                        :style="get_cell_style(row, 'against_sew_details', col)"
                        :class="{ 'clickable-quantity': can_open_inhouse_report(row, 'against_sew_details', col) }"
                        :title="get_inhouse_title(row, 'against_sew_details', col)"
                        @click="open_inhouse_quantity_report(row, 'against_sew_details', col)"
                        >
                        {{ row['against_sew_details'][col] }}
                    </td>
                    <td v-for="col in items['columns']['finishing_columns']"
                        :style="get_cell_style(row, 'finishing_details', col)"
                        :class="{ 'clickable-quantity': can_open_inhouse_report(row, 'finishing_details', col) }"
                        :title="get_inhouse_title(row, 'finishing_details', col)"
                        @click="open_inhouse_quantity_report(row, 'finishing_details', col)"
                        >
                        {{ row['finishing_details'][col] }}
                    </td>
                    <td>{{ get_date(row['last_cut_date']) }}</td>
                    <td>{{ get_date(row['sew_sent_date']) }}</td>
                    <td>{{ get_date(row['finishing_inward_date']) }}</td>
                </tr>
                <tr>
                    <th></th>
                    <th></th>
                    <th v-for="col in items['columns']['cut_columns']">
                        {{ filteredTotals.cut_details[col] }}
                    </th>
                    <th v-for="col in items['columns']['against_cut_columns']">
                        {{ filteredTotals.against_cut_details[col] }}
                    </th>
                    <th v-for="col in items['columns']['sew_columns']">
                        {{ filteredTotals.sewing_details[col] }}
                    </th>
                    <th v-for="col in items['columns']['against_sew_columns']">
                        {{ filteredTotals.against_sew_details[col] }}
                    </th>
                    <th v-for="col in items['columns']['finishing_columns']">
                        {{ filteredTotals.finishing_details[col] }}
                    </th>
                    <th></th>
                    <th></th>
                    <th></th>
                </tr>
            </table>
        </div>
        <div v-else>
            <div class="flex justify-center align-center text-muted" style="height: 50vh;">
                <div>
                    <div class="msg-box no-border">
                        <div>
                            <img src="/assets/frappe/images/ui-states/list-empty-state.svg" alt="Generic Empty State" class="null-state">
                            <p>Nothing to show</p>
                        </div>
                    </div>
                </div>
            </div>    
        </div>
    </div>
</template>

<script setup>

import {ref, reactive, computed, watch, onMounted, createApp} from 'vue';
import MultiProcessReport from './MultiProcessReport.vue'
import MultiSelectListConverter from './MultiSelectListConverter.vue'

let category = null
let lot_status = null
let root = ref(null)
let sample_doc = ref({})
let items = ref({})
let lot_list = null
let item_list = null
const multiReport = ref(null)
let process_list = ref([])

const columnFilters = reactive({})

const matches = (cell, filter) => {
    if (!filter) return true
    const s = (cell === null || cell === undefined) ? '' : String(cell)
    return s.toLowerCase().includes(String(filter).toLowerCase())
}

const filteredRows = computed(() => {
    if (!items.value || !items.value.lot_data) return []
    const raw = items.value.lot_data
    const rows = Array.isArray(raw) ? raw : Object.values(raw)
    const cols = items.value.columns || {}
    const cellMatches = (row, bucket, section, rowKey) => {
        const map = cols[section] || {}
        for (const label of Object.keys(map)) {
            const dataKey = map[label]
            const src = row[rowKey]
            const cellVal = src ? src[dataKey] : undefined
            if (!matches(cellVal, columnFilters[bucket + ':' + label])) return false
        }
        return true
    }
    return rows.filter(row => {
        if (!matches(row.style, columnFilters.style)) return false
        if (!matches(row.lot, columnFilters.lot)) return false
        if (!cellMatches(row, 'cut', 'cut_columns', 'cut_details')) return false
        if (!cellMatches(row, 'against_cut', 'against_cut_columns', 'against_cut_details')) return false
        if (!cellMatches(row, 'sew', 'sew_columns', 'sewing_details')) return false
        if (!cellMatches(row, 'against_sew', 'against_sew_columns', 'against_sew_details')) return false
        if (!cellMatches(row, 'finishing', 'finishing_columns', 'finishing_details')) return false
        if (!matches(get_date(row.last_cut_date), columnFilters.last_cut_date)) return false
        if (!matches(get_date(row.sew_sent_date), columnFilters.sew_sent_date)) return false
        if (!matches(get_date(row.finishing_inward_date), columnFilters.finishing_inward_date)) return false
        return true
    })
})

const filteredTotals = computed(() => {
    const totals = {
        cut_details: {},
        against_cut_details: {},
        sewing_details: {},
        against_sew_details: {},
        finishing_details: {},
    }
    const cols = (items.value && items.value.columns) || {}
    const addTo = (bucket, colsKey, rowKey) => {
        const map = cols[colsKey] || {}
        for (const label of Object.keys(map)) {
            const dataKey = map[label]
            let sum = 0
            for (const row of filteredRows.value) {
                const src = row[rowKey]
                if (!src) continue
                const v = Number(src[dataKey])
                if (!isNaN(v)) sum += v
            }
            totals[bucket][dataKey] = sum
        }
    }
    addTo('cut_details', 'cut_columns', 'cut_details')
    addTo('against_cut_details', 'against_cut_columns', 'against_cut_details')
    addTo('sewing_details', 'sew_columns', 'sewing_details')
    addTo('against_sew_details', 'against_sew_columns', 'against_sew_details')
    addTo('finishing_details', 'finishing_columns', 'finishing_details')
    return totals
})

function get_process_for_cell(row, detailsKey, dataKey){
    return row?.process_drilldown?.[detailsKey]?.[dataKey] || null
}

function can_open_inhouse_report(row, detailsKey, dataKey){
    return Boolean(row?.lot && get_process_for_cell(row, detailsKey, dataKey))
}

function get_cell_style(row, detailsKey, dataKey){
    const diffColumns = items.value.diff_columns || []
    const details = row[detailsKey] || {}
    if(diffColumns.includes(dataKey)){
        return get_style(details[dataKey])
    }
    return { background: 'white' }
}

function get_inhouse_title(row, detailsKey, dataKey){
    const processName = get_process_for_cell(row, detailsKey, dataKey)
    if(!processName){
        return ''
    }
    return `Open Inhouse Quantity Report for ${processName}`
}

function open_inhouse_quantity_report(row, detailsKey, dataKey){
    const processName = get_process_for_cell(row, detailsKey, dataKey)
    if(!row?.lot || !processName){
        return
    }
    const params = new URLSearchParams({
        lot: row.lot,
        process: processName,
        show: '1',
    })
    window.open(`/app/inhouse-quantity-rep?${params.toString()}`, '_blank', 'noopener')
}

// Clear filters whenever a new report is loaded
watch(items, () => {
    for (const k of Object.keys(columnFilters)) delete columnFilters[k]
})

onMounted(()=> {
    let el = root.value
    $(el).find(".category-input").html("");
    category = frappe.ui.form.make_control({
        parent: $(el).find(".category-input"),
        df: {
            fieldname: "category",
            fieldtype: "Link",
            options: "Product Category",
            label: "Product Category",
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".lot-status-input").html("");
    lot_status = frappe.ui.form.make_control({
        parent: $(el).find(".lot-status-input"),
        df: {
            fieldname: "lot_status",
            fieldtype: "Select",
            options: "\nOpen\nClosed",
            label: "Lot Status",
            default: "Open",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    })
    $(el).find(".lot-input").html("");
    lot_list = frappe.ui.form.make_control({
        parent: $(el).find(".lot-input"),
        df: {
            fieldtype: "MultiSelectList",
            fieldname: "lot",
            label: "Lot",
            options: "Lot",
            get_data: function (txt) {
                return frappe.db.get_link_options("Lot", txt);
            },
        },
        doc: sample_doc.value,
        render_input: true,
    })
    
    $(el).find(".item-input").html("");
    item_list = frappe.ui.form.make_control({
        parent: $(el).find(".item-input"),
        df: {
            fieldtype: "MultiSelectList",
            fieldname: "item",
            label: "Item",
            options: "Item",
            get_data: function(txt){
                return frappe.db.get_link_options("Item", txt)
            }
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

function get_work_in_progress_report(){
    let lot_list_val = lot_list.get_value()
    let item_list_val = item_list.get_value()
    process_list.value = multiReport.value.process_list
    if(!category.get_value() && lot_list_val.length == 0 && item_list_val.length == 0){
        frappe.msgprint("Please Set Atleast one filter other than Lot Status")
    }
    else{
        frappe.call({
            method: "production_api.utils.get_work_in_progress_report",
            args: {
                "category": category.get_value(),
                "status": lot_status.get_value(),
                "lot_list_val": lot_list_val,
                "item_list": item_list_val,
                "process_list": process_list.value
            },
            freeze: true,
            freeze_message: "Fetching Data",
            callback: function(r){
                items.value = r.message
            }
        })
    }
}

function get_list_items(){
    let d = new frappe.ui.Dialog({
        fields: [
            {
                "fieldname": "pop_up_html",
                "fieldtype": "HTML"
            }
        ],
        primary_action(){
            if (i.select_value == 'Item'){
                let updated_list = item_list.get_value().concat(i.list)
                item_list.set_value(updated_list)
            }
            else if(i.select_value == 'Lot'){
                let updated_list = lot_list.get_value().concat(i.list)
                console.log(updated_list)
                lot_list.set_value(updated_list)
            }
            d.hide()
        }
    })
    d.fields_dict['pop_up_html'].$wrapper.html("")
    let el = d.fields_dict['pop_up_html'].$wrapper.get(0)
    let vue = createApp(MultiSelectListConverter, {
        "items_list": ['Lot', 'Item']
    })
    i = vue.mount(el)
    d.show()
}

function get_style(val){
    if(val < 0){
        return {"background":"#f57f87"};
    }
    else if(val > 0){
        return {"background":"#98ebae"}
    }
    return {"background": "none"};
}

function get_date(date){
    if(date){
        let x = new Date(date)
        return x.getDate() + "-" + (x.getMonth() + 1) + "-" + x.getFullYear()
    }
    return ""
}

</script>
<style scoped>
.table-container {
    width: 100%;
    overflow: auto;
    max-height: 70vh;
    -webkit-overflow-scrolling: touch;
    border: 2px solid #000;
    border-radius: 6px;
    background: #fff;
}

.bordered-table {
    width: 100%;
    min-width: 1200px; /* ensures scrollable area */
    border-collapse: collapse;
    text-align: center;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    white-space: nowrap; /* prevents columns from wrapping */
}

.bordered-table th {
    background-color: #f8f9fa;
    position: sticky;
    top: 0;
    z-index: 1;
    font-weight: 600;
}

.bordered-table tr.filter-row th {
    top: 33px;
    background-color: #fff;
    padding: 0;
    z-index: 1;
    font-weight: 400;
    border: 1px solid #d1d5db;
}

.filter-input {
    width: 100%;
    height: 100%;
    min-height: 26px;
    padding: 4px 8px;
    border: none;
    border-radius: 0;
    font-size: inherit;
    font-family: inherit;
    font-weight: 400;
    color: #374151;
    background: transparent;
    outline: none;
    box-shadow: none;
}

.filter-input:focus {
    background: #eff6ff;
}

.clickable-quantity {
    color: #0b5cab;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
}

.clickable-quantity:hover {
    color: #063f7a;
}

.table-container::-webkit-scrollbar {
    height: 8px;
}
.table-container::-webkit-scrollbar-thumb {
    background-color: #ccc;
    border-radius: 4px;
}
.table-container::-webkit-scrollbar-thumb:hover {
    background-color: #999;
}

</style>
