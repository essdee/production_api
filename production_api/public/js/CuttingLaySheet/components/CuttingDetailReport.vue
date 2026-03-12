<template>
    <div ref="root" style="padding: 15px;">
        <h3 style="text-align:center;padding-top:15px;">Cutting Detail Report</h3>
        <div style="padding:15px;display:flex;">
            <div class="start-date-input col-md-2"></div>
            <div class="end-date-input col-md-2"></div>
            <div class="select-field col-md-2"></div>
            <div style="padding-top: 27px;">
                <button class="btn btn-primary" @click="get_report()">Get Report</button>
            </div>
            <div style="padding-top: 27px;padding-left:10px;">
                <button class="btn btn-success" @click="take_screenshot()">Take Screenshot</button>
            </div>
        </div>
        <div v-if="report">
            <div style="padding-left:30px;">
                <h3>Bundle Generated - {{ bundle_generated }}</h3>
                <h3>Label Printed - {{ label_printed }}</h3>
                <h3>Created - {{ created }}</h3>
            </div>
            <div v-for="i in items" :key="i" style="padding-left:20px;">
                <h3> {{ i['style_no'] }} - {{ i['lot_no'] }} ({{i['location']}})</h3>
                <table class="table table-sm table-bordered">
                    <tr>
                        <td>
                            <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                                <tr>
                                    <th>S.No.</th>
                                    <th v-for="(j, idx) in i.attributes" :key="idx">{{ j }}</th>
                                    <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                        {{ j }}
                                    </th>
                                    <th>Total Qty</th>
                                    <th>Planned</th>
                                    <th>Cumulative Total</th>
                                    <th>Pending</th>
                                </tr>
                                <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <td>{{item1_index + 1}}</td>
                                    <td v-for="(k, idx) in i.attributes" :key="idx">
                                        {{j.attributes[k]}}
                                        <span>
                                            <span v-if="k == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                            <span v-else-if="k == 'Colour' && !j.is_set_item && j.attributes[k] != j.item_keys['major_colour'] && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                        </span>
                                    </td>
                                    <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                        <div v-if="j.values[k] > 0">
                                            {{ j.values[k] }}
                                            <div
                                                v-for="p in j.values1[k]"
                                                :key="p.panel"
                                                class="panel-pill"
                                            >
                                                {{ p.panel }} – {{ p.qty }}
                                            </div>
                                        </div>
                                        <div v-else>--</div>
                                    </td>
                                    <th>{{ j['total_qty'] }}</th>
                                    <th>{{ j['planned'] }}</th>
                                    <th>{{ j['cumulative'] }}</th>
                                    <th>{{ j['cumulative'] - j['planned'] }}</th>
                                </tr>
                                <tr>
                                    <th>Total</th>
                                    <td v-for="(j, idx) in i.attributes" :key="idx"></td>
                                    <th v-for="(j, idx) in i.total_qty" :key="idx">{{j}}</th>
                                    <th>{{ i['total_sum'] }}</th>
                                    <th>{{ i['total_planned_sum'] }}</th>
                                    <th>{{ i['total_received_sum'] }}</th>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
            <div v-if="Object.keys(styleSummary).length > 0" style="padding-left:20px;padding-top:20px;">
                <h3 style="text-align:center;">Style Wise Summary</h3>
                <table class="table table-sm table-bordered" style="max-width:500px;margin:0 auto;">
                    <tr>
                        <th>S.No.</th>
                        <th>Style</th>
                        <th>Lot</th>
                        <th>Total Qty</th>
                    </tr>
                    <tr v-for="(row, idx) in styleSummaryRows" :key="idx">
                        <td>{{ idx + 1 }}</td>
                        <td>{{ row.style }}</td>
                        <td>{{ row.lot }}</td>
                        <th>{{ row.qty }}</th>
                    </tr>
                    <tr>
                        <th colspan="3">Grand Total</th>
                        <th>{{ grandTotal }}</th>
                    </tr>
                </table>
            </div>
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
import { ref, computed, onMounted } from 'vue';

const root = ref(null);
const sample_doc = ref({})
let start_date_filter = ref(null)
let end_date_filter = ref(null)
let cutting_location = ref(null)
let items = ref({});
let report = ref(true)
let bundle_generated = ref(0)
let label_printed = ref(0)
let created = ref(0)

const styleSummary = computed(() => {
    let summary = {};
    if (!items.value || !Array.isArray(items.value)) return summary;
    for (let i of items.value) {
        let key = `${i.style_no}||${i.lot_no}`;
        if (!summary[key]) {
            summary[key] = { style: i.style_no, lot: i.lot_no, qty: 0 };
        }
        summary[key].qty += i.total_sum || 0;
    }
    return summary;
});

const styleSummaryRows = computed(() => {
    return Object.values(styleSummary.value);
});

const grandTotal = computed(() => {
    return styleSummaryRows.value.reduce((sum, row) => sum + row.qty, 0);
});

function get_first_of_month() {
    let now = new Date();
    let y = now.getFullYear();
    let m = String(now.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}-01`;
}

onMounted(() => {
    let el = root.value
    start_date_filter.value = frappe.ui.form.make_control({
        parent: el.querySelector('.start-date-input'),
        df: {
            fieldtype: 'Date',
            label: 'Start Date',
            fieldname: 'start_date',
            reqd: 1,
            default: get_first_of_month(),
        },
        doc: sample_doc.value,
        render_input: true,
    });
    end_date_filter.value = frappe.ui.form.make_control({
        parent: el.querySelector('.end-date-input'),
        df: {
            fieldtype: 'Date',
            label: 'End Date',
            fieldname: 'end_date',
            reqd: 1,
            default: frappe.datetime.nowdate(),
        },
        doc: sample_doc.value,
        render_input: true,
    });
    cutting_location.value = frappe.ui.form.make_control({
        parent: el.querySelector('.select-field'),
        df: {
            fieldtype: 'Select',
            label: "Cutting Location",
            fieldname: "cutting_location",
            options: ['Machine Cutting', "Manual Cutting"]
        },
        doc: sample_doc.value,
        render_input: true,
    })
});

async function take_screenshot(){
    frappe.require("https://cdn.jsdelivr.net/npm/html2canvas-pro@1.5.8/dist/html2canvas-pro.min.js", async () => {
        let sourceDiv = document.getElementById("page-cutting-detail");
        html2canvas(sourceDiv, {
            scale: 1,
            useCORS: true,
            backgroundColor: null,
            logging: false,
            removeContainer: true
        }).then((canvas) => {
            let link = document.createElement("a");
            link.href = canvas.toDataURL("image/png");
            link.download = "cutting-detail-screenshot.png";
            link.click();
        });
    });
}


function get_report(){
    let start = start_date_filter.value.get_value();
    let end = end_date_filter.value.get_value();
    if (!start) {
        frappe.msgprint(__('Please select a start date'));
        return;
    }
    if (!end) {
        frappe.msgprint(__('Please select an end date'));
        return;
    }
    if (start > end) {
        frappe.msgprint(__('Start date must be before or equal to end date'));
        return;
    }
    frappe.call({
        method: 'production_api.utils.get_cutting_detail_report',
        args: {
            start_date: start,
            end_date: end,
            location: cutting_location.value.get_value(),
        },
        freeze: true,
        freeze_message: "Fetching Cutting Detail Report",
        callback: function (r) {
            if (r.message) {
                if(r.message.report_data.length > 0){
                    report.value = true
                }
                else{
                    report.value = false
                }
                items.value = r.message.report_data;
                bundle_generated.value = r.message.bundle_generated
                label_printed.value = r.message.label_printed
                created.value = r.message.created
            }
            else {
                frappe.msgprint('No data found for the selected date range');
            }
        }
    });
}

</script>
<style scoped>
.msg-box {
    padding: var(--padding-xl) var(--padding-md);
    text-align: center;
    color: var(--text-muted);
}
.no-border {
    border: none !important;
}
</style>
