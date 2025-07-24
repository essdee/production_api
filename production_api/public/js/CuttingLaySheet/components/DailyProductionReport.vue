<template>
    <div ref="root" style="padding: 15px;">
        <h3>Daily Production Report</h3>
        <div style="padding:15px;display:flex;">
            <div class="date-input col-md-2"></div>
            <div style="padding-top: 27px;">
                <button class="btn btn-primary" @click="get_report()">Get Report</button>
            </div>
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
</template>

<script setup>
import { ref, onMounted } from 'vue';

const root = ref(null);
const sample_doc = ref({})
let date_filter = ref(null)
let items = ref({});

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
});

function get_report(){
    if (!date_filter.value.get_value()) {
        frappe.msgprint(__('Please select a date'));
        return;
    }
    frappe.call({
        method: 'production_api.utils.get_daily_production_report',
        args: {
            date: date_filter.value.get_value(),
        },
        callback: function (r) {
            if (r.message) {
                items.value = r.message;
            } 
            else {
                frappe.msgprint('No data found for the selected date');
            }
        }
    });
}

</script>