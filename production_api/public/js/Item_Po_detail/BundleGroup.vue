<template>
    <div>
        <table class="table table-sm table-bordered" v-if="grp_items.length > 0">
            <tr>
                <td>Panels</td>
                <td>Delete</td>
            </tr>
            <tr v-for="item in grp_items" :key="item">
                <td v-if="item.defaultList.length > 0">
                    <MultiSelect :options="item.options" :setDefault="true" :defaultList="item.defaultList" :triggerEvent="update_selected" :item_key="item['id']" :docstatus="docstatus"/>
                </td>
                <td v-else>
                    <MultiSelect :options="options" :setDefault="true" :defaultList="[]" :triggerEvent="update_selected" :item_key="item['id']"/>
                </td>
                <td>
                    <div class="cursor-pointer" @click="delete_group_item(item)" v-html="frappe.utils.icon('delete', 'md')"></div>
                </td>
            </tr>
        </table>
        <button style="margin-top:10px;" @click="add_groups()" class="btn btn-success">Add Groups</button>

    </div>    
</template>

<script setup>
import { ref, onMounted } from 'vue';
import MultiSelect from "../components/MultiSelect.vue";

let grp_items = ref([])
let options = ref([])
let grp_panel = null

onMounted(()=> {
    let panels = []
    for(let i = 0; i < cur_frm.doc.stiching_item_details.length; i++){
        panels.push(cur_frm.doc.stiching_item_details[i].stiching_attribute_value)
    }
    grp_panel = panels
    create_options(panels)
    load_data()
})

function create_options(panels){
    options = panels.map((panel, idx) => {
        return {
            "option": panel,
            "id": panel,
        }
    })
}

function add_groups(){
    grp_items.value.push({
        "options": grp_panel,
        "defaultList": [],
        "id": grp_items.value.length,
        "selected": [],
    })
}

function update_selected(selected_vals, idx){
    selected_vals = selected_vals.map((item) => {
        return item.option
    })
    grp_items.value[idx].selected = selected_vals
    make_dirty()
}

function delete_group_item(item){
    let x = grp_items.value
    x.splice(x.indexOf(item), 1)
    for(let i = 0; i < x.length; i++){
        x[i].id = i
    }
    grp_items.value = x
    make_dirty()
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function load_data(){
    if(!cur_frm.doc.__islocal){
        let t_options = []
        let items = []
        for(let i = 0; i < cur_frm.doc.stiching_item_details.length; i++){
            let p = cur_frm.doc.stiching_item_details[i].stiching_attribute_value
            t_options.push({ "option": p, "id": p })
        }
        let index = 0
        for(let i = 0; i < cur_frm.doc.cutting_marker_groups.length; i++){
            let panels = cur_frm.doc.cutting_marker_groups[i].group_panels.split(",")
            let default_list = [];
            for(let j = 0; j < panels.length ; j++){
                default_list.push(panels[j])
            }
            items.push({
                "id": index,
                "options": t_options,
                "setDefault":true,
                "defaultList": default_list,
                "selected": panels,
            })
            index += 1
        }
        grp_items.value = items
    }
}

function get_items(){
    let selected_panels = []
    for(let i = 0; i < grp_items.value.length ; i++){
        if(grp_items.value[i].selected.length > 0){
            for(let j = 0; j < grp_items.value[i].selected.length; j++){
                if(selected_panels.includes(grp_items.value[i].selected[j])){
                    frappe.throw("Panel " + grp_items.value[i].selected[j] + " is grouped multiple times")
                }
                selected_panels.push(grp_items.value[i].selected[j])
            }
        }
    }
    if(selected_panels.length != 0 && selected_panels.length != cur_frm.doc.stiching_item_details.length){
        frappe.throw("Select All the Panels")
    }
    return grp_items.value
}

defineExpose({
    load_data,
    get_items
})

</script>

