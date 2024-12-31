<template>
    <div ref="root">
        <div v-if="show_title">
            <h4>Order Items</h4>
        </div>
        <table class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td v-if="i.primary_attribute">
                    <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                        <tr>
                            <th>S.No.</th>
                            <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
                            <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                {{ j }}
                            </th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td><input type="checkbox" v-model="checkbox_value" @change="update_qty(item_index, item1_index)">{{item1_index + 1}}</td>
                            <td v-for="(k, idx) in j.attributes" :key="idx">{{k}}</td>
                            <td v-for="(k, idx) in j.values" :key="idx">
                                <div v-if="k > 0">
                                    {{k}}
                                    <div class="input-field" :class="get_input_class(idx, item1_index)"></div>
                                </div>
                                <div v-else>--</div>
                            </td>
                        </tr>
                    </table>
                </td>
                <td v-else>
                    <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                        <tr>
                            <th>S.No.</th>
                            <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
                            <th>Quantity</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <template v-if="i.final_state_attr">
                                <td v-for="(k, idx) in j.attributes" :key="idx">{{ k }}</td>
                            </template>
                            <td>{{ j.values.qty }}</td>
                        </tr>
                    </table>
                </td>
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
function load_data(item){
    items.value = item;
    if(item.length > 0){
        show_title.value = true
    }
}

function create_input_classes(){
    for(let i = 0 ; i < items.value[0].items.length; i++){
        items.value[0].items[i]['entered_qty'] = {}
        items.value[0].items[i]['work_order_qty'] = {}
        Object.keys(items.value[0].items[i].values).forEach((key,value)=> {
            let val = items.value[0].items[i].values[key]
            let input = createInput(key,i,val)
            items.value[0].items[i]['work_order_qty'][key] = 0
            items.value[0].items[i]['entered_qty'][key] = input
        })
    }
}

function update_qty(idx1, idx2){
    if(!checkbox_value){
        Object.keys(items.value[idx1].items[idx2].values).forEach((key,value)=> {
            let input = items.value[idx1].items[idx2]['entered_qty'][key]
            input.set_value(0)
        })
    }
    else{
        Object.keys(items.value[idx1].items[idx2].values).forEach((key,value)=> {
            let input = items.value[idx1].items[idx2]['entered_qty'][key]
            input.set_value(items.value[idx1].items[idx2]['values'][key])
        })
    }
    

}
function createInput(key,index,val){
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
    input.set_value(val)
    input.refresh()
    input['df']['onchange'] = ()=>{
        let input_value = input.get_value()
        items.value[0].items[index]['work_order_qty'][key] = input_value;
    }
    return input
}

function get_input_class(key,index){
    key = key.replaceAll(" ","-")
    return key+"-"+index;
}

function get_items(){
    // for(let i = 0 ; i < items.value[0].items.length; i++){
    //     Object.keys(items.value[0].items[i].values).forEach((key,value)=> {
    //         let entered = items.value[0].items[i]['work_order_qty'][key]
    //         let limit = items.value[0].items[i]['values'][key]
    //         if(entered > limit){
    //             frappe.throw(`For ${key} ${items.value[0].items[i]['primary_attribute']}, Entered value was ${entered}, but the limit is ${limit}`)
    //         }
    //     })
    // }
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
