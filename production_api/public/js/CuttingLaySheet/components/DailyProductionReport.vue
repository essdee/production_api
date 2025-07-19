<template>
    <div ref="root" style="padding: 15px;">
        <h3>Daily Production Report</h3>
        <div style="padding:15px;display:flex;">
            <div class="date-input col-md-2"></div>
            <div style="padding-top: 27px;">
                <button class="btn btn-primary" @click="get_report()">Get Report</button>
            </div>
        </div>
        <div v-for="key in Object.keys(items)" :key="key" style="padding-left:20px;">
            <h4>{{ key }}</h4>
            <CuttingCompletionDetail :data="items[key]"/>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import CuttingCompletionDetail from '../../CuttingPlan/components/CuttingCompletionDetail.vue';

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