<template>
    <div ref="root">
        <div v-if="show_title">
            <h4>Order Items</h4>
            <div style="display:flex;">
                <div>Select</div> <div style="padding: 2px 0 0 5px;"><input type="checkbox" v-model="checkbox_value" @change="update_checkbox($event)"></div>
            </div>
        </div>
        <table class="table table-sm table-bordered" >
            <tr v-for="(i, item_index) in items" :key="item_index">
                <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                    <tr>
                        <th>S.No.</th>
                        <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                        <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                    </tr>
                    <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                        <td><input type="checkbox" v-model="checkboxes[item1_index]" @change="update_qty(item_index, item1_index)">{{item1_index + 1}}</td>
                        <td v-for="attr in i.attributes" :key="attr">
                            {{ j.attributes[attr] }}
                            <span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
                            <span v-else-if="attr == 'Colour' && !j.is_set_item && j.attributes[attr] != j.item_keys['major_colour'] && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
                        </td>
                        <td v-for="attr in Object.keys(j.values)" :key="attr">
                            <div v-if="j.values[attr]['qty'] > 0">
                                <div class="input-field" :class="get_input_class(attr, item1_index)"></div>
                            </div>
                            <div v-else>--</div>
                        </td>
                    </tr>
                </table>
            </tr>
        </table>
    </div>  
</template>

<script setup>
import {ref} from 'vue';

let checkbox_value = true
let items = ref(null)
let show_title = ref(false)
let sample_doc = ref({})
let root= ref(null)
let checkboxes = ref([])
function load_data(item){
    items.value = item;
    if(item.length > 0){
        show_title.value = true
        for(let i = 0 ; i < items.value[0].items.length; i++){
            checkboxes.value.push(true)
        }
    }
}

function create_input_classes(){
    for(let i = 0 ; i < items.value[0].items.length; i++){
        items.value[0].items[i]['entered_qty'] = {}
        items.value[0].items[i]['work_order_qty'] = {}
        Object.keys(items.value[0].items[i].values).forEach((key,value)=> {
            let val = items.value[0].items[i].values[key]['qty']
            let input = createInput(key,i,val)
            items.value[0].items[i]['work_order_qty'][key] = 0
            items.value[0].items[i]['entered_qty'][key] = input
        })
    }
}

function update_checkbox(event){
    let val = event.target.checked
    for(let i = 0 ; i < items.value[0].items.length; i++){
        checkboxes.value[i] = val
        Object.keys(items.value[0].items[i].values).forEach((key,value)=> {
            if(items.value[0].items[i]['entered_qty'][key]){
                if(val){
                    let input = items.value[0].items[i]['entered_qty'][key]
                    input.set_value(items.value[0].items[i]['values'][key]['qty'])
                }
                else{
                    let input = items.value[0].items[i]['entered_qty'][key]
                    input.set_value(0)
                }
            }
        })
    }
}

function update_qty(idx1, idx2){
    if(!checkboxes.value[idx2]){
        Object.keys(items.value[idx1].items[idx2].values).forEach((key,value)=> {
            if(items.value[idx1].items[idx2]['entered_qty'][key]){
                let input = items.value[idx1].items[idx2]['entered_qty'][key]
                input.set_value(0)
            }
        })
    }
    else{
        Object.keys(items.value[idx1].items[idx2].values).forEach((key,value)=> {
            if(items.value[idx1].items[idx2]['entered_qty'][key]){
                let input = items.value[idx1].items[idx2]['entered_qty'][key]
                input.set_value(items.value[idx1].items[idx2]['values'][key]['qty'])
            }
        })
    }
}

function createInput(key,index,val){
    if(val > 0){
        let parent_class = "." + get_input_class(key,index);
    
        let el = root.value
        let df = {
            fieldtype: 'Int',
            fieldname: key+""+index,
        } 
        let input =  frappe.ui.form.make_control({
            parent: $(el).find(parent_class),
            df:df,
            doc: sample_doc.value,
            render_input: true,
        });

        $(el).find(".control-label").remove();
        if(val != 0){
            input.set_value(val)
            input.refresh()
        }
        input['df']['onchange'] = ()=>{
            let input_value = input.get_value()
            items.value[0].items[index]['work_order_qty'][key] = input_value;
        }
        return input
    }
    
}

function get_input_class(key,index){
    key = key.replaceAll(" ","-")
    return key+"-"+index;
}

function get_items(){
    for(let i = 0 ; i < items.value[0].items.length; i++){
        Object.keys(items.value[0].items[i].values).forEach((key,value)=> {
            if(items.value[0].items[i]['entered_qty'][key]){
                let entered = items.value[0].items[i]['entered_qty'][key].get_value()
                items.value[0].items[i]['entered_qty'][key] = entered
            }
            // let limit = items.value[0].items[i]['values'][key]
            // if(entered > limit){
            //     frappe.throw(`For ${key} ${items.value[0].items[i]['primary_attribute']}, Entered value was ${entered}, but the limit is ${limit}`)
            // }
        })
    }
    return items.value
}

defineExpose({
    load_data,
    get_items,
    create_input_classes,
})
</script>

<style scoped>
.input-field {
    margin-bottom: -5;
}
</style>
