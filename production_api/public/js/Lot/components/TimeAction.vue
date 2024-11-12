<template>
    <div>
        <div v-if="items && items.length > 0">
            <h4>Time and Action Summary</h4>
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

let items = ref([])
let is_set_item = ref(cur_frm.doc.is_set_item)
let set_item_attribute = ref(cur_frm.doc.set_item_attribute)

function load_data(item){
    items.value = item
}

function get_data(){
    return items.value
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
                    cur_frm.dirty()
                    cur_frm.save()
                    d.hide()
                }
            }
            else{
                items.value[index]['actual_date'] = values.actual_date
                cur_frm.dirty()
                cur_frm.save()
                d.hide()
            }
        }
    })
    d.show()
}

defineExpose({
    load_data,
    get_data,
})

</script>