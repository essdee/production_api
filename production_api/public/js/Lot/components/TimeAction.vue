<template>
    <div>
        <div v-if="items && items.length > 0">
            <div style="display:flex;width:100%;">
                <h4 style="width:85%;">Time and Action Summary</h4>
                <button class="btn btn-success" style="width:15%;" @click="update_work_station()">Update Work Station</button>
            </div>
            <table class="table table-sm table-bordered">
                <tr>
                    <th>S.No</th>
                    <th v-if="is_set_item">Colour - {{set_item_attribute}}</th>
                    <th v-else>Colour</th>
                    <th>Action</th>
                    <th>Department</th>
                    <th>Planned Date</th>
                    <th>Rescheduled Date</th>
                    <th></th>
                </tr>
                <tr v-for="(i,index) in items" :key="i">
                    <td>{{ index + 1}}</td>
                    <td>{{ i.colour }}</td>
                    <td>{{ i.action }}</td>
                    <td>{{ i.department }}</td>
                    <td>{{ date_format(i.date) }}</td>
                    <td>{{ date_format(i.rescheduled_date) }}</td>
                    <td v-if="i.process"><button class="btn btn-success" @click="make_popup(index)">Update</button></td>
                </tr>
            </table>
        </div>
    </div>    
</template>
<script setup>
import {ref} from 'vue';
import WorkStation from './WorkStation.vue';
import { createApp } from 'vue';

let items = ref([])
let is_set_item = ref(cur_frm.doc.is_set_item)
let set_item_attribute = ref(cur_frm.doc.set_item_attribute)
let changed = ref(false)

function load_data(item){
    items.value = item
}

function get_data(){
    return {
        "items" : items.value,
        "changed" : changed.value,
    }
}

function date_format(date){
    if(date){
        let arr = date.split("-")
        return arr[2]+"-"+arr[1]+"-"+arr[0]
    }
}

function make_popup(index){
    let d =new frappe.ui.Dialog({
        title:"Update Actual Date",
        fields:[
            {
                fieldtype:"Date",
                fieldname:"rescheduled_date",
                label:"Rescheduled Date",
                default:items.value[index]['rescheduled_date'],
            }, 
            {
                fieldtype:"Date",
                fieldname:"actual_date",
                label:"Actual Date",
            },
            {
                fieldtype:"Data",
                fieldname:"reason",
                label:"Reason"
            },
        ],
        primary_action(values){
            if(values.rescheduled_date < values.actual_date){
                if(values.reason == "" || values.reason == null){
                    frappe.msgprint("Enter the Reason")
                }
                else{
                    items.value[index]['actual_date'] = values.actual_date
                    items.value[index]['reason'] = values.reason    
                    changed.value = true
                    cur_frm.dirty()
                    cur_frm.save()
                    d.hide()
                }
            }
            else{
                items.value[index]['actual_date'] = values.actual_date
                if(values.reason){
                    items.value[index]['reason'] = values.reason
                }
                changed.value = true
                cur_frm.dirty()
                cur_frm.save()
                d.hide()
            }
        }
    })
    d.show()
}

function update_work_station(){
    frappe.call({
        method:"production_api.essdee_production.doctype.lot.lot.get_work_stations",
        args : {
            "items": items.value,
        },
        callback :async function(r){
            let d = new frappe.ui.Dialog({
                size : "large",
                title: "Update Work Station",
                fields: [
                    {
                        fieldname: "html_field",
                        fieldtype: "HTML",
                    },
                ],
                primary_action_label : "Update",
                primary_action: () => {
                    d.hide();
                    let updated_ws = app.get_items()
                    frappe.call({
                        method: "production_api.essdee_production.doctype.lot.lot.update_t_and_a_ws",
                        args : {
                            datas : updated_ws
                        },
                        callback: function(){
                            cur_frm.refresh()
                        }
                    })
                },
            });
            d.fields_dict.html_field.$wrapper.empty();
            const vueApp = createApp(WorkStation); 
            const app = vueApp.mount(d.fields_dict.html_field.$wrapper[0]);
            await app.load_data(r.message,"update")
            app.set_attributes()
            d.show();
        }
    })
}

defineExpose({
    load_data,
    get_data,
})

</script>