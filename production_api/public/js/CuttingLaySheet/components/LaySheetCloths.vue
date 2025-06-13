<template>
    <div ref='root'>
        <div v-if="is_manual_entry">
            <h3>Bundle Details</h3>
            <table class="table table-sm table-bordered" v-if="primary_values.length && Object.keys(manual_items).length">
                <thead>
                    <tr>
                        <th>S.No</th>
                        <th style="width:135px;">Colour</th>
                        <th style="width:135px;">Major Colour</th>
                        <th v-if="is_set_item" style="width:135px;">Set Colour</th>
                        <th style="width:70px;">Shade</th>
                        <th style="width:100px;">Quantity</th>
                        <th v-for="primary in primary_values" :key="primary">{{ primary }}</th>
                        <th v-if="!disabled">Delete</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(item, rowIndex) in Object.values(manual_items)" :key="rowIndex">
                        <td>{{ rowIndex + 1 }}</td>
                        <td>
                            <select v-model="item.colour" class="form-control form-control-sm" @input="get_set_colour(item, $event.target.value)" :disabled="disabled">
                                <option v-for="attr in select_attributes['colour']" :key="attr" :value="attr">{{ attr }}</option>
                            </select>
                        </td>
                        <td>
                            <select v-model="item.major_colour" class="form-control form-control-sm" :disabled="disabled" @blur="make_dirty()">
                                <option v-for="attr in select_attributes['colour']" :key="attr" :value="attr">{{ attr }}</option>
                            </select>
                        </td>
                        <td v-if="is_set_item">
                            <select v-model="item.set_colour" class="form-control form-control-sm" :disabled="disabled" @blur="make_dirty()">
                                <option v-for="attr in select_attributes['colour']" :key="attr" :value="attr">{{ attr }}</option>
                            </select>
                        </td>
                        <td>
                            <input type="text" v-model="item.shade" class="form-control form-control-sm" @blur="make_dirty()" :disabled="disabled">
                        </td>
                        <td>
                            <input type="number" v-model.number="item.quantity" @blur="make_dirty()" :disabled="disabled" class="form-control form-control-sm" />
                        </td>
                        <td v-for="primary in primary_values" :key="primary">
                            <input type="number" v-model.number="item[primary]" @blur="make_dirty()" :disabled="disabled" class="form-control form-control-sm" />
                        </td>
                        
                        <td v-if="!disabled">
                            <div class="cursor-pointer" @click="delete_group_item(item)" v-html="frappe.utils.icon('delete', 'md')"></div>
                        </td>
                    </tr>
                </tbody>
            </table>
            <button v-if="!disabled" class="btn btn-success" @click="add_manual_item()" style="margin-top:10px;">Add Item</button>
        </div>
        <div style="margin-top:20px;">
            <div class="row" v-if="items && items.length > 0">
                <h3>Cloth Details</h3>
                <table class='table table-sm table-bordered'>
                    <tr>
                        <th>S.No</th>
                        <th>Cloth Type</th>
                        <th>Colour</th>
                        <th>Dia</th>
                        <th>Shade</th>
                        <th>Weight</th>
                        <th>No of Rolls</th>
                        <th v-if="!is_manual_entry">No of Bits</th>
                        <th v-if="!is_manual_entry">End Bit Weight</th>
                        <th v-if="!is_manual_entry">Balance Weight</th>
                        <th>Fabric Type</th>
                        <th v-if="!is_manual_entry">Comments</th>
                        <th v-if="status != 'Label Printed' && status != 'Cancelled'">Edit</th>
                    </tr>
                    <tr v-for="(item,idx) in items" :key='idx'>
                        <td>{{idx + 1}}</td>
                        <td>{{item.cloth_type}}</td>
                        <td>{{item.colour}} ({{JSON.parse(item['set_combination'])['major_colour']}})</td>
                        <td>{{item.dia}}</td>
                        <td>{{item.shade}}</td>
                        <td>{{item.weight}}</td>
                        <td>{{item.no_of_rolls}}</td>
                        <td v-if="!is_manual_entry">{{item.no_of_bits}}<span v-if="item.effective_bits">({{item.effective_bits}})</span></td>
                        <td v-if="!is_manual_entry">{{item.end_bit_weight}}</td>
                        <td v-if="!is_manual_entry">{{item.balance_weight}}</td>
                        <td>{{item.fabric_type}}</td>
                        <td v-if="!is_manual_entry">{{item.comments}}</td>
                        <td v-if="status != 'Label Printed' && status != 'Cancelled'">
                            <div class="pull-right cursor-pointer" @click="add_cloth_item(idx)"
                                v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
                            <div class="pull-right cursor-pointer" @click="delete_item(idx)"
                                v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div> 
                        </td>    
                    </tr>
                </table>
            </div>
            <div class="row pt-3" v-if="status != 'Label Printed' && status != 'Cancelled' && show_button1 && docstatus != null">
                <button class="btn btn-success pull-left" @click="add_cloth_item(null)">Add Cloth Items</button>
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
                    <div class="cloth-bits col-md-4"></div>
                    <div class="cloth-end-bit col-md-4"></div>
                    <div class="cloth-balance col-md-4"></div>
                </div>
                <div class="row">
                    <div class="fabric-type col-md-4"></div>
                </div>
                <div class="row">
                    <div class="set-detail row pl-5 pb-2" style="display: flex; gap: 10px"></div>
                </div>
                <div class="row" v-if="!is_manual_entry">
                    <div class="pl-4" v-if="show_button4">
                        <button class="btn btn-info pull-left" @click="add_entries()">Add Entries</button>       
                    </div>
                    <div class="pl-4"  v-if="show_button5">
                        <button class="btn btn-info pull-left" @click="update_entries()">Update Entries</button>
                    </div>
                    <div class="items-json col-md-12"></div> 
                    <div class="cloth-comment col-md-12"></div>
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
    </div>
</template>
<script setup>
import {ref, onMounted, computed, watch, nextTick} from 'vue';
let show_button1 = ref(true)
let show_button2 = ref(false)
let show_button3 = ref(false)
let show_button4 = ref(false)
let show_button5 = ref(false)
let items = ref([])
let manual_items = ref({})
let manual_index = ref(0)
let root = ref(null)
let sample_doc = ref({})
let select_attributes = ref({
    "colour": []
})
let is_manual_entry = cur_frm.doc.is_manual_entry
let primary_values = ref([])
let cloth_type = null
let cloth_colour = null
let cloth_dia = null
let cloth_shade = null
let cloth_weight = null
let cloth_rolls = null
let cloth_bits = null
let cloth_end_bit = null
let cloth_comment = null
let fabric_type = null
let edit_index = ref(null)
let balance_weight = null
let items_json =  null
let docstatus = ref(null)
let status = cur_frm.doc.status
let set_parameters = []
let fieldnames = []
let part_set_colours = null
let colourRefs = ref({})
let setColourRefs = ref({})
let multiplierRefs = ref({})
let primaryValueRefs = ref({})
let disabled = ref(false)
let is_set_item = cur_frm.doc.is_set_item

function delete_group_item(item){
    let idx = item['manual_index']
    delete manual_items.value[idx]
    make_dirty()
}

function onchange_event(){
    if (!cloth_colour){
        return
    }
    let val = cloth_colour.get_value()
    if(val && val != "" && val != null){
        frappe.call({
            method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_input_fields",
            args: {
                cutting_marker:cur_frm.doc.cutting_marker,
                colour: val,
                select_attributes: select_attributes.value
            },
            callback:function(r){
                if(r.message.input_fields.length > 0){
                    part_set_colours = r.message.part_colours
                    let inputs = r.message.input_fields
                    let el = root.value;
                    $(el).find(".set-detail").html("");
                    set_parameters = [];
                    fieldnames = [];
                    for(let i = 0 ; i < inputs.length ; i++){
                        let df = inputs[i]
                        if(df.default){
                            df['read_only'] = true
                        }
                        fieldnames.push(df.fieldname)
                        set_parameters[i] = frappe.ui.form.make_control({
                            parent: $(el).find(".set-detail"),
                            df: df,
                            doc: sample_doc.value,
                            render_input: true,
                        });
                        if(df.default){
                            set_parameters[i].set_value(inputs[i].default)
                        }
                        if(edit_index.value != null && edit_index.value >= 0 && !df.default){
                            let val = items.value[edit_index.value]['set_combination']
                            if(typeof(val) == "string"){
                                val = JSON.parse(val)
                            }
                            if(val[df.fieldname]){
                                set_parameters[i].set_value(val[df.fieldname])
                            }
                        }
                        set_parameters[i].refresh()
                    }  
                }
            }
        })
    }
}

async function add_cloth_item(index){
    show_button1.value = false
    if(index == null){
        show_button2.value = true
        show_button4.value = true
    }
    else{
        edit_index.value = index
        show_button3.value = true
        show_button5.value = true
    }
    let el = root.value;
    let no_options = null
    let reqd = true
    let not_reqd = false
    cloth_type = get_input_field(".cloth-type", "Select", "cloth_type","Cloth Type", select_attributes.value['cloth_type'], reqd)
    cloth_colour = get_input_field(".cloth-colour", "Select", "cloth_colour", "Colour", select_attributes.value['colour'], reqd, change=onchange_event)
    cloth_dia = get_input_field(".cloth-dia", "Select", "cloth_dia", "Dia", select_attributes.value['dia'], reqd)
    cloth_shade = get_input_field(".cloth-shade", "Data", "cloth_shade", "Shade", no_options, reqd)
    cloth_weight = get_input_field(".cloth-weight", "Float", "cloth_weight", "Weight in kg's", no_options, reqd)
    cloth_rolls = get_input_field(".cloth-rolls", "Int", "cloth_rolls", "No of Rolls", no_options, reqd)
    if(!cur_frm.doc.is_manual_entry){
        cloth_comment = get_input_field(".cloth-comment", "Small Text", "cloth_comment",'Comment', no_options, not_reqd)
        cloth_bits = get_input_field(".cloth-bits", "Int", "cloth_bits", "No of Bits", no_options, reqd)
        cloth_end_bit = get_input_field(".cloth-end-bit", "Float", "cloth_end_bit", "End Bit Weight", no_options, reqd)
        balance_weight = get_input_field(".cloth-balance", "Float", "balance_weight", "Balance Weight", no_options, reqd)
        items_json = get_input_field(".items-json", "JSON", "items_json", "Items JSON", no_options, not_reqd)
        items_json.df.hidden = true
        items_json.refresh()
    }
    fabric_type = get_input_field(".fabric-type", "Select", "fabric_type", "Fabric Type",["Open Width", "Tubler"],reqd)
    fabric_type.set_value("Open Width")
    fabric_type.refresh()
   
    if(index != null){
        let arr1 = [cloth_type,cloth_colour,cloth_dia,cloth_weight,cloth_shade,cloth_rolls,cloth_bits,cloth_end_bit,cloth_comment,balance_weight, items_json, fabric_type]
        let arr2 = ["cloth_type","colour","dia","weight","shade","no_of_rolls","no_of_bits","end_bit_weight","comments","balance_weight","items_json", "fabric_type"]
        if(cur_frm.doc.is_manual_entry){
            arr1 = [cloth_type, cloth_colour, cloth_dia, cloth_weight, cloth_shade, cloth_rolls, fabric_type]
            arr2 = ["cloth_type", "colour", "dia", "weight", "shade", "no_of_rolls", "fabric_type"]
        }
        await set_attr_values(arr1,arr2, index)
        if(!cur_frm.doc.is_manual_entry){
            let json = JSON.parse(items.value[index]['items_json'])
            if(typeof(json) == "string"){
                json = JSON.parse(json)
            }
            if(json.length > 0){
                update_readonly([cloth_weight, cloth_rolls, cloth_bits, cloth_end_bit, balance_weight])
            }
        }
    }
}

async function set_attr_values(variables,keys, index){
    for(let i = 0 ; i < variables.length ; i++){
        variables[i].set_value(items.value[index][keys[i]])
        variables[i].refresh()
    }
}

function update_readonly(input_fields){
    for(let i = 0 ; i < input_fields.length ; i++){
        input_fields[i].df.read_only = !input_fields[i].df.read_only
        input_fields[i].refresh()
    }
}

function add_item(){
    check_values()
    make_dirty()

    let set_json = {}
    for(let i = 0 ; i < set_parameters.length ; i++){
        let val = set_parameters[i].get_value()
        if(val == null || val == ""){
            if(set_parameters[i]['df']["fieldname"] == 'is_same_packing_attribute' || set_parameters[i]['df']["fieldname"] == 'is_set_item'){
                val = 0
            }
            else{
                frappe.throw("Enter the Set Combination")
            }
        }
        set_json[fieldnames[i]] = val
    }
    check_combination(set_json)
    let json_val = {}
    if(!is_manual_entry){
        json_val = items_json.get_value()
        if(!json_val || json_val == null){
            json_val = []
        }
    }
    let d = {
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "fabric_type": fabric_type.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
        "set_combination":JSON.stringify(set_json)
    }

    if(!is_manual_entry){
        let x = {
            "comments":cloth_comment.get_value(),
            "no_of_bits":cloth_bits.get_value(),
            "end_bit_weight":cloth_end_bit.get_value(),
            "items_json": JSON.stringify(json_val),
            "balance_weight":balance_weight.get_value(),
            "used_weight": cloth_weight.get_value() - balance_weight.get_value()
        }
        Object.assign(d, x) 
    }
    items.value.push(d)
    make_clean()
}

function add_entries(){
    let d = new frappe.ui.Dialog({
        title:"Enter Lay Details",
        size:"extra-large",
        fields: [
            {
                "fieldtype":"Table",
                "fieldname":"cloth_table",
                "fields": [
                    {"fieldname":"rolls","fieldtype":"Int","label":"Roll No","in_list_view":true},
                    {"fieldname":"weight","fieldtype":"Float","label":"Weight (kg's)","in_list_view":true},
                    {"fieldname":"bits","fieldtype":"Int","label":"No of Bits","in_list_view":true},
                    {"fieldname":"end_bit","fieldtype":"Float","label":"End Bit Weight","in_list_view":true},
                    {"fieldname":"balance","fieldtype":"Float","label":"Balance Weight","in_list_view":true}
                ]
            }
        ],
        primray_action_label:"Enter",
        primary_action(values){
            if(!values.cloth_table){
                d.hide()
            }
            else{
                let tot_weight = 0
                let tot_rolls = 0
                let tot_bits = 0
                let tot_end_bit = 0
                let tot_balance = 0
                let items = []
                for(let i = 0 ; i < values.cloth_table.length ; i++){
                    items.push({
                        weight: values.cloth_table[i].weight,
                        rolls: values.cloth_table[i].rolls,
                        bits: values.cloth_table[i].bits,
                        end_bit: values.cloth_table[i].end_bit,
                        balance: values.cloth_table[i].balance    
                    })
                    tot_weight += values.cloth_table[i].weight
                    tot_rolls += values.cloth_table[i].rolls
                    tot_bits += values.cloth_table[i].bits
                    tot_end_bit += values.cloth_table[i].end_bit
                    tot_balance += values.cloth_table[i].balance
                }
                items_json.set_value(JSON.stringify(items))
                items_json.refresh()
                let calculated =[tot_weight, tot_rolls, tot_bits, tot_end_bit, tot_balance]
                set_calculated_value([cloth_weight, cloth_rolls, cloth_bits, cloth_end_bit, balance_weight], calculated)
                show_button4.value = false
                show_button5.value = true
                d.hide()
            }
        }
    })
    d.show()
}

function update_entries(){
    let data = items_json.get_value()
    if(!data){
        data = []
    }
    else if(typeof(data) == "object" && data.length == 0){
        data = []
    }
    else if(typeof(data) == "string"){
        let y = JSON.parse(data)
        if(typeof(y) == "string"){
            y = JSON.parse(y)
        }
        if(y.length == 0){
            data = []
        }
        else{
            if(typeof(y) == "object" && Object.keys(y).length == 0){
                y = []
            }
            data = y
        }
    }
    if(typeof(data) == "string"){
        data = JSON.parse(data)
    }
    let d = new frappe.ui.Dialog({
        title:"Enter Lay Details",
        size:"extra-large",
        fields: [
            {
                "fieldtype":"Table",
                "fieldname":"cloth_table1",
                "data":data,
                "fields": [
                    {"fieldname":"rolls","fieldtype":"Int","label":"Roll No","in_list_view":true},
                    {"fieldname":"weight","fieldtype":"Float","label":"Weight (kg's)","in_list_view":true},
                    {"fieldname":"bits","fieldtype":"Int","label":"NO of Bits","in_list_view":true},
                    {"fieldname":"end_bit","fieldtype":"Float","label":"End Bit Weight","in_list_view":true},
                    {"fieldname":"balance","fieldtype":"Float","label":"Balance Weight","in_list_view":true}
                ]
            }
        ],
        primray_action_label:"Enter",
        primary_action(values){
            if(!values.cloth_table1){
                let calculated =[0,0,0,0,0]
                set_calculated_value([cloth_weight, cloth_rolls, cloth_bits, cloth_end_bit, balance_weight], calculated)
                update_readonly([cloth_weight, cloth_rolls, cloth_bits, cloth_end_bit, balance_weight])
                items_json.set_value(JSON.stringify([]))
                items_json.refresh()
                d.hide()
            }
            else{
                let tot_weight = 0
                let tot_rolls = 0
                let tot_bits = 0
                let tot_end_bit = 0
                let tot_balance = 0
                let items = []
                for(let i = 0 ; i < values.cloth_table1.length ; i++){
                    items.push({
                        weight: values.cloth_table1[i].weight,
                        rolls: values.cloth_table1[i].rolls,
                        bits: values.cloth_table1[i].bits,
                        end_bit: values.cloth_table1[i].end_bit,
                        balance: values.cloth_table1[i].balance    
                    })
                    tot_weight += values.cloth_table1[i].weight
                    tot_rolls += values.cloth_table1[i].rolls
                    tot_bits += values.cloth_table1[i].bits
                    tot_end_bit += values.cloth_table1[i].end_bit
                    tot_balance += values.cloth_table1[i].balance
                }
                items_json.set_value(JSON.stringify(items))
                items_json.refresh()
                let calculated =[tot_weight, tot_rolls, tot_bits, tot_end_bit, tot_balance]
                set_calculated_value([cloth_weight, cloth_rolls, cloth_bits, cloth_end_bit, balance_weight], calculated)
                d.hide()
            }
        }
    })
    d.show()
}

function set_calculated_value(input_fields, calculated_value){
    for(let i = 0 ; i < input_fields.length ; i++){
        input_fields[i].df.read_only = true
        input_fields[i].set_value(calculated_value[i])
        input_fields[i].refresh()
    }
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function delete_item(index){
    make_dirty()
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
    make_dirty()
    let set_json = {}
    for(let i = 0 ; i < set_parameters.length ; i++){
        let val = set_parameters[i].get_value()
        if(val == null || val == ""){
            if(set_parameters[i]['df']["fieldname"] == 'is_same_packing_attribute' || set_parameters[i]['df']["fieldname"] == 'is_set_item'){
                val = 0
            }
            else{
                frappe.throw("Enter the Set Combination")
            }
        }
        set_json[fieldnames[i]] = val
    }
    check_combination(set_json)
    json_val = null
    if(!is_manual_entry){
        json_val = items_json.get_value()
        if(!json_val || json_val == null){
            json_val = []
        }
    }
    let d = {
        "cloth_type":cloth_type.get_value(),
        "dia":cloth_dia.get_value(),
        "colour":cloth_colour.get_value(),
        "shade":cloth_shade.get_value(),
        "weight":cloth_weight.get_value(),
        "no_of_rolls":cloth_rolls.get_value(),
        "fabric_type": fabric_type.get_value(),
        "set_combination":JSON.stringify(set_json)
    }
    if(!is_manual_entry){
        let x = {
            "comments":cloth_comment.get_value(),
            "no_of_bits":cloth_bits.get_value(),
            "end_bit_weight":cloth_end_bit.get_value(),
            "items_json": JSON.stringify(json_val),
            "balance_weight":balance_weight.get_value(),
            "used_weight": cloth_weight.get_value() - balance_weight.get_value()
        }
        Object.assign(d, x) 
    }
    items.value[edit_index.value] = d
    edit_index.value = null
    show_button3.value = false
    show_button5.value = false
    show_button1.value = true
    make_clean()
}

function check_values(){
    let arr = [cloth_type, cloth_dia, cloth_colour, cloth_shade, cloth_weight, cloth_rolls, cloth_bits, fabric_type]
    if(is_manual_entry){
        arr = [cloth_type, cloth_dia, cloth_colour, cloth_shade, cloth_weight, cloth_rolls, fabric_type]
    }
    for(let i = 0 ; i < arr.length ; i++){
        let val = arr[i].get_value()
        if(val == null || val == ""){
            frappe.throw("Enter All the Values to Add an Item")
        }
    }        
}

function check_combination(set_json){
    if(set_json['set_part']){
        let check = false
        Object.keys(part_set_colours).forEach((c)=> {
            let c1 = part_set_colours[c][set_json['major_part']]
            let c2 = part_set_colours[c][set_json['set_part']]
            if(set_json['major_colour'] == c1 && set_json['set_colour'] == c2){
                check = true
            }
        })
        if(!check){
            frappe.throw("Set Combination was Wrong")
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
    if(change){
        df['onchange'] = change
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
    let arr1 = [cloth_type,cloth_dia,cloth_colour,cloth_shade,cloth_weight,cloth_rolls,cloth_bits,cloth_end_bit,cloth_comment,balance_weight, fabric_type]
    for(let i = 0 ; i < arr1.length; i++){
        if(arr1[i]){
            arr1[i].set_value(null)
        }
    }
    for(let i = 0 ; i < set_parameters.length ; i++){
        set_parameters[i].set_value(null)
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
    $(el).find(".items-json").html("");
    $(el).find(".set-detail").html("");
    $(el).find(".fabric-type").html("")
    show_button1.value = true
    show_button2.value = false
    show_button3.value = false
    show_button4.value = false
    show_button5.value = false
    edit_index.value = null
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
                select_attributes.value = r.message
            }
        })  
    }
    if(cur_frm.doc.is_manual_entry){
        frappe.call({
            method: "production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_primary_values",
            args: {
                cutting_laysheet: cur_frm.doc.name,
            },
            callback: function(r){
                primary_values.value = r.message
            }
        })
    }
    if(status == "Label Printed" || status == "Cancelled"){
        disabled.value = true
    }
})

function load_data(item_detail){
    manual_items.value = item_detail.manual_items
    items.value = item_detail.cloth_items
    manual_index.value = Object.keys(manual_items.value).length + 1
}

function add_manual_item(){
    const rowIndex = manual_index.value
    const newItem = {
        colour: null,
        major_colour: null,
        quantity: 1,
        shade: null,
        manual_index: rowIndex,
    }
    primary_values.value.forEach(pv => {
        newItem[pv] = 0
    })
    manual_items.value[rowIndex] = newItem
    manual_index.value = rowIndex + 1
}

function get_set_colour(item, colour){
    item['colour'] = colour
    if(item['colour']){
        make_dirty()
        let val = item['colour']
        console.log(item['colour'])
        frappe.call({
            method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_input_fields",
            args: {
                cutting_marker:cur_frm.doc.cutting_marker,
                colour: val,
                select_attributes: select_attributes.value
            },
            callback: function(r){
                if(r.message){
                    for(let i = 0; i < r.message.input_fields.length; i++){
                        let fieldname = r.message.input_fields[i]["fieldname"]
                        manual_items.value[item['manual_index']][fieldname] = r.message.input_fields[i]['default']
                    }
                }
            }
        })
    }
}

function get_items(){
    if(cur_frm.doc.is_manual_entry){
        Object.keys(manual_items.value).forEach(index => {
            if(!manual_items.value[index]['colour']){
                frappe.throw("Enter Colour")
            }
            if(!manual_items.value[index]['major_colour']){
                frappe.throw("Enter Major Colour")
            }
            if(is_set_item && !manual_items.value[index]['set_colour']){
                frappe.throw("Enter Set Colour")
            }
            if(!manual_items.value[index]['shade']){
                frappe.throw("Enter the Shade")
            }
            let quantity = manual_items.value[index]['quantity']
            if(quantity == "" || quantity == undefined){
                quantity = 0
            }
            if(quantity <= 0){
                frappe.throw("Quantity should be greater than Zero")
            }
            let once = false
            primary_values.value.forEach(pv => {
                let qty = manual_items.value[index][pv]
                if(qty == "" || qty == undefined){
                    manual_items.value[index][pv] = 0
                    qty = 0
                }
                if(qty < 0){
                    frappe.throw("Negative Multiplier's are not Accepted")
                }
                if(qty > 0){
                    once = true
                }        
            })
            if(!once){
                frappe.throw("Enter the Multiplier for atleast one size")
            }
        })
    }
    return {
        "manual_items": manual_items.value,
        "cloth_items": items.value,
    }
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