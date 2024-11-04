<template>
    <div ref='root'>
        <div class="row">
            <table v-if="items && items.length > 0" class='table table-sm table-bordered'>
                <tr>
                    <th>S.No</th>
                    <th>Cloth Type</th>
                    <th>Colour</th>
                    <th>Dia</th>
                    <th>Shade</th>
                    <th>Weight</th>
                    <th>No of Rolls</th>
                    <th>No of Bits</th>
                    <th>End Bit Weight</th>
                    <th>Accessory in kg's</th>
                    <th>Comments</th>
                    <th>Edit</th>
                </tr>
                <tr v-for="(item,idx) in items" :key='idx'>
                    <td>{{idx + 1}}</td>
                    <td>{{item.cloth_type}}</td>
                    <td>{{item.colour}}</td>
                    <td>{{item.dia}}</td>
                    <td>{{item.shade}}</td>
                    <td>{{item.weight}}</td>
                    <td>{{item.no_of_rolls}}</td>
                    <td>{{item.no_of_bits}}</td>
                    <td>{{item.end_bit_weight}}</td>
                    <td>
                        <div v-for='(key,value) in JSON.parse(item.accessory_json)' :key='key'>
                            {{value}}:{{key}}
                        </div>
                    </td>
                    <td>{{item.comments}}</td>
                    <td>
                        <div class="pull-right cursor-pointer" @click="add_cloth_item(idx)"
                            v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
                        <div class="pull-right cursor-pointer" @click="delete_item(idx)"
                            v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div> 
                    </td>    
                </tr>
            </table>
        </div>
        <div class="row" v-if="show_button1 && docstatus != null">
            <button class="btn btn-success pull-left" @click="add_cloth_item(null)">Add Cloth Items</button>
        </div>
        <div class="html-container col mt-5">
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
                <div class="cloth-bits col-md-4"></div>
                <div class="cloth-end-bit col-md-4"></div>
                <div class="cloth-balance col-md-4"></div>
            </div>
            <div class="row">                
                <div class="cloth-accessory-left col-md-4"></div>
                <div class="cloth-accessory-middle col-md-4"></div>
                <div class="cloth-accessory-right col-md-4"></div>
            </div>
            <div class="row">
                <div class="cloth-comment col-md-12"></div>
            </div>
        </div>
        <div class="row" v-if="show_button2">
            <button class="btn btn-success pull-left" @click="add_item()">Add Item</button>
        </div>
        <div class="row" v-if="show_button3">
            <button class="btn btn-success pull-left" @click="update_item()">Update Item</button>
        </div>
    </div>
</template>
<script setup>
import {ref, onMounted, computed} from 'vue';
let show_button1 = ref(true)
let show_button2 = ref(false)
let show_button3 = ref(false)
let items = ref([])
let root = ref(null)
let sample_doc = ref({})
let select_attributes = null
let cloth_accessories = []
let cloth_type = null
let cloth_colour = null
let cloth_dia = null
let cloth_shade = null
let cloth_weight = null
let cloth_rolls = null
let cloth_bits = null
let cloth_end_bit = null
let cloth_comment = null
let edit_index = null
let balance_weight = null
let cloth_attrs = []
let docstatus = ref(null)

function add_cloth_item(index){
    show_button1.value = false
    if(index == null){
        show_button2.value = true
    }
    else{
        edit_index = index
        show_button3.value = true
    }
    let el = root.value;
    cloth_type = get_input_field(".cloth-type","Select","cloth_type","Cloth Type",select_attributes['cloth_type'],true)
    cloth_colour = get_input_field(".cloth-colour","Select","cloth_colour","Colour",select_attributes['colour'],true)
    cloth_dia = get_input_field(".cloth-dia","Select","cloth_dia","Dia",select_attributes['dia'],true)
    cloth_shade = get_input_field(".cloth-shade","Data","cloth_shade","Shade",null,true)
    cloth_weight = get_input_field(".cloth-weight","Float","cloth_weight","Weight in kg's",null,true)
    cloth_rolls = get_input_field(".cloth-rolls","Int","cloth_rolls","No of Rolls",null,true)
    cloth_bits = get_input_field(".cloth-bits","Int","cloth_bits","No of Bits",null,true)
    cloth_end_bit = get_input_field(".cloth-end-bit","Float","cloth_end_bit","End Bit Weight",null,true)
    cloth_comment = get_input_field(".cloth-comment","Small Text","cloth_comment",'Comment',null,false)
    balance_weight = get_input_field(".cloth-balance","Float","balance_weight","Balance Weight",null,true)
    $(el).find(".cloth-accessory-left").html("");
    $(el).find(".cloth-accessory-right").html("");
    $(el).find(".cloth-accessory-middle").html("");
    for(let i = 0 ; i < cloth_accessories.length ; i++){
        let classname = "";
        if(i % 3 == 0){
            classname = ".cloth-accessory-left";
        }
        else if(i % 2 == 0){
            classname = ".cloth-accessory-right";
        }
        else{
            classname = ".cloth-accessory-middle";
        }
        $(el).find(classname).append("<div class='input-wrapper'></div>");
        cloth_attrs[i] = get_input_field(classname + ' .input-wrapper:last',"Float","cloth_accessories_" + i,cloth_accessories[i]+" in kg's",null,false)
    }
    if(index != null){
        let arr1 = [cloth_type,cloth_colour,cloth_dia,cloth_weight,cloth_shade,cloth_rolls,cloth_bits,cloth_end_bit,cloth_comment,balance_weight]
        let arr2 = ["cloth_type","colour","dia","weight","shade","no_of_rolls","no_of_bits","end_bit_weight","comments","balance_weight"]
        set_attr_values(arr1,arr2, index)
        let dict = items.value[index]['accessory_json']
        if(typeof(dict) == 'string'){
            dict = JSON.parse(dict)
        }
        Object.keys(dict).forEach((key,value)=> {
            cloth_attrs[value].set_value(dict[key])
        })
    }
}

function set_attr_values(variables,keys, index){
    for(let i = 0 ; i < variables.length ; i++){
        variables[i].set_value(items.value[index][keys[i]])
        variables[i].refresh()
    }
}

function add_item(){
    check_values()
    cur_frm.dirty()
    let accessory_json = {}
    let total_weight = 0.0
    for(let i = 0 ; i < cloth_attrs.length; i++){
        let val = cloth_attrs[i].get_value()
        accessory_json[cloth_accessories[i]] = val
        total_weight += val
    }
    items.value.push({
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
        "no_of_bits":cloth_bits.get_value(),
        "end_bit_weight":cloth_end_bit.get_value(),
        "comments":cloth_comment.get_value(),
        "balance_weight":balance_weight.get_value(),
        "used_weight": cloth_weight.get_value() - cloth_end_bit.get_value() - balance_weight.get_value(),
        "accessory_json":JSON.stringify(accessory_json),
        "accessory_weight":total_weight,
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
}

function update_item(){
    check_values()
    cur_frm.dirty()
    let accessory_json = {}
    let total_weight = 0.0
    for(let i = 0 ; i < cloth_attrs.length; i++){
        let val = cloth_attrs[i].get_value()
        accessory_json[cloth_accessories[i]] = val
        total_weight += val
    }
    items.value[edit_index] = {
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
        "no_of_bits":cloth_bits.get_value(),
        "end_bit_weight":cloth_end_bit.get_value(),
        "balance_weight":balance_weight.get_value(),
        "used_weight": cloth_weight.get_value() - cloth_end_bit.get_value() - balance_weight.get_value(),
        "accessory_weight":total_weight,
        "accessory_json":accessory_json,
        "comments":cloth_comment.get_value(),
    }
    edit_index = null
    show_button3.value = false
    make_clean()
}

function check_values(){
    let arr = [cloth_type, cloth_dia, cloth_colour, cloth_shade, cloth_weight, cloth_rolls, cloth_bits]
    for(let i = 0 ; i < arr.length ; i++){
        let val = arr[i].get_value()
        if(val == null || val == ""){
            frappe.throw("Enter All the Values to Add an Item")
        }
    }
}

function get_input_field(classname,fieldtype,fieldname,label,options,reqd){
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
    return frappe.ui.form.make_control({
        parent: $(el).find(classname),
        df: df,
        doc: sample_doc.value,
        render_input: true,
    });
}
function make_clean(){
    let el = root.value
    let arr1 = [cloth_type,cloth_dia,cloth_colour,cloth_shade,cloth_weight,cloth_rolls,cloth_bits,cloth_end_bit,cloth_comment]
    for(let i = 0 ; i < arr1.length; i++){
        arr1[i].set_value(null)
    }
    for (let i =0 ; i < cloth_attrs.length ; i++){
        cloth_attrs[i].set_value(null)
    }
    $(el).find(".cloth-type").html("");
    $(el).find(".cloth-weight").html("");
    $(el).find(".cloth-end-bit").html("");
    $(el).find(".cloth-comment").html("");
    $(el).find(".cloth-shade").html("");
    $(el).find(".cloth-colour").html("");
    $(el).find(".cloth-dia").html("");
    $(el).find(".cloth-bits").html("");
    $(el).find(".cloth-rolls").html("");
    $(el).find(".cloth-balance").html("");
    $(el).find(".cloth-accessory-right").html("");
    $(el).find(".cloth-accessory-left").html("");
    $(el).find(".cloth-accessory-middle").html("");
    show_button1.value = true
    show_button2.value = false
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
            }
        })
        frappe.call({
            method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_cloth_accessories",
            args: {
                cutting_plan:cur_frm.doc.cutting_plan,
            },
            callback:function(r){
                cloth_accessories = r.message
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

