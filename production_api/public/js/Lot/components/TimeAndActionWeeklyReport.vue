<template>
    <div ref="root" style="padding: 20px;">
        <div class="row pb-4">
            <div class="report-date col-md-4"></div>
            <div class="lot-name col-md-4"></div>
            <div class="item-name col-md-4"></div>
            <button class="btn btn-success ml-3" @click="get_filters()">Show Report</button>
        </div>
        <div class="scroll-container1" v-show="show_table">
            <div v-for="lot in Object.keys(items)" :key="lot" class="lot-container">
                    <div v-for="master in Object.keys(items[lot])" :key="master">
                        <div>
                            <div class="lot-title">{{ lot }} ({{ master }})</div>
                            <div class="scroll-container2">
                                <div class="outer-table">
                                    <table class="inner-table">
                                        <thead>
                                            <tr>
                                                <th class="sticky-col col1">S.No</th>
                                                <th class="sticky-col col2">Item</th>
                                                <th class="sticky-col col3">Colour</th>
                                                <th class="sticky-col col4">Sizes</th>
                                                <th class="sticky-col col5">Quantity</th>
                                                <th class="sticky-col col6">Start Date</th>
                                                <th class="sticky-col col7">Delay</th>
                                                <th class="sticky-col col8">Activity</th>
                                                <th v-for="action in items[lot][master]['actions']" :key="action">
                                                    {{ action }}
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <template v-for="(data, idx) in items[lot][master]['datas']" :key="data">
                                                <tr>
                                                    <td class="sticky-col col1" rowspan="8">{{ idx + 1 }}</td>
                                                    <td class="sticky-col col2" rowspan="8">{{ data.item }}</td>
                                                    <td class="sticky-col col3" rowspan="8">{{ data.colour }}</td>
                                                    <td class="sticky-col col4" rowspan="8">{{ data.sizes }}</td>
                                                    <td class="sticky-col col5" rowspan="8">{{ data.qty }}</td>
                                                    <td class="sticky-col col6" rowspan="8">{{ get_date(data.start_date) }}</td>
                                                    <td class="sticky-col col7" rowspan="8">{{ data.delay }}</td>
                                                </tr>
                                                <tr>
                                                    <td class="sticky-col col8">Planned Date</td>
                                                    <td v-for="d in data['actions']" :key="d.date">{{ get_date(d.date) }}</td>
                                                </tr>
                                                <tr>
                                                    <td class="sticky-col col8">Rescheduled Date</td>
                                                    <td v-for="d in data['actions']" :key="d.rescheduled_date">{{ get_date(d.rescheduled_date) }}</td>
                                                </tr>
                                                <tr>
                                                    <td class="sticky-col col8">Actual</td>
                                                    <td v-for="d in data['actions']" :key="d.actual_date" :style="{ backgroundColor: d.actual_date > d.rescheduled_date ? '#FFCCCB' : d.actual_date ? '#90EE90' : 'White'}">
                                                        {{ get_date(d.actual_date) }}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td class="sticky-col col8">Reason for Delay</td>
                                                    <td v-for="d in data['actions']" :key="d.reason">{{ d.reason }}</td>
                                                </tr>
                                                <tr>
                                                    <td class="sticky-col col8">Performance</td>
                                                    <td v-for="d in data['actions']" :key="d.performance">{{ d.performance }}</td>
                                                </tr>
                                                <tr>
                                                    <td class="sticky-col col8">Delay</td>
                                                    <td v-for="d in data['actions']" :key="d">
                                                        {{get_cumulative_delay(d.actual_date, d.date)}}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td class="sticky-col col8">Cumulative Delay</td>
                                                    <td v-for="d in data['actions']" :key="d">
                                                        {{ d.delay }}
                                                    </td>
                                                </tr>
                                            </template>
                                        </tbody>
                                    </table>
                                </div>
                            </div>    
                        </div>
                    </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted} from 'vue';

let date = null;
let lot = null;
let item = null;
let root = ref(null);
let sample_doc = ref({});
let items = ref([])
let show_table = ref(true)

onMounted(() => {
    let el = root.value;
    $(el).find(".report-date").html("");
    date = frappe.ui.form.make_control({
        parent: $(el).find(".report-date"),
        df: {
            fieldname: "report_date",
            fieldtype: "Date",
            label: "Report Date",
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
    let date_value = date.get_value()
    if(!date_value){
        date_value = null
    }
    show_table.value = false
    frappe.call({
        method: "production_api.utils.get_t_and_a_review_report_data",
        args: {
            "lot":lot.get_value(),
            "item": item.get_value(),
            "report_date": date_value,
        },
        callback: function(r){
            items.value = r.message
            show_table.value = true
        }
    })
}

function get_cumulative_delay(actual, planned){
    if(actual && planned){
        actual = new Date(actual)
        planned = new Date(planned)
        let diff = new Date(actual - planned).getDate()
        return diff - 1
    }
    return 0
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
.scroll-container1 {
    width: 100%;
    overflow-x: hidden;
    border: 1px solid #ddd;
    position: relative;
    height:700px;
    overflow-y: scroll;
}

.scroll-container2 {
    width: 100%;
    max-height: 700px;
    overflow: auto;
    position: relative;
}

.inner-table {
    min-width: 3200px;
}

.inner-table thead th.sticky-col {
  position: sticky;
  top: 0;
  z-index: 5;
  background: white;
}

.inner-table th, .inner-table td, .inner-table thead, .inner-table tbody{
    text-align: center;
    word-wrap: break-word; 
    border: 1px solid black;
}

.inner-table tr{
    border: 1px solid black;
}

.inner-table th{
    background-color: #D3D3D3;
}

.lot-title {
    width: fit-content;
    position: sticky;
    z-index: 3;
    left: 0;
    background: white;
    padding: 10px;
}

table td {
  padding: 0px;
}

.inner-table thead {
    position: sticky;
    top: 0;
    z-index: 5;
    background: white; 
}

.sticky-col {
    border: 1px solid black;
    position: sticky;
    background: white;
    z-index: 1;
    border-right: 1px solid black;
    box-shadow: 2px 0 5px -2px black;
}

.col1 { left: 0;     box-shadow: inset 0 0 0 0.05rem black; width: 60px; }
.col2 { left: 60px;  box-shadow: inset 0 0 0 0.05rem black; width: 150px; }
.col3 { left: 210px; box-shadow: inset 0 0 0 0.05rem black; width: 100px;}
.col4 { left: 310px; box-shadow: inset 0 0 0 0.05rem black; width: 150px;}
.col5 { left: 460px; box-shadow: inset 0 0 0 0.05rem black; width: 80px; }
.col6 { left: 540px; box-shadow: inset 0 0 0 0.05rem black; width: 100px; }
.col7 { left: 640px; box-shadow: inset 0 0 0 0.05rem black; width: 110px; } 
.col8 { left: 750px; box-shadow: inset 0 0 0 0.05rem black; width: 150px; } 

</style>
