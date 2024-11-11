<template>
    <div ref="root">
        <div class="select-field col-md-6"></div>
        <table v-if="items && items.length > 0 " class="table table-sm table-bordered">
            <tr>
                <th>S.No</th>
                <th>Action</th>
                <th>Department</th>
                <th>Lead Time</th>
                <th>Date</th>
                <th>Rescheduled Date</th>
                <th>Actual Date</th>
                <th>Date Diff</th>
                <th>Reason</th>
                <th>Performance</th>
            </tr>
            <tr v-for="(i,index) in items" :key="index">
                <td>{{ index + 1 }}</td>
                <td>{{ i.action }}</td>
                <td>{{ i.department }}</td>
                <td>{{ i.lead_time }}</td>
                <td>{{ i.date }}</td>
                <td>{{ i.rescheduled_date }}</td>
                <td>{{ i.actual_date }}</td>
                <td>{{ i.date_diff }}</td>
                <td>{{ i.reason }}</td>
                <td>{{ i.performance }}</td>
            </tr>
        </table>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const root = ref(null);
const items = ref([]);
const colours = ref([]);
const select_field = ref(null);
const sample_doc = ref({});
const docnames = {};

onMounted(() => {
    cur_frm.doc.lot_time_and_action_details.forEach(detail => {
        colours.value.push(detail.colour);
        docnames[detail.colour] = detail.time_and_action;
    });

    const el = root.value;
    $(el).find(".select-field").html("")

    select_field.value = frappe.ui.form.make_control({
        parent: $(el).find(".select-field"),
        df: {
            fieldtype: "Select",
            fieldname: "select_field",
            label: "Select Colour",
            options: colours.value,
            onchange: () => {
                frappe.call({
                    method:"production_api.essdee_production.doctype.lot.lot.get_time_and_action_details",
                    args: {
                        docname: docnames[select_field.value.get_value()]
                    },
                    callback:function(r){
                        items.value = r.message
                    }
                })
            }
        },
        doc: sample_doc.value,
        render_input: true,
    });
});
</script>
