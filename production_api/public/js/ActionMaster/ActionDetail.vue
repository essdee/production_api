<template>
    <div ref="root">
        <div v-if="items && items.length > 0">
            <table class="table table-sm table-bordered">
                <thead>
                    <tr>
                        <th>S.No</th>
                        <th>Action</th>
                        <th>Lead Time</th>
                        <th>Department</th>
                        <th>Dependent Actions</th>
                        <th>Merge Process</th>
                        <th>One Colour Process</th>
                        <th v-if="!preview">Edit</th>
                    </tr>
                </thead>
                <tbody v-if="preview">
                    <tr v-for="(row, index) in items">
                        <td>{{ index + 1 }}</td>
                        <td>{{ row.action }}</td>
                        <td>
                            <input type="number" step="1" v-model="row.lead_time" class="form-control"/>
                        </td>
                        <td>{{ row.department }}</td>
                        <td>
                            <div v-for="action in row.dependent_action" :key="action">{{ action }}<br></div>
                        </td>
                        <td>
                            <span v-if="row.check_value">✅</span>
                        </td>
                        <td>
                            <span v-if="row.one_colour_process">✅</span>
                        </td>
                    </tr>
                </tbody>
                <draggable v-else v-model="items" tag="tbody" item-key="action" handle=".drag-handle"
                    animation="200" ghost-class="drag-ghost" @end="save_new_order">
                    <template #item="{ element, index }">
                        <tr>
                            <td>
                                <span class="drag-handle" style="cursor: grab;">☰</span>
                                {{ index + 1 }}
                            </td>
                            <td>{{ element.action }}</td>
                            <td>{{ element.lead_time }}</td>
                            <td>{{ element.department }}</td>
                            <td>
                                <div v-for="action in element.dependent_action" :key="action">{{ action }}<br></div>
                            </td>
                            <td>
                                <span v-if="element.check_value">✅</span>
                            </td>
                            <td>
                                <span v-if="element.one_colour_process">✅</span>
                            </td>
                            <td style="display: flex;">
                                <div class="cursor-pointer" @click="edit_item(index)" v-html="frappe.utils.icon('edit', 'md')"></div>
                                <div class="cursor-pointer" @click="delete_item(index)" v-html="frappe.utils.icon('delete', 'md')"></div>
                            </td>
                        </tr>
                    </template>
                </draggable>
            </table>
        </div>
        <div v-if="!preview">
            <div v-if="!show_div">
                <button @click="add_action()" class="btn btn-success">Add Action</button>
            </div>
            <div v-if="show_div">
                <div class="row pl-3">
                    <div class="cur-action col-md-2"></div>
                    <div class="col-md-4" v-if="in_edit">
                        Dependent Actions
                        <MultiSelect :options="prev_options" :setDefault="true" :item_key="1" 
                        :defaultList="default_list" :triggerEvent="update_selected"/>
                    </div>
                    <div class="col-md-4" v-else>
                        Dependent Actions
                        <MultiSelect :options="prev_options" :setDefault="false" :item_key="1" 
                        :defaultList="[]" :triggerEvent="update_selected"/>
                    </div>
                    <div class="lead-time col-md-2"></div>
                    <div class="department-val col-md-2"></div>
                    <div style="margin-top:20px;" class="merge-check col-md-1"></div>
                    <div style="margin-top: 20px;" class="one-colour-check col-md-1"></div>
                </div>
                <div style="display: flex;">
                    <div>
                        <button class="btn btn-success" @click="add_items()">
                            <span v-if="in_edit">Update</span><span v-else>Add</span>
                        </button>
                    </div>
                    <div style="padding-left:20px;">
                        <button class="btn btn-success" @click="close()">Close</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>

import draggable from 'vuedraggable'
import { ref, nextTick } from "vue";
import MultiSelect from "../components/MultiSelect.vue";

let items = ref([])
let show_div = ref(false)
let action = null
let lead_time = null
let department = null
let root = ref(null)
let sample_doc= ref({})
let prev_options = []
let prev_options_list = []
let cur_selected = []
let in_edit = ref(false)
let default_list = ref([])
let edit_index = ref(null) 
let check_value = null
let one_colour = null
let preview = ref(false)

function save_new_order() {
    make_dirty()
}


function load_data(data, prev_options_value, is_preview=false){
    items.value = data
    console.log(items.value)
    console.log(is_preview)
    preview.value = is_preview
    prev_options = prev_options_value
    for(opt of prev_options_value){
        prev_options_list.push(opt['option'])
    }
}

function delete_item(idx){
    let del_act = items.value[idx]['action']
    prev_options_list = []
    prev_options = []
    for(row of items.value){
        if(row['action'] != del_act){
            prev_options.push({
                "option": row['action'],
                "id": row['action'],
            })
            prev_options_list.push(row['action'])
        }
        let dependent = []
        for(act of row['dependent_action']){
            if (act != del_act){
                dependent.push(act)
            }
        }
        row['dependent_action'] = dependent
    }
    nextTick(()=> {
        items.value.splice(idx, 1)
        make_dirty()
    })
}

function edit_item(idx){
    in_edit.value = true
    edit_index.value = idx
    for(action of items.value[idx]['dependent_action']){
        default_list.value.push(action)
    }
    nextTick(()=> {
        add_action(idx)
    })
}

async function get_action_data(){
    if (!action){
        return
    }
    if(edit_index.value && edit_index.value >= 0){
        return
    }
    let val = action.get_value()
    if(val && val != "" && val != null){
        let d = await frappe.db.get_value("Action", val, ["department", "lead_time"])
        department.set_value(d.message.department)
        lead_time.set_value(d.message.lead_time)
    }
}

function add_action(index=null){
    show_div.value = true
    nextTick(() => {
        action = get_input_field(".cur-action", "Link", "action", "Action", "Action", true, change=get_action_data);
        lead_time = get_input_field(".lead-time", "Int", "lead_time", "Lead Time", null, true);
        department = get_input_field(".department-val", "Link", "department", "Department", "Department", true);
        check_value = get_input_field(".merge-check", "Check", "merge_action", "Merge Action", null, true)
        one_colour = get_input_field(".one-colour-check", "Check", "one_colour_process", "One Colour Process", null, true)
        if(index == 0 || index){
            action.set_value(items.value[index]['action'])
            lead_time.set_value(items.value[index]['lead_time'])
            department.set_value(items.value[index]['department'])
            cur_selected = items.value[index]['dependent_action']
            check_value.set_value(items.value[index]['check_value'])
            one_colour.set_value(items.value[index]['one_colour_process'])
        }
    });
}

function close(){
    edit_index.value = null
    show_div.value = false
    clear_values()
    make_dirty()
}

function get_input_field(classname, fieldtype, fieldname, label, options, reqd, change=null){
    let el = root.value
    $(el).find(classname).html("");
    let df = {
        fieldtype: fieldtype,
        fieldname: fieldname,
        label: label,
        reqd:reqd,
    }
    if(options){
        df['options'] = options
    }  
    if(change){
        df['onchange'] = change
    }
    return frappe.ui.form.make_control({
        parent: $(el).find(classname),
        df: df,
        doc: sample_doc.value,
        render_input: true,
    });
}

function add_items(){
    show_div.value = false
    let action_value = action.get_value()
    if(!prev_options_list.includes(action_value)){
        prev_options.push({
            "option": action_value,
            "id": action_value,
        })
        prev_options_list.push(action_value)
    }
    if(edit_index.value == 0 || edit_index.value){
        items.value[edit_index.value] = {
            "action": action_value,
            "dependent_action": cur_selected,
            "lead_time": lead_time.get_value(),
            "department": department.get_value(),
            "check_value": check_value.get_value(),
            "one_colour_process": one_colour.get_value(),
        }
        edit_index.value = null
        default_list.value = []
    }
    else{
        items.value.push({
            "action": action_value,
            "dependent_action": cur_selected,
            "lead_time": lead_time.get_value(),
            "department": department.get_value(),
            "check_value": check_value.get_value(),
            "one_colour_process": one_colour.get_value(),
        })
    }
    clear_values()
    make_dirty()
}

function clear_values(){
    action.set_value(null)
    lead_time.set_value(null)
    department.set_value(null)
    check_value.set_value(0)
}

function update_selected(selected_vals, idx){
    selected_vals = selected_vals.map((item) => {
        return item.option
    })
    cur_selected = selected_vals
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function get_items(){
    return items.value
}

defineExpose({
    load_data,
    get_items,
})

</script>

<style scoped>
.drag-ghost {
    opacity: 0.6;
    background: #f0f0f0;
  }
  
  .drag-handle {
    cursor: grab;
    margin-right: 6px;
  }
  
</style>
