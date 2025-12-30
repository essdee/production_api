<template>
    <div ref="root">
        <div style="margin-top:20px;">
            <h3>Cloth Details</h3>
            <div class="row" v-if="items && items.length > 0">
                <table class='table table-sm table-bordered'>
                    <tr>
                        <th>S.No</th>
                        <th>Cloth Type</th>
                        <th>Colour</th>
                        <th>Dia</th>
                        <th>Shade</th>
                        <th>Weight in Kg's</th>
                        <th>No of Rolls</th>
                        <th v-if="is_print_panel">Panel Count</th>
                        <th>Delete</th>
                    </tr>
                    <tr v-for="(item,idx) in items" :key='idx'>
                        <td>{{idx + 1}}</td>
                        <td>{{item.cloth_type}}</td>
                        <td>{{item.colour}}</td>
                        <td>{{item.dia}}</td>
                        <td>{{item.shade}}</td>
                        <td>{{item.weight}}</td>
                        <td>{{item.no_of_rolls}}</td>
                        <td v-if="is_print_panel">{{ item.panel_count }}</td>
                        <td>
                            <div class="pull-right cursor-pointer" @click="delete_item(idx)"
                                v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div> 
                        </td>    
                    </tr>
                </table>
            </div>
            <div v-else>
                <h3 v-if='is_print_panel' style="text-align: center;">Add Cloth Items to Print Panel Details</h3>
                <h3 v-else style="text-align: center;">Add Cloth Items to Create Recut Details</h3>
            </div>
        </div>
        <div class="row pt-3" v-if="show_button1">
            <button class="btn btn-success pull-left" @click="add_cloth_item()">Add Cloth Items</button>
        </div>
        <div class="html-container col mt-1">
            <div class="row">
                <div class="cloth-type col-md-4"></div>
                <div class="cloth-colour col-md-4"></div>
                <div class="cloth-dia col-md-4"></div>
            </div>
            <div class="row">
                <div class="cloth-shade col-md-4"></div>
                <div class="cloth-weight col-md-4"></div>
                <div class="cloth-rolls col-md-4"></div>
            </div>
            <div class="row">
                <div class="cloth-panel col-md-4"></div>
            </div>
        </div>
        <div class="row" style="padding-left: 35px;" v-if="!show_button1">
            <button class="btn btn-success" @click="add_item()">Add Item</button>
            <button class="btn btn-success ml-4" @click="make_clean()">Close</button>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

let items = ref([])
let select_attributes = ref({})
let root = ref(null)
let sample_doc = ref({})
let cloth_type = null
let cloth_colour = null
let cloth_dia = null
let cloth_shade = null
let cloth_weight = null
let cloth_rolls = null
let panel_count = null
let docstatus = ref(null)
let show_button1 = ref(true)
let is_print_panel = ref(false)

onMounted(()=> {
    if(cur_frm.is_new()){
        docstatus.value = null
    }
    else{
        docstatus.value = cur_frm.doc.docstatus
    }
    items.value = []
    make_clean()
    frappe.call({
        method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_select_attributes",
        args: {
            cutting_plan:cur_frm.doc.name,
        },
        callback:function(r){
            select_attributes.value = r.message
        }
    })  
})

function add_item(){
    check_values()
    let d = {
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
    }
    if(is_print_panel.value){
        d['panel_count'] = panel_count.get_value()
    }
    items.value.push(d)
    make_clean()
}

function check_values(){
    let arr = [cloth_type, cloth_dia, cloth_colour, cloth_shade, cloth_weight, cloth_rolls]
    if(is_print_panel.value){
        arr.push(panel_count)
    }
    for(let i = 0 ; i < arr.length ; i++){
        let val = arr[i].get_value()
        if(val == null || val == ""){
            frappe.throw("Enter All the Values to Add an Item")
        }
    }        
}

async function add_cloth_item(){
    show_button1.value = false
    cloth_type = get_input_field(".cloth-type", "Select", "cloth_type","Cloth Type", select_attributes.value['cloth_type'])
    cloth_colour = get_input_field(".cloth-colour", "Select", "cloth_colour", "Colour", select_attributes.value['colour'])
    cloth_dia = get_input_field(".cloth-dia", "Select", "cloth_dia", "Dia", select_attributes.value['dia'])
    cloth_shade = get_input_field(".cloth-shade", "Data", "cloth_shade", "Shade", null)
    cloth_weight = get_input_field(".cloth-weight", "Float", "cloth_weight", "Weight in kg's", null)
    cloth_rolls = get_input_field(".cloth-rolls", "Int", "cloth_rolls", "No of Rolls", null)
    if(is_print_panel.value){
        panel_count = get_input_field(".cloth-panel", "Int", "panel_count", "Panel Count", null)
    }
}

function get_input_field(classname, fieldtype, fieldname, label, options){
    let el = root.value
    $(el).find(classname).html("");
    let df = {
        fieldtype: fieldtype,
        fieldname: fieldname,
        label: label,
        reqd: true,
    }
    if(options){
        df['options'] = options
    }    
    return frappe.ui.form.make_control({
        parent: $(el).find(classname),
        df: df,
        doc: sample_doc.value,
        render_input: true,
    });
}

function make_clean(){
    let el = root.value
    let arr1 = [cloth_type, cloth_dia, cloth_colour, cloth_shade, cloth_weight, cloth_rolls]
    if(is_print_panel.value){
        arr1.push(panel_count)
    }
    for(let i = 0 ; i < arr1.length; i++){
        if(arr1[i]){
            arr1[i].set_value(null)
        }
    }
    $(el).find(".cloth-type").html("");
    $(el).find(".cloth-weight").html("");
    $(el).find(".cloth-shade").html("");
    $(el).find(".cloth-colour").html("");
    $(el).find(".cloth-dia").html("");
    $(el).find(".cloth-rolls").html("");
    $(el).find(".cloth-panel").html("");
    show_button1.value = true
}

function delete_item(index){
    let new_arr = null
    if (index ==  0){
        new_arr = items.value.slice(1,items.value.length)
    }
    else if( index == items.value.length -1){
        new_arr = items.value.slice(0,items.value.length-1)
    }
    else{
        let new_arr1 = items.value.slice(0,index)
        let new_arr2 = items.value.slice(index + 1,items.value.length)
        new_arr = new_arr1.concat(new_arr2)
    }
    items.value = new_arr
    make_clean()
}

function get_items(){
    return items.value
}

function load_data(){
    is_print_panel.value = true
}

defineExpose({
    get_items,
    load_data,
})

</script>