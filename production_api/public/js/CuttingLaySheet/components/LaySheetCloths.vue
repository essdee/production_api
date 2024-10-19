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
                <div class="cloth-shade col-md-5"></div>
                <div class="cloth-weight col-md-5"></div>
            </div>
            <div class="row">
                <div class="cloth-rolls col-md-5"></div>
                <div class="cloth-bits col-md-5"></div>
                <div class="cloth-end-bit col-md-5"></div>
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
import {ref, onMounted} from 'vue';
let show_button1 = ref(true)
let show_button2 = ref(false)
let show_button3 = ref(false)
let items = ref([])
let root = ref(null)
let sample_doc = ref({})
let select_attributes = null
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
    $(el).find(".cloth-type").html("");
    cloth_type = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-type"),
        df: {
            fieldtype: "Select",
            fieldname: "cloth_type",
            label: "Cloth Type",
            options : select_attributes['cloth_type'],
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-colour").html("");
    cloth_colour = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-colour"),
        df: {
            fieldtype: "Select",
            fieldname: "cloth_colour",
            label: "Colour",
            options : select_attributes['colour'],
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-dia").html("");
    cloth_dia = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-dia"),
        df: {
            fieldtype: "Select",
            fieldname: "cloth_dia",
            label: "Dia",
            options : select_attributes['dia'],
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-shade").html("");
    cloth_shade = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-shade"),
        df: {
            fieldtype: "Data",
            fieldname: "cloth_shade",
            label: "Shade",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-weight").html("");
    cloth_weight = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-weight"),
        df: {
            fieldtype: "Float",
            fieldname: "cloth_weight",
            label: "Weight",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-rolls").html("");
    cloth_rolls = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-rolls"),
        df: {
            fieldtype: "Int",
            fieldname: "cloth_rolls",
            label: "No of Rolls",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-bits").html("");
    cloth_bits = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-bits"),
        df: {
            fieldtype: "Int",
            fieldname: "cloth_bits",
            label: "No of Bits",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-end-bit").html("");
    cloth_end_bit = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-end-bit"),
        df: {
            fieldtype: "Float",
            fieldname: "cloth_end_bit",
            label: "Cloth End Bit Weight",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".cloth-comment").html("");
    cloth_comment = frappe.ui.form.make_control({
        parent: $(el).find(".cloth-comment"),
        df: {
            fieldtype: "Small Text",
            fieldname: "cloth_comment",
            label: "Comment",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    });
    if(index != null){
        cloth_type.set_value(items.value[index]['cloth_type'])
        cloth_type.refresh()
        cloth_colour.set_value(items.value[index]['colour'])
        cloth_colour.refresh()
        cloth_dia.set_value(items.value[index]['dia'])
        cloth_dia.refresh()
        cloth_weight.set_value(items.value[index]['weight'])
        cloth_weight.refresh()
        cloth_shade.set_value(items.value[index]['shade'])
        cloth_shade.refresh()
        cloth_rolls.set_value(items.value[index]['no_of_rolls'])
        cloth_rolls.refresh()
        cloth_bits.set_value(items.value[index]['no_of_bits'])
        cloth_bits.refresh()
        cloth_end_bit.set_value(items.value[index]['end_bit_weight'])
        cloth_end_bit.refresh()
        cloth_comment.set_value(items.value[index]['comments'])
        cloth_comment.refresh()
    }
}

function add_item(){
    check_values()
    cur_frm.dirty()
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
    items.value[edit_index] = {
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
        "no_of_bits":cloth_bits.get_value(),
        "end_bit_weight":cloth_end_bit.get_value(),
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

function make_clean(){
    let el = root.value
    cloth_type.set_value(null),
    cloth_dia.set_value(null),
    cloth_colour.set_value(null),
    cloth_shade.set_value(null),
    cloth_weight.set_value(null),
    cloth_rolls.set_value(null),
    cloth_bits.set_value(null),
    cloth_end_bit.set_value(null),
    cloth_comment.set_value(null),
    $(el).find(".cloth-type").html("");
    $(el).find(".cloth-weight").html("");
    $(el).find(".cloth-end-bit").html("");
    $(el).find(".cloth-comment").html("");
    $(el).find(".cloth-shade").html("");
    $(el).find(".cloth-colour").html("");
    $(el).find(".cloth-dia").html("");
    $(el).find(".cloth-bits").html("");
    $(el).find(".cloth-rolls").html("");
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
    }
})

function load_data(item_detail){
    console.log(items.length)
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

