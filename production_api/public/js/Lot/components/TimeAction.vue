<template>
    <div>
        <div v-if="items && items.length > 0">
            <div style="display:flex;width:100%; justify-content: space-between;">
                <h4>Time and Action Summary</h4>
                <div style="display:flex; justify-content: space-between; gap: 0.75rem; ">
                    <button v-if="show_button" class="btn btn-success" @click="update_all()">Update All</button>
                    <button class="btn btn-success" @click="update_work_station()">Update Work Station</button>
                    <button v-if="version=='V1'" class="btn btn-success" @click="update_allocated_days()">Update Allocated Days</button>
                </div>
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
                    <td>{{ check_action(i.action) }}</td>
                    <td>{{ i.department }}</td>
                    <td>{{ date_format(i.date) }}</td>
                    <td>{{ date_format(i.rescheduled_date) }}</td>
                    <td v-if="i.process"><button class="btn btn-success" @click="make_popup(index,i.colour, i.action)">Update</button></td>
                </tr>
            </table>
        </div>
    </div>    
</template>
<script setup>
import {ref} from 'vue';
import WorkStation from './WorkStation.vue';
import WorkStationV2 from './WorkStationV2.vue';
import { createApp } from 'vue';

let items = ref([])
let version = cur_frm.doc.version
let is_set_item = ref(cur_frm.doc.is_set_item)
let set_item_attribute = ref(cur_frm.doc.set_item_attribute)
let changed = ref(false)
let show_button = ref(false)
let cur_action = ref(null)
let dates = ref([])
let duplicate_value = ref(null)

function load_data(item){
    items.value = item
    duplicate_value.value = item
}

async function get_data(){
    return new Promise((resolve) => {
        resolve({
            "items" : items.value,
            "changed" : changed.value,
        })
    })
}

function update_allocated_days(){
    let d = new frappe.ui.Dialog({
        title: "Update Allocated Days",
        size: "extra-large",
        fields: [
            {
                "fieldname": "allocation_days_html",
                "fieldtype": "HTML"
            }
        ],
        primary_action_label: "Check and Update Days",
        primary_action(){
            frappe.call({
                method: "production_api.essdee_production.doctype.lot.lot.update_and_unallocate_workstation",
                args: {
                    data: dialog_html.get_data(),
                },
                callback: function(){
                    d.hide()
                }
            })
        }
    })
    d.show()
    d.fields_dict.allocation_days_html.$wrapper.html("")
    let dialog_html = new frappe.production.ui.UpdateAllocationDays(d.fields_dict.allocation_days_html.wrapper);
    dialog_html.load_data(items.value)
}

function date_format(date){
    if(date){
        let arr = date.split("-")
        return arr[2]+"-"+arr[1]+"-"+arr[0]
    }
}

function check_action(action){
    if(cur_action.value == null){
        cur_action.value = action
        show_button.value = true
    }
    else{
        if(action != cur_action.value){
            show_button.value = false
        }
    }
    return action
}

function update_all(){
    items.value.forEach((row)=> {
        dates.value.push(row.rescheduled_date)
    })

    let dialog = new frappe.ui.Dialog({
        title : `Update ${cur_action.value} for all`,
        fields : [
            {
                "fieldname" : "actual_date",
                "fieldtype" : "Date",
                "label" : "Actual Date",
            },
            {
                "fieldname" : "reason",
                "fieldtype" : "Data",
                "label" : "Reason"
            },
        ],
        async primary_action(values){
            let cp = await frappe.db.get_value("Action", cur_action.value, "capacity_planning")
            if(!values.reason){
                for(let i = 0 ; i < dates.value.length ; i++){
                    if(dates.value[i] < values.actual_date){
                        frappe.throw("Enter the Reason")
                    }
                }
            }
            let reason = values.reason
            if(!reason){
                reason = null
            }
            items.value.forEach((row)=> {
                row['actual_date'] = values.actual_date
                row['reason'] = reason    
                changed.value = true
                dialog.hide()
            })
            cur_frm.dirty()
            cur_frm.save()
        }
    })
    dialog.show()
}

function make_popup(index, colour, action){
    let d =new frappe.ui.Dialog({
        title:`On ${colour}, Update Actual Date for ${action}`,
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
            "lot": cur_frm.doc.name,
        },
        callback :async function(r){
            let d = new frappe.ui.Dialog({
                size : "extra-large",
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
                            datas : updated_ws,
                            version: cur_frm.doc.version
                        },
                        callback: function(){
                            cur_frm.refresh()
                        }
                    })
                },
            });
            d.fields_dict.html_field.$wrapper.empty();
            let module = WorkStation
            if(cur_frm.doc.version == "V2"){
                module = WorkStationV2
            }
            const vueApp = createApp(module); 
            const app = vueApp.mount(d.fields_dict.html_field.$wrapper[0]);
            await app.load_data(r.message,"update")
            if(cur_frm.doc.version == "V1"){
                app.set_attributes()
            }
            d.show();
        }
    })
}

defineExpose({
    load_data,
    get_data,
})

</script>