<template>
    <div ref="root" style="padding: 15px;">
        <h3 style="text-align:center;padding-top:15px;">Daily Cut Sheet Report</h3>
        <div style="padding:15px;display:flex;">
            <div class="date-input col-md-2"></div>
            <div class="select-field col-md-2"></div>
            <div style="padding-top: 27px;">
                <button class="btn btn-primary" @click="get_report()">Get Report</button>
            </div>
        </div>
        <div v-if="report">
            <div v-if="items">
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
                                    </tr>
                                    <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                        <td>{{item1_index + 1}}</td>
                                        <td v-for="(k, idx) in i.attributes" :key="idx">
                                            {{j.attributes[k]}}
                                            <span v-if="k == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                            <span v-else-if="k == 'Colour' && !j.is_set_item && j.attributes[k] != j.item_keys['major_colour'] && j.attributes[k]">({{ j.item_keys['major_colour'] }})</span>
                                        </td>
                                        <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                            <div v-for="(panel,idx2) in Object.keys(j.values[k])" :key='idx2'>
                                                <span v-if="j.values[k][panel] > 0">
                                                    {{panel}} {{j.values[k][panel]}}
                                                </span>
                                            </div>
                                        </td>
                                        <td>
                                            <div v-for="(panel,idx2) in Object.keys(j.total_panel_qty)" :key='idx2'>
                                                {{panel}} {{j.total_panel_qty[panel]}}
                                            </div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </div>
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
import { ref, onMounted } from 'vue';

const root = ref(null);
const sample_doc = ref({})
let date_filter = ref(null)
let cutting_location = ref(null)
let items = ref({});
let report = ref(true)

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
    })
});

function get_report(){
    if (!date_filter.value.get_value()) {
        frappe.msgprint(__('Please select a date'));
        return;
    }
    frappe.call({
        method: 'production_api.utils.get_cut_sheet_report',
        args: {
            date: date_filter.value.get_value(),
            location: cutting_location.value.get_value(),
        },
        freeze: true,
        freeze_message: "Fetching Cut Sheet Report",
        callback: function (r) {
            if (r.message) {
                if(r.message.length > 0){
                    report.value = true
                }
                else{
                    report.value = false
                }
                items.value = r.message;
            } 
            else {
                frappe.msgprint('No data found for the selected date');
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
