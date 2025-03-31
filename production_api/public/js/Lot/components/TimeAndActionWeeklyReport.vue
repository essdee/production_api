<template>
    <div ref="root">
        <div class="row pb-4">
            <div class="report-date col-md-4"></div>
            <div class="lot-name col-md-4"></div>
            <div class="item-name col-md-4"></div>
            <button class="btn btn-success ml-3" @click="get_filters()">Show Report</button>
        </div>

        <div class="scroll-container" v-if="show_table">
            <div v-for="lot in Object.keys(items)" :key="lot">
                <table class="outer-table">
                    <tr v-for="master in Object.keys(items[lot])" :key="master">
                        <td>
                            <span class="lot-title">{{ lot }} ({{ master }})</span>
                            <table class="inner-table">
                                <thead>
                                    <tr>
                                        <th style="width:70px;">S.No</th>
                                        <th style="width:100px;">Item</th>
                                        <th style="width:100px;">Colour</th>
                                        <th style="width:150px;">Sizes</th>
                                        <th style="width:100px;">Quantity</th>
                                        <th style="width:100px;">Start Date</th>
                                        <th style="width:60px;">Delay</th>
                                        <th style="width:200px;">Activity</th>
                                        <th v-for="action in items[lot][master]['actions']" :key="action">
                                            {{ action }}
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <template v-for="(data, idx) in items[lot][master]['datas']" :key="data">
                                        <tr>
                                            <td rowspan="8">{{ idx + 1 }}</td>
                                            <td rowspan="8">{{ data.item }}</td>
                                            <td rowspan="8">{{ data.colour }}</td>
                                            <td rowspan="8">{{ data.sizes }}</td>
                                            <td rowspan="8">{{ data.qty }}</td>
                                            <td rowspan="8">{{ get_date(data.start_date) }}</td>
                                            <td rowspan="8">{{ data.delay }}</td>
                                        </tr>
                                        <tr>
                                            <td>Planned Date</td>
                                            <td v-for="d in data['actions']" :key="d.date">{{ get_date(d.date) }}</td>
                                        </tr>
                                        <tr>
                                            <td>Rescheduled Date</td>
                                            <td v-for="d in data['actions']" :key="d.rescheduled_date">{{ get_date(d.rescheduled_date) }}</td>
                                        </tr>
                                        <tr>
                                            <td>Actual</td>
                                            <td v-for="d in data['actions']" :key="d.actual_date" :style="{ backgroundColor: d.actual_date > d.rescheduled_date ? '#FFCCCB' : d.actual_date ? '#90EE90' : 'White'}">
                                                {{ get_date(d.actual_date) }}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td>Reason for Delay</td>
                                            <td v-for="d in data['actions']" :key="d.reason">{{ d.reason }}</td>
                                        </tr>
                                        <tr>
                                            <td>Performance</td>
                                            <td v-for="d in data['actions']" :key="d.performance">{{ d.performance }}</td>
                                        </tr>
                                        <tr>
                                            <td>Delay</td>
                                            <td v-for="d in data['actions']" :key="d">
                                                {{get_cumulative_delay(d.actual_date, d.date)}}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td>Cumulative Delay</td>
                                            <td v-for="d in data['actions']" :key="d">
                                                {{ d.delay }}
                                            </td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

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
    const container = document.querySelector('.scroll-container');
    const headers = container.querySelectorAll('.inner-table thead');

    container.addEventListener('scroll', () => {
        let lastHeader = null;

        headers.forEach((header) => {
            const { top } = header.getBoundingClientRect();
            if (top <= 0 && top > -header.clientHeight) {
                lastHeader = header;
            }
        });

        headers.forEach((header) => {
            header.style.zIndex = header === lastHeader ? '2' : '1';
        });
    });
});

function get_filters() {
    let date_value = date.get_value()
    if(!date_value){
        date_value = null
    }
    show_table.value = false
    frappe.call({
        method: "production_api.essdee_production.doctype.time_and_action_weekly_review_report.time_and_action_weekly_review_report.get_report_data",
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
.scroll-container {
    max-height: 700px;
    overflow-y: auto; 
    border: 1px solid #ddd; 
    overflow-x: auto;
    position: relative;
}

.outer-table {
    width: 100%;
    border-collapse: collapse;
}

.inner-table {
    width: 100%;
    min-width: 3200px;
    table-layout: fixed; 
    border-collapse: collapse;
}

.inner-table th, .inner-table td {
    text-align: center;
    word-wrap: break-word; 
    border: 1px solid black;
}

.inner-table th{
    background-color: #D3D3D3;
}

.lot-title {
    padding-left: 10px;
    font-size: 25px;
    font-weight: 600;
    display: inline-block;
    width: 100%;
}

table td {
  padding: 0px;
}

.inner-table thead {
    position: sticky;
    top: 0;
    z-index: 2;
    background: white; 
}

</style>
