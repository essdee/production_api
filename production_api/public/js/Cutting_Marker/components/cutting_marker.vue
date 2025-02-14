<template>
    <div>
        <div v-if="show && docstatus == 0 && doctype=='Cutting Marker' ">
            <div ref="select_field_ref" class="select-field col-md-5"></div>
            <div ref="panel_list" class="panel-list pl-3"></div>
            <button class="btn btn-success" @click="get_combination()">Get Combination</button>
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
                        <input type="number" step="1" v-model="item.ratio" class="form-control"  @blur="update_doc()">
                    </td>
                    <td v-else>
                        {{item.ratio}}
                    </td>
                </tr>
            </table>
            <button v-if="!show  && docstatus == 0 && doctype=='Cutting Marker'" class="btn btn-info" @click="make_show_panel()">Update Panels</button>
        </div>
    </div>    
</template>

<script setup>
import {ref} from 'vue';

let items = ref([])
let show=ref(false)
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

function load_data(item){
    if(!cur_frm.doc.__islocal){
        if(cur_frm.doc.selected_type == "Manual"){
            show_panel.value = true
        }
        items.value = item
        if(item.length == 0){
            show.value = true
            setTimeout(()=> {
                create_attributes()
            }, 300)
        }
    }
}

function make_show_panel(){
    show.value = true
    setTimeout(()=> {
        create_attributes()
    }, 300)
}

function update_doc(){
    cur_frm.dirty()
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
                console.log(val)
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

function get_combination(){
    cur_frm.dirty()
    let selected_value = select_field.get_value()
    if(!selected_value || selected_value == "" || selected_value == null){
        frappe.msgprint("Select the Select Type")
        return
    }
    let panels = select_attrs.get_value()
    if(panels.length == 0){
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
        })
    })
}

function get_items(){
    let check = false
    for(let i = 0; i < items.value.length ; i++){
        if(items.value[i].ratio > 0){
            check = true
        }
    }
    if(!check){
        frappe.throw("Enter the Ratio Values")
    }
    else{
        return items.value
    }
}

defineExpose({
    load_data,
    get_items,
})
</script>
