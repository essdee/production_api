<template>
    <div ref="root" style="padding: 15px;">
        <h3 style="text-align:center;padding-top:15px;">Daily Production Report</h3>
        <div style="padding:15px;display:flex;flex-wrap:wrap;align-items:flex-start;">
            <div class="date-input col-md-2" v-show="!isSummaryMode"></div>
            <div class="item-input col-md-3" v-show="isSummaryMode"></div>
            <div class="lot-input col-md-3" v-show="isSummaryMode"></div>
            <div class="select-field col-md-2"></div>
            <div style="padding-top: 27px;">
                <button class="btn btn-primary" @click="get_report()">Get Report</button>
            </div>
            <div style="padding-top: 27px;padding-left:10px;">
                <button class="btn btn-success" @click="take_screenshot()">Take Screenshot</button>
            </div>
            <div style="padding-top: 30px;padding-left:15px;">
                <label style="cursor:pointer;font-weight:normal;display:flex;align-items:center;gap:6px;">
                    <input type="checkbox" v-model="isSummaryMode" @change="onSummaryToggle" />
                    Check Summary
                </label>
            </div>
        </div>

        <!-- Normal mode -->
        <div v-if="!isSummaryMode">
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
                                        <th>Today Total</th>
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

        <!-- Summary mode -->
        <div v-if="isSummaryMode">
            <div v-if="summaryData.length > 0">
                <div v-for="(dateGroup, dgIdx) in summaryData" :key="dgIdx" style="margin-bottom:30px;">
                    <h3 style="background:#f5f5f5;padding:10px 20px;border-left:4px solid #5e64ff;">
                        {{ formatDate(dateGroup.date) }}
                        <span style="font-size:14px;margin-left:20px;color:#666;">
                            Bundle Generated: {{ dateGroup.bundle_generated }} |
                            Label Printed: {{ dateGroup.label_printed }} |
                            Created: {{ dateGroup.created }}
                        </span>
                    </h3>
                    <div v-for="i in dateGroup.report_data" :key="i.style_no + i.lot_no" style="padding-left:20px;">
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
                                            <th>Today Total</th>
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
                </div>
            </div>
            <div v-else-if="summaryFetched">
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
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const root = ref(null);
const sample_doc = ref({})
let date_filter = ref(null)
let cutting_location = ref(null)
let items = ref({});
let report = ref(true)
let bundle_generated = ref(0)
let label_printed = ref(0)
let created = ref(0)

// Summary mode refs
let isSummaryMode = ref(false)
let summaryData = ref([])
let summaryFetched = ref(false)
let item_multiselect = ref(null)
let lot_multiselect = ref(null)

onMounted(() => {
    let el = root.value
    date_filter.value = frappe.ui.form.make_control({
        parent: el.querySelector('.date-input'),
        df: {
            fieldtype: 'Date',
            label: 'Date',
            fieldname: 'date',
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
    });
    item_multiselect.value = frappe.ui.form.make_control({
        parent: el.querySelector('.item-input'),
        df: {
            fieldtype: 'MultiSelectList',
            label: 'Item',
            fieldname: 'item',
            options: 'Item',
            get_data: function(txt) {
                return frappe.db.get_link_options('Item', txt);
            }
        },
        doc: sample_doc.value,
        render_input: true,
    });
    lot_multiselect.value = frappe.ui.form.make_control({
        parent: el.querySelector('.lot-input'),
        df: {
            fieldtype: 'MultiSelectList',
            label: 'Lot',
            fieldname: 'lot',
            options: 'Lot',
            get_data: function(txt) {
                return frappe.db.get_link_options('Lot', txt);
            }
        },
        doc: sample_doc.value,
        render_input: true,
    });
});

function formatDate(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    return `${parts[2]}-${parts[1]}-${parts[0]}`;
}

function onSummaryToggle() {
    report.value = false;
    items.value = {};
    summaryData.value = [];
    summaryFetched.value = false;
    if (item_multiselect.value) {
        item_multiselect.value.set_value([]);
    }
    if (lot_multiselect.value) {
        lot_multiselect.value.set_value([]);
    }
}

async function take_screenshot(){
    frappe.require("https://cdn.jsdelivr.net/npm/html2canvas-pro@1.5.8/dist/html2canvas-pro.min.js", async () => {
        let sourceDiv = document.getElementById("page-daily-production-rep");
        html2canvas(sourceDiv, {
            scale: 1,
            useCORS: true,
            backgroundColor: null,
            logging: false,
            removeContainer: true
        }).then((canvas) => {
            let link = document.createElement("a");
            link.href = canvas.toDataURL("image/png");
            link.download = "screenshot.png";
            link.click();
        });
    });
}


function get_report(){
    if (isSummaryMode.value) {
        let selItems = item_multiselect.value ? (item_multiselect.value.get_value() || []) : [];
        let selLots = lot_multiselect.value ? (lot_multiselect.value.get_value() || []) : [];
        if (selItems.length === 0 && selLots.length === 0) {
            frappe.msgprint(__('Please select at least one Item or Lot'));
            return;
        }
        frappe.call({
            method: 'production_api.utils.get_daily_production_summary_report',
            args: {
                items: JSON.stringify(selItems),
                lots: JSON.stringify(selLots),
                location: cutting_location.value.get_value(),
            },
            freeze: true,
            freeze_message: "Fetching Summary Report",
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    summaryData.value = r.message;
                    summaryFetched.value = true;
                } else {
                    summaryData.value = [];
                    summaryFetched.value = true;
                }
            }
        });
    } else {
        if (!date_filter.value.get_value()) {
            frappe.msgprint(__('Please select a date'));
            return;
        }
        frappe.call({
            method: 'production_api.utils.get_daily_production_report',
            args: {
                date: date_filter.value.get_value(),
                location: cutting_location.value.get_value(),
            },
            freeze: true,
            freeze_message: "Fetching Completion Report",
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
                    frappe.msgprint('No data found for the selected date');
                }
            }
        });
    }
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
