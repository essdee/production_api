<template>
    <div ref='root'>
        <div class="row" v-if="items && items.length > 0">
            <h3>Accessory Detail</h3>
            <table class='table table-sm table-bordered'>
                <tr>
                    <th>S.No</th>
                    <th>Accessory</th>
                    <th>Cloth Type</th>
                    <th>Colour</th>
                    <th>Dia</th>
                    <th>Shade</th>
                    <th>Weight</th>
                    <th>No of Rolls</th>
                    <th>Actual Dia</th>
                    <th v-if="status != 'Label Printed' && status != 'Cancelled'">Edit</th>
                </tr>
                <tr v-for="(item,idx) in items" :key='idx'>
                    <td>{{idx + 1}}</td>
                    <td>{{item.accessory}}</td>
                    <td>{{item.cloth_type}}</td>
                    <td>{{item.colour}}</td>
                    <td>{{item.dia}}</td>
                    <td>{{item.shade}}</td>
                    <td>{{item.weight}}</td>
                    <td>{{item.no_of_rolls}}</td>
                    <td>{{item.actual_dia}}</td>
                    <td v-if="status != 'Label Printed' && status != 'Cancelled'">
                        <div class="pull-right cursor-pointer" @click="add_cloth_item(idx)"
                            v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
                        <div class="pull-right cursor-pointer" @click="delete_item(idx)"
                            v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div> 
                    </td>    
                </tr>
            </table>
        </div>
        <div class="row pt-3" v-if="status != 'Label Printed' && status != 'Cancelled' && show_button1 && docstatus != null && had_accessory">
            <button class="btn btn-success pull-left" @click="add_cloth_item(null)">Add Accessory</button>
        </div>
        <div class="html-container col mt-1">
            <div>
                <div class="accessory-type col-md-4"></div>
            </div>
            <div class="row pl-3">
                <div class="cloth-type col-md-4"></div>
                <div class="cloth-colour col-md-4"></div>
                <div class="cloth-dia col-md-4"></div>
            </div>
            <div class="row pl-3">
                <div class="cloth-shade col-md-4"></div>
                <div class="cloth-weight col-md-4"></div>
                <div class="cloth-rolls col-md-4"></div>
            </div>
            <div>
                <div class="actual-dia col-md-4"></div>
            </div>
        </div>
        <div class="row" style="padding-left: 35px;" v-if="show_button2">
            <button class="btn btn-success" @click="add_item()">Add Item</button>
            <button class="btn btn-success ml-4" @click="make_clean()">Close</button>
        </div>
        <div class="row" style="padding-left: 35px;" v-if="show_button3">
            <button class="btn btn-success" @click="update_item()">Update Item</button>
            <button class="btn btn-success ml-4" @click="make_clean()">Close</button>
        </div>
    </div>
</template>
<script setup>
import {ref, onMounted, computed, watch} from 'vue';
let had_accessory = ref(true)
let show_button1 = ref(true)
let show_button2 = ref(false)
let show_button3 = ref(false)
let show_button4 = ref(false)
let show_button5 = ref(false)
let items = ref([])
let root = ref(null)
let sample_doc = ref({})
let select_attributes = null
let cloth_type_dia_map = {}
let accessory = null
let cloth_type = null
let cloth_colour = null
let cloth_dia = null
let cloth_shade = null
let cloth_weight = null
let cloth_rolls = null
let actual_dia = null
let edit_index = null
let cloth_accessories = []
let docstatus = ref(null)
let status = cur_frm.doc.status

function on_change_event(){
    let cloth_dia_value = cloth_dia.get_value()
    if(cloth_dia_value){
        actual_dia.set_value(cloth_dia_value)
        actual_dia.refresh()
    }
}

function on_cloth_type_change_accessory(){
    if(!cloth_type) return
    let selected = cloth_type.get_value()
    let valid_dias = cloth_type_dia_map[selected]
    if(valid_dias && valid_dias.length > 0){
        let dia_options = [""].concat(valid_dias)
        if(cloth_dia){
            cloth_dia.df.options = dia_options
            cloth_dia.set_value("")
            cloth_dia.refresh()
        }
        if(actual_dia){
            actual_dia.df.options = dia_options
            actual_dia.set_value("")
            actual_dia.refresh()
        }
    } else {
        let all_dias = select_attributes['dia'] || []
        let dia_options = [""].concat([...all_dias])
        if(cloth_dia){
            cloth_dia.df.options = dia_options
            cloth_dia.set_value("")
            cloth_dia.refresh()
        }
        if(actual_dia){
            actual_dia.df.options = dia_options
            actual_dia.set_value("")
            actual_dia.refresh()
        }
    }
}

async function add_cloth_item(index){
    show_button1.value = false
    if(index == null){
        show_button2.value = true
        show_button4.value = true
    }
    else{
        edit_index = index
        show_button3.value = true
        show_button5.value = true
    }
    accessory = get_input_field('.accessory-type', 'Select', "accessory", "Accessory", cloth_accessories,true)
    cloth_type = get_input_field(".cloth-type","Select","cloth_type","Cloth Type",select_attributes['cloth_type'],true, change=on_cloth_type_change_accessory)
    cloth_colour = get_input_field(".cloth-colour","Select","cloth_colour","Colour",select_attributes['colour'],true)
    cloth_dia = get_input_field(".cloth-dia","Select","cloth_dia","Dia",select_attributes['dia'],true, change=on_change_event)
    cloth_shade = get_input_field(".cloth-shade","Data","cloth_shade","Shade",null,true)
    cloth_weight = get_input_field(".cloth-weight","Float","cloth_weight","Weight in kg's",null,true)
    cloth_rolls = get_input_field(".cloth-rolls","Int","cloth_rolls","No of Rolls",null,true)
    actual_dia = get_input_field(".actual-dia","Select","actual_dia","Actual Dia",select_attributes['dia'],true)
    if(index != null){
        let arr1 = [accessory, cloth_type,cloth_colour,cloth_dia,cloth_weight,cloth_shade,cloth_rolls]
        let arr2 = ["accessory","cloth_type","colour","dia","weight","shade","no_of_rolls"]
        await set_attr_values(arr1, arr2, index)
        // Filter dia options based on existing cloth_type, then re-set dia values
        let existing_ct = items.value[index]['cloth_type']
        if(existing_ct && cloth_type_dia_map[existing_ct]){
            let valid_dias = cloth_type_dia_map[existing_ct]
            let dia_options = [""].concat(valid_dias)
            cloth_dia.df.options = dia_options
            cloth_dia.refresh()
            actual_dia.df.options = dia_options
            actual_dia.refresh()
        }
        cloth_dia.set_value(items.value[index]['dia'])
        cloth_dia.refresh()
        if(items.value[index]['actual_dia']){
            actual_dia.set_value(items.value[index]['actual_dia'])
            actual_dia.refresh()
        }
    }
}

async function set_attr_values(variables,keys, index){
    for(let i = 0 ; i < variables.length ; i++){
        variables[i].set_value(items.value[index][keys[i]])
        variables[i].refresh()
    }
}

function add_item(){
    check_values()
    cur_frm.dirty()
    items.value.push({
        "accessory":accessory.get_value(),
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
        "actual_dia":actual_dia.get_value(),
    })
    make_clean()
}

function delete_item(index){
    cur_frm.dirty()
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

function update_item(){
    check_values()
    cur_frm.dirty()
    items.value[edit_index] = {
        "accessory":accessory.get_value(),
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
        "actual_dia":actual_dia.get_value(),
    }
    edit_index = null
    show_button3.value = false
    show_button5.value = false
    show_button1.value = true
    make_clean()
}

function check_values(){
    let arr = [cloth_type, cloth_dia, cloth_colour, cloth_shade, cloth_weight, cloth_rolls, actual_dia]
    for(let i = 0 ; i < arr.length ; i++){
        let val = arr[i].get_value()
        if(val == null || val == ""){
            frappe.throw("Enter All the Values to Add an Item")
        }
    }
}

function get_input_field(classname,fieldtype,fieldname,label,options,reqd, change=null){
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
function make_clean(){
    let el = root.value
    let arr1 = [accessory, cloth_type, cloth_dia, cloth_colour, cloth_shade, cloth_weight, cloth_rolls, actual_dia]
    for(let i = 0 ; i < arr1.length; i++){
        if(arr1[i]){
            arr1[i].set_value(null)
        }
    }
    $(el).find(".accessory-type").html("")
    $(el).find(".cloth-type").html("");
    $(el).find(".cloth-weight").html("");
    $(el).find(".cloth-shade").html("");
    $(el).find(".cloth-colour").html("");
    $(el).find(".cloth-rolls").html("");
    $(el).find(".cloth-dia").html("");
    $(el).find(".actual-dia").html("");
    show_button1.value = true
    show_button2.value = false
    show_button3.value = false
    show_button4.value = false
    show_button5.value = false
}

onMounted(()=> {
    if(cur_frm.is_new()){
        docstatus.value = null
    }
    else{
        docstatus.value = cur_frm.doc.docstatus
    }
    if(cur_frm.doc.cutting_plan){
        frappe.call({
            method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_select_attributes",
            args: {
                cutting_plan:cur_frm.doc.cutting_plan,
            },
            callback:function(r){
                select_attributes = r.message
                cloth_type_dia_map = r.message.cloth_type_dia_map || {}
            }
        })
        frappe.call({
            method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_cloth_accessories",
            args: {
                cutting_plan:cur_frm.doc.cutting_plan,
            },
            callback:function(r){
                cloth_accessories = r.message
                if(cloth_accessories.length == 0){
                    had_accessory.value = false
                }
            }
        })
    } else if(cur_frm.doc.cutting_order){
        frappe.call({
            method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_select_attributes",
            args: {
                cutting_order:cur_frm.doc.cutting_order,
            },
            callback:function(r){
                select_attributes = r.message
                cloth_type_dia_map = r.message.cloth_type_dia_map || {}
            }
        })
        frappe.call({
            method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_cloth_accessories",
            args: {
                cutting_order:cur_frm.doc.cutting_order,
            },
            callback:function(r){
                cloth_accessories = r.message
                if(cloth_accessories.length == 0){
                    had_accessory.value = false
                }
            }
        })
    }
})

function load_data(item_detail){
    items.value = item_detail
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
.table{
    margin: 0 !important;
}
</style>

