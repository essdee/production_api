<template>
    <div ref="root">
        <div style="padding:25px;">
            <div class="row pb-4">
                <div class="lot-name col-md-4"></div>
                <div class="item-name col-md-4"></div>
                <div class="process-name col-md-4"></div>
                <button class="btn btn-success ml-3" @click="get_filters()">Show Report</button>
            </div>

            <div class="scroll-container" v-if="show_table && items.datas && items.datas.length > 0">
                <table class="table table-md table-md-bordered inner-table">
                    <thead>
                        <tr>
                            <th class="sticky-col col1">S.No</th>
                            <th class="sticky-col col2">Item</th>
                            <th class="sticky-col col3">Lot</th>
                            <th class="sticky-col col4">Process</th>
                            <th class="sticky-col col5">Quantity</th>
                            <th class="sticky-col col6">Reason</th>
                            <th class="sticky-col col7">Delay</th>
                            <th class="sticky-col col8">Planned Date</th>
                            <th style="width:110px;" v-for="d in items['dates']" :key="d">{{ d }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="(item, idx) in items.datas" :key="idx">
                            <tr @click="toggle_row(item, idx)">
                                <td class="sticky-col col1">{{ idx + 1 }}</td>
                                <td class="sticky-col col2">{{ item['item'] }}</td>
                                <td class="sticky-col col3">{{ item['lot'] }}</td>
                                <td class="sticky-col col4">{{ item['process_name'] }}</td>
                                <td class="sticky-col col5">{{ item['qty'] }}</td>
                                <td class="sticky-col col6">{{ item['reason'] || '' }}</td>
                                <td class="sticky-col col7">{{ item['delay'] || '' }}</td>
                                <td class="sticky-col col8">{{ item['planned_end_date'] || '' }}</td>
                                <td v-for="d in items['dates']" :key="d">{{ item[d] || '' }}</td>
                            </tr>
                            <tr v-if="expandedRowIndex === idx">
                                <td :colspan="6" class="p-0 sticky-col col6">
                                    <div style="display:flex;padding-top:10px;justify-content:center;">
                                        <div>
                                            <table class="table table-bordered">
                                                <thead>
                                                    <tr>
                                                        <th style="min-width: 250px;">Work Order</th>
                                                        <th style="min-width: 250px;">Colours</th>
                                                        <th style="min-width: 200px;">Update</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    <tr style="cursor:pointer;" v-for="(row, i) in work_order_details" :key="i">
                                                        <td @click="map_to_work_order(row.name)">{{ row.name }}</td>
                                                        <td>{{ row.wo_colours }}</td>
                                                        <td>
                                                            <button class="btn btn-secondary" @click="update_expected_date(row.name)">Update Expected Date</button>
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
                                        <button class="btn btn-success" @click="update_all_work_orders()">Update All Work Order Date</button>
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

function update_expected_date(work_order) {
    get_date_and_reason().then((values) => {
        if (values) {
            frappe.call({
                method: "production_api.utils.update_expected_date",
                args: {
                    work_order:  work_order,
                    expected_date: values.date,
                    reason: values.reason,
                },
            });
        }
    });
}

function update_all_work_orders(){
    get_date_and_reason().then((values) => {
        if (values) {
            frappe.call({
                method: "production_api.utils.update_all_work_orders",
                args: {
                    work_order_details: work_order_details.value,
                    expected_date: values.date,
                    reason: values.reason,
                },
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


.col1 { left: 0;     width: 60px; }
.col2 { left: 60px;  width: 250px; }
.col3 { left: 310px; width: 100px;}
.col4 { left: 410px; width: 80px;}
.col5 { left: 490px; width: 80px; }
.col6 { left: 570px; width: 100px; }
.col7 { left: 670px; width: 50px; } 
.col8 { left: 720px; width: 110px; }

.scroll-container {
    max-height: 700px;
    overflow-y: auto;
    overflow-x: auto;
    position: relative; 
}

</style>
