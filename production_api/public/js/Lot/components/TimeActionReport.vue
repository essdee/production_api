<template>
    <div ref="root">
        <div v-if="items && items.length > 0">
            <h4>Report</h4>
        </div>
        <div class="row">
            <div class="select-field col-md-5"></div>
            <div class="col-md-4"></div>
            <div v-if="selected_colour && status != 'Completed'" class="col-md-3 mt-4">
                <button @click="undo_last_update()" class="btn btn-success" style="margin-right: 10px;">Undo Last</button>
                <button @click="make_complete()" class="btn btn-success">Complete T&A</button>
            </div>
        </div>
        <table v-if="items && items.length > 0" class="table table-sm table-bordered">
            <tr>
                <th>S.No</th>
                <th>Action</th>
                <th>Department</th>
                <th>Lead Time</th>
                <th>Work Station</th>
                <th>Planned Date</th>
                <th>Rescheduled Date</th>
                <th>Actual Date</th>
                <th>Date Diff</th>
                <th>Reason</th>
                <th>Performance</th>
            </tr>
            <tr v-for="(i, index) in items" :key="index">
                <td>{{ index + 1 }}</td>
                <td>{{ i.action }}</td>
                <td>{{ i.department }}</td>
                <td>{{ i.lead_time }}</td>
                <td v-if="i.work_station">
                    {{ i.work_station }}
                </td>
                <td v-else></td>
                <td>{{ date_format(i.date) }}</td>
                <td>{{ date_format(i.rescheduled_date) }}</td>
                <td :class="{'bg-red': i.rescheduled_date < i.actual_date, 'bg-green': i.rescheduled_date >= i.actual_date}">
                    {{ date_format(i.actual_date) }}
                </td>
                <td>{{ i.date_diff }}</td>
                <td>{{ i.reason }}</td>
                <td>{{ i.performance }}%</td>
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
let docname = ref(null)
let selected_colour = ref(null)
let status = ref(null)

onMounted(() => {
    cur_frm.doc.lot_time_and_action_details.forEach(detail => {
        colours.value.push(detail.colour);
        docnames[detail.colour] = detail.time_and_action;
    });
    const el = root.value;
    $(el).find(".select-field").html("");
    let label = "Select Colour"
    if(cur_frm.doc.is_set_item){
        label = label +" - "+cur_frm.doc.set_item_attribute
    }
    select_field.value = frappe.ui.form.make_control({
        parent: $(el).find(".select-field"),
        df: {
            fieldtype: "Select",
            fieldname: "select_field",
            label: label,
            options: colours.value,
            onchange: () => {
                frappe.call({
                    method: "production_api.essdee_production.doctype.lot.lot.get_time_and_action_details",
                    args: {
                        docname: docnames[select_field.value.get_value()]
                    },
                    callback: function (r) {
                        items.value = r.message.item_list;
                        status.value = r.message.status
                        docname.value = docnames[select_field.value.get_value()];
                        selected_colour.value = select_field.value.get_value();
                    }
                });
            }
        },
        doc: sample_doc.value,
        render_input: true,
    });
});

function undo_last_update(){
    let d = new frappe.ui.Dialog({
        title:`Are you sure want to undo the last update on ${selected_colour.value}`,
        primary_action_label:"Yes",
        secondary_action_label:"No",
        primary_action(){
            frappe.call({
                method:"production_api.essdee_production.doctype.lot.lot.undo_last_update",
                args: {
                    "time_and_action":docname.value,
                },
                callback:function(){
                    d.hide()
                    cur_frm.dirty()
                    cur_frm.save()
                }
            })
        },
        secondary_action(){
            d.hide()
        }
    })
    d.show()
}

function make_complete(){
    frappe.call({
        method:"production_api.essdee_production.doctype.lot.lot.make_complete",
        args: {
            "time_and_action":docname.value,
        },
        callback:function(){
            cur_frm.dirty()
            cur_frm.save()
        }
    })
}

function date_format(date){
    if(date){
        let arr = date.split("-")
        return arr[2]+"-"+arr[1]+"-"+arr[0]
    }
}
</script>
<style scoped>
.bg-red {
    background-color: #f8d7da;
    color: #721c24;
}
.bg-green {
    background-color: #d4edda;
    color: #155724;
}
</style>
