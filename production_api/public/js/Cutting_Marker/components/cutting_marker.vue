<template>
    <div>
        <div v-if="show && docstatus == 0 && doctype=='Cutting Marker' ">
            <div ref="select_field_ref" class="select-field col-md-5"></div>
            <div ref="panel_list" class="panel-list pl-3"></div>
            <button class="btn btn-success" @click="get_combination(true)">Get Combination</button>
        </div>

        <div v-if="items && items.length > 0" class="pt-5">
            <h4 v-if="doc_panels.length > 0">Panels: {{doc_panels}}</h4>
            <h3>Ratios</h3>
            <table class="table table-sm table-bordered">
                <tr>
                    <td>Size</td>
                    <td v-if="show_panel">Panel</td>
                    <td>Ratio</td>
                </tr>
                <tr v-for="item in items" :key="item">
                    <td>{{item.size}}</td>
                    <td v-if="show_panel">{{item.panel}}</td>
                    <td v-if="docstatus == 0 && doctype=='Cutting Marker'">
                        <input type="number" step="1" v-model="item.ratio" class="form-control"  @blur="make_dirty()">
                    </td>
                    <td v-else>
                        {{item.ratio}}
                    </td>
                </tr>
            </table>
            <button v-if="!show  && docstatus == 0 && doctype=='Cutting Marker'" class="btn btn-info" @click="make_show_panel()">Update Panels</button>
        </div>
        <div v-if="grp_items.length > 0 && version == 'V3'">
            <h3>Group Panels</h3>
            <table class="table table-sm table-bordered">
                <tr>
                    <td>Panels</td>
                    <td v-if="docstatus == 0">Delete</td>
                </tr>
                <tr v-for="item in grp_items" :key="item">
                    <td v-if="item.defaultList.length > 0">
                        <MultiSelect :options="item.options" :setDefault="true" :defaultList="item.defaultList" :triggerEvent="update_selected" :item_key="item['id']" :docstatus="docstatus"/>
                    </td>
                    <td v-else>
                        <MultiSelect :options="options" :setDefault="true" :defaultList="[]" :triggerEvent="update_selected" :item_key="item['id']"/>
                    </td>
                    <td v-if="docstatus == 0">
                        <div class="cursor-pointer" @click="delete_group_item(item)" v-html="frappe.utils.icon('delete', 'md')"></div>
                    </td>
                </tr>
            </table>
        </div>    
        <button v-if="docstatus == 0 && version == 'V3'" style="margin-top:10px;" @click="add_groups()" class="btn btn-success">Add Groups</button>
    </div>    
</template>
<script setup>
import { ref, onMounted } from 'vue';
import MultiSelect from "../../components/MultiSelect.vue";

let items = ref([])
let grp_items = ref([])
let show = ref(false)
let select_field = null
let select_attrs = null
let root = ref(null)
let select_field_ref = ref(null)
let panel_list = ref(null)
let sample_doc = ref({})
let show_panel = ref(false)
let docstatus = ref(cur_frm.doc.docstatus)
let doctype = ref(cur_frm.doc.doctype)
let doc_panels = cur_frm.doc.calculated_parts
let version = cur_frm.doc.version
let grp_panel = null
let options = []

onMounted(() => {
    if(doc_panels){
        create_options(doc_panels.split(","))
    }
})

function make_show_panel(){
    show.value = true
    setTimeout(()=> {
        create_attributes()
    }, 300)
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
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

function load_data(item){
    if(!cur_frm.doc.__islocal){
        if(cur_frm.doc.selected_type == "Manual"){
            show_panel.value = true
        }
        items.value = item['cutting_marker_ratios']
        if(item['cutting_marker_ratios'].length == 0){
            show.value = true
            setTimeout(()=> {
                create_attributes()
            }, 300)
        }
        grp_items.value = item['cutting_marker_groups']
    }
}
function get_items(){
    let check = false
    if(!cur_frm.doc.is_manual_entry){
        for(let i = 0; i < items.value.length ; i++){
            if(items.value[i].ratio > 0){
                check = true
            }
        }
        if(!check){
            frappe.throw("Enter the Ratio Values")
        }
    }
    let selected_panels = []
    for(let i = 0; i < grp_items.value.length ; i++){
        if(grp_items.value[i].selected.length > 0){
            if(grp_items.value[i].selected.length > 2){
                frappe.throw("Only two panels can be a group")
            }
            for(let j = 0; j < grp_items.value[i].selected.length; j++){
                if(selected_panels.includes(grp_items.value[i].selected[j])){
                    frappe.throw("Panel " + grp_items.value[i].selected[j] + " is grouped multiple times")
                }
                selected_panels.push(grp_items.value[i].selected[j])
            }
        }
    }
    if(selected_panels.length != 0 && selected_panels.length != doc_panels.split(",").length && cur_frm.doc.version == 'V3'){
        frappe.throw("Select All the Panels")
    }
    return {
        "ratio_items":items.value,
        "group_items":grp_items.value,
    }
}

function create_attributes(){
    let el = root.value
    $(select_field_ref.value).html("")
    select_field = frappe.ui.form.make_control({
        parent : $(select_field_ref.value),
        df : {
            fieldname: "select",
            fieldtype: "Select",
            label:"Select Type",
            options:"Machine\nManual",
            onchange:()=> {
                let val = select_field.get_value()
                if(val && val != "" && val != null){
                    get_combination()
                }
            }
        },
        doc: sample_doc.value,
        render_input : true
    })
    select_field.set_value("Machine")
    select_field.refresh()
    frappe.call({
        method:"production_api.production_api.doctype.cutting_marker.cutting_marker.calculate_parts",
        args: {
            cutting_plan: cur_frm.doc.cutting_plan,
        },
        callback: function(r){
            let parts = r.message
            $(panel_list.value).html("")
            select_attrs = frappe.ui.form.make_control({
                parent:$(panel_list.value),
                df: {
                    fieldname: "select_attributes",
                    fieldtype: "MultiCheck",
                    select_all: true,
                    sort_options: false,
                    columns: 7,
                    get_data: () => {
                        return parts.map(attr => {
                            return {
                                label: attr.part,   
                                value: attr.part,  
                            };
                        });
                    },
                },
                doc: sample_doc.value,
                render_input : true
            })
        }
    })
}

function get_combination(user_input=null){
    make_dirty()
    let selected_value = select_field.get_value()
    if(!selected_value || selected_value == "" || selected_value == null){
        frappe.msgprint("Select the Select Type")
        return
    }
    let panels = select_attrs.get_value()
    grp_panel = panels
    create_options(panels)
    if(panels.length == 0 && user_input){
        frappe.msgprint("Select a panel")
        return
    }
    if(selected_value == "Machine"){
        show_panel.value = false
    }
    else{
        show_panel.value = true
    }
    cur_frm.doc.selected_type = selected_value
    cur_frm.doc.calculated_parts = panels.join(",")
    doc_panels = panels.join(",")
    frappe.call({
        method:"production_api.production_api.doctype.cutting_marker.cutting_marker.get_primary_attributes",
        args: {
            lot:cur_frm.doc.lot,
            selected_value: selected_value,
            panels: panels
        },
        callback:((r)=> {
            items.value = r.message
            grp_items.value = []
        })
    })
}

function create_options(panels){
    options = panels.map((panel, idx) => {
        return {
            "option": panel,
            "id": panel,
        }
    })
}

defineExpose({
    load_data,
    get_items
})

</script>
