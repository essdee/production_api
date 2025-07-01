<template>
    <div ref="root">
        <div style="padding:25px;">
            <div class="row pb-4">
                <div class="lot-name col-md-3"></div>
                <div class="item-name col-md-4"></div>
                <div class="process-name col-md-4"></div>
                <div style="padding-top:27px;">
                    <button class="btn btn-secondary" @click="clear_filters()">Clear Filters</button>
                </div>
                <div></div>
                <div class="d-flex w-100 mt-3 pr-3 pl-3">
                    <div><button class="btn btn-success" @click="get_filters()">Show Report</button></div>
                    <div style="padding-left:15px;">
                        <button class="btn btn-success" @click="create_checkpoint(items.datas)">Create Check Point</button>
                    </div>
                </div>
            </div>
            <div class="scroll-container" v-if="show_table && items.datas && items.datas.length > 0">
                <table class="table table-md table-md-bordered inner-table">
                    <thead>
                        <tr>
                            <th class="sticky-col col1">S.No</th>
                            <th class="sticky-col col2">Assigned to</th>
                            <th class="sticky-col col3">Item</th>
                            <th class="sticky-col col4">Lot</th>
                            <th class="sticky-col col5">Process</th>
                            <th class="sticky-col col6">Quantity</th>
                            <th class="sticky-col col7">Planned Date</th>
                            <th class="sticky-col col8">Delay</th>
                            <th class="sticky-col col9">Reason</th>
                            <th class="sticky-col col10">Check Point</th>
                            <th style="width:110px;" v-for="d in items['dates']" :key="d">{{ d }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="(item, idx) in items.datas" :key="idx">
                            <tr @click="toggle_row(item, idx)">
                                <td class="sticky-col col1">{{ idx + 1 }}</td>
                                <td class="sticky-col col2">{{ item['assigned'] || '' }}</td>
                                <td class="sticky-col col3">{{ item['item'] }}</td>
                                <td class="sticky-col col4">{{ item['lot'] }}</td>
                                <td class="sticky-col col5">{{ item['process_name'] }}</td>
                                <td class="sticky-col col6">{{ item['qty'] }}</td>
                                <td class="sticky-col col7">{{ item['planned_end_date'] || '' }}</td>
                                <td class="sticky-col col8">{{ item['delay'] || '' }}</td>
                                <td class="sticky-col col9">{{ item['reason'] || '' }}</td>
                                <td class="sticky-col col10" :style="getCheckPointStyle(item)" >
                                    {{ item['check_point'] || '' }}
                                </td>
                                <td v-for="d in items['dates']" :key="d">{{ item[d] || '' }}</td>
                            </tr>
                            <tr v-if="expandedRowIndex === idx">
                                <td :colspan="1000" class="p-0 expanded-row-content">
                                    <div style="display:flex;padding-top:10px;justify-content:center;">
                                        <div>
                                            <table class="table table-bordered">
                                                <thead>
                                                    <tr>
                                                        <th style="min-width:150px;">Work Order</th>
                                                        <th style="min-width:100px;">Colours</th>
                                                        <th style="min-width:100px;">Supplier</th>
                                                        <th style="min-width:100px;">Supplier Name</th>
                                                        <th style="min-width:100px;">Planned Quantity</th>
                                                        <th style="min-width:100px;">Pending</th>
                                                        <th style="min-width:200px;">Update</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    <tr style="cursor:pointer;" v-for="(row, i) in work_order_details" :key="i">
                                                        <td @click="map_to_work_order(row.name)">{{ row.name }}</td>
                                                        <td>{{ row.wo_colours }}</td>
                                                        <td>{{ row.supplier }}</td>
                                                        <td>{{ row.supplier_name }}</td>
                                                        <td>{{ row.total_quantity }}</td>
                                                        <td>{{ row.total_quantity - row.total_no_of_pieces_received }}</td>
                                                        <td>
                                                            <button class="btn btn-secondary" @click="update_expected_date(row.name, idx)">Update Expected Date</button>
                                                        </td>
                                                    </tr>
                                                </tbody>
                                            </table>
                                        </div>
                                        <div @click="expandedRowIndex = null">
                                            <svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" 
                                                xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px" width="122.881px" height="122.88px" 
                                                viewBox="0 0 600.881 600.88" enable-background="new 0 0 122.881 122.88" 
                                                xml:space="preserve"><g><path fill-rule="evenodd" clip-rule="evenodd" 
                                                d="M61.44,0c33.933,0,61.441,27.507,61.441,61.439 c0,33.933-27.508,61.44-61.441,61.44C27.508,122.88,0,95.372,0,61.439C0,27.507,27.508,0,61.44,0L61.44,0z M81.719,36.226 c1.363-1.363,3.572-1.363,4.936,0c1.363,1.363,1.363,3.573,0,4.936L66.375,61.439l20.279,20.278c1.363,1.363,1.363,3.573,0,4.937 c-1.363,1.362-3.572,1.362-4.936,0L61.44,66.376L41.162,86.654c-1.362,1.362-3.573,1.362-4.936,0c-1.363-1.363-1.363-3.573,0-4.937 l20.278-20.278L36.226,41.162c-1.363-1.363-1.363-3.573,0-4.936c1.363-1.363,3.573-1.363,4.936,0L61.44,56.504L81.719,36.226 L81.719,36.226z"/></g></svg>
                                        </div>
                                    </div>
                                    <div style="padding-bottom:15px;text-align:center;padding-right:75px;">
                                        <button class="btn btn-success" @click="update_all_work_orders(item, idx)">Update All Work Order Date</button>
                                    </div>
                                </td>
                            </tr>
                        </template>    
                    </tbody>
                </table>
            </div>
        </div>    
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

let process = null;
let lot = null;
let item = null;
let root = ref(null);
let sample_doc = ref({});
let items = ref({})
let show_table = ref(true)
let work_order_details = ref([])
let expandedRowIndex = ref(null);

function toggle_row(item, index) {
    expandedRowIndex.value = index
    get_work_order_detail(item)
}

onMounted(() => {
    let el = root.value;
    $(el).find(".process-name").html("");
    process = frappe.ui.form.make_control({
        parent: $(el).find(".process-name"),
        df: {
            fieldname: "process_name",
            fieldtype: "Link",
            label: "Process",
            options: "Process",
        },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".lot-name").html("");
    lot = frappe.ui.form.make_control({
        parent: $(el).find(".lot-name"),
        df: {
            fieldname: "lot",
            fieldtype: "Link",
            options: "Lot",
            label: "Lot",
            onchange:async ()=> {
                let x = lot.get_value()
                if(x && x != "" && x != null){
                    let y = await frappe.db.get_value('Lot',x, "item")
                    item.set_value(y.message.item)
                    item.refresh()
                }
            } 
        },
        doc: sample_doc.value,
        render_input: true,
    });

    $(el).find(".item-name").html("");
    item = frappe.ui.form.make_control({
        parent: $(el).find(".item-name"),
        df: {
            fieldname: "item",
            fieldtype: "Link",
            options: "Item",
            label: "Item",
        },
        doc: sample_doc.value,
        render_input: true,
    });
});

function parseDMYtoDate(dmyStr) {
    const [dd, mm, yyyy] = dmyStr.split("-");
    return new Date(`${yyyy}-${mm}-${dd}`);
}

function getCheckPointStyle(item) {
    if (!item['check_point']) return {};

    const lastDateKey = items.value['dates'][items.value['dates'].length - 1];
    const checkPoint = new Date(parseDMYtoDate(item['check_point']));
    const lastDate = new Date(parseDMYtoDate(item[lastDateKey]));
    return {
        backgroundColor: checkPoint <= lastDate ? 'rgb(249, 194, 195)' : 'rgb(180, 244, 170)',
    };
}

function clear_filters(){
    lot.set_value(null)
    item.set_value(null)
    process.set_value(null)
}

function get_filters() {
    show_table.value = false
    expandedRowIndex.value = null
    frappe.call({
        method: "production_api.utils.get_t_and_a_report_data",
        args: {
            "lot":lot.get_value(),
            "item": item.get_value(),
            "process_name": process.get_value(),
        },
        callback: function(r){
            items.value = r.message
            show_table.value = true
        }
    })
}

function create_checkpoint(data){
    if(!data || data.length == 0){
        frappe.msgprint("There is no items in the page")
        return   
    }
    let check = false
    for(let i = 0; i < data.length ; i++){
        if(data[i].hasOwnProperty("changed")){
            check = true
        }
    }
    if(!check){
        frappe.msgprint("There is nothing updated in this page");
    }
    frappe.call({
        method: "production_api.utils.update_wo_checkpoint",
        args: {
            datas: data,
        }
    })
}

function get_work_order_detail(item, idx){
    frappe.call({
        method: "production_api.utils.get_work_order_details",
        args: {
            detail: item
        },
        callback: function(r){
            work_order_details.value = r.message
        }
    })
}

function map_to_work_order(work_order){
    const url = `/app/work-order/${work_order}`;
    window.open(url, '_blank');
}

function get_date_and_reason() {
    return new Promise((resolve) => {
        let d = new frappe.ui.Dialog({
            title: "Update Expected Date",
            fields: [
                {
                    fieldtype: "Date",
                    fieldname: "expected_date",
                    label: "Expected Date",
                    reqd: 1,
                },
                {
                    fieldtype: "Small Text",
                    fieldname: "reason",
                    label: "Reason",
                    reqd: 1,
                }
            ],
            primary_action_label: "Update",
            primary_action: (values) => {
                d.hide();
                resolve({
                    date: values.expected_date,
                    reason: values.reason,
                });
            }
        });
        d.show();
    });
}

function update_expected_date(work_order, idx) {
    get_date_and_reason().then((values) => {
        if (values) {
            frappe.call({
                method: "production_api.utils.update_expected_date",
                args: {
                    work_order:  work_order,
                    expected_date: values.date,
                    reason: values.reason,
                },
                callback: function(r){
                    items.value.datas[idx] = r.message
                    items.value.datas[idx]['changed'] = true
                }
            });
        }
    });
}

function update_all_work_orders(row_data, idx){
    get_date_and_reason().then((values) => {
        if (values) {
            frappe.call({
                method: "production_api.utils.update_all_work_orders",
                args: {
                    lot: row_data['lot'],
                    item: row_data['item'],
                    process_name: row_data['process_name'],
                    work_order_details: work_order_details.value,
                    expected_date: values.date,
                    reason: values.reason,
                },
                callback: function(r){
                    items.value.datas[idx] = r.message
                    items.value.datas[idx]['changed'] = true
                }
            })
        }
    });
}

</script>

<style scoped>
.scroll-container {
    max-height: 700px;
    overflow-y: auto; 
    border: 1px solid #ddd; 
    overflow-x: auto;
    position: relative;
}

.inner-table {
    width: max-content;
    table-layout: fixed;
    border-collapse: collapse;
}

.inner-table th{
    background-color: #D3D3D3;
}

.inner-table thead {
    position: sticky;
    top: 0;
    z-index: 2;
    background: white; 
}

table th, td {
    border: 1px solid black;
    z-index: 10;
}

.sticky-col {
    border: 1px solid black;
    position: sticky;
    background: white;
    z-index: 1;
}

.sticky-col {
    border-right: 1px solid black;
    box-shadow: 2px 0 5px -2px black;
}

.expanded-row-content {
    position: relative;
    z-index: 0;
    background: white;
}

.col1 { left: 0;     box-shadow: inset 0 0 0 0.001rem black; width: 60px; }
.col2 { left: 60px;  box-shadow: inset 0 0 0 0.001rem black; width: 150px; }
.col3 { left: 210px; box-shadow: inset 0 0 0 0.001rem black; width: 250px;}
.col4 { left: 460px; box-shadow: inset 0 0 0 0.001rem black; width: 100px;}
.col5 { left: 560px; box-shadow: inset 0 0 0 0.001rem black; width: 80px; }
.col6 { left: 640px; box-shadow: inset 0 0 0 0.001rem black; width: 80px; }
.col7 { left: 720px; box-shadow: inset 0 0 0 0.001rem black; width: 110px; } 
.col8 { left: 830px; box-shadow: inset 0 0 0 0.001rem black; width: 60px; }
.col9 { left: 890px; box-shadow: inset 0 0 0 0.001rem black; width: 110px; }
.col10 { left: 1000px; box-shadow: inset 0 0 0 0.001rem black; width: 110px; }

.scroll-container {
    max-height: 700px;
    overflow-y: auto;
    overflow-x: auto;
    position: relative; 
}

.inner-table {
    width: max-content;
    table-layout: fixed;
    border-collapse: separate; /* Change to separate to avoid border merging issues */
    border-spacing: 0; /* Ensure no gaps between cells */
}

</style>
