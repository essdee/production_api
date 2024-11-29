<template>
    <div ref="root" v-if="Object.keys(items).length > 0">
        <div v-for="item in Object.keys(items)" :key="item">
            <div v-if='items[item].length > 0'>
                <h4 style="line-height:0;">{{item}}</h4>
                <table class="table table-sm table-bordered">
                    <tr>
                        <th>Action</th>
                        <th>Master</th>
                        <th>Work Station</th>
                    </tr>
                    <tr v-for="(value,index) in items[item]" :key="index">
                        <td>{{value.action}}</td>
                        <td>{{value.parent}}</td>
                        <td>
                            <div :class="get_input_class(item,value.action,value.parent)"></div>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
</template>
<script setup>
import {ref} from 'vue';

let root = ref(null)
let sample_doc = ref({})
let items = ref({})
function load_data(item){
    items.value = item
}

function set_attributes() {
    if(!items.value){
        return
    }
    if (items.value) {
        Object.keys(items.value).forEach(colour => {
            for(let i = 0; i < items.value[colour].length ; i++){
                let action = items.value[colour][i]['action']
                let master = items.value[colour][i]['parent']
                let work_station = items.value[colour][i]['work_station']
                let input =createInput(colour, action, master,work_station)
                items.value[colour][i]['work_station'] = input
            }
        })
    }
}

function createInput(colour, action, master, work_station){
    let parent_class = "." + get_input_class(colour,action,master);
    let el = root.value
    let input =  frappe.ui.form.make_control({
        parent: $(el).find(parent_class),
        df:{
            "fieldtype":"Link",
            "fieldname": colour+"_"+action+"_"+master,
            "options":"Work Station",
            get_query:function(){
                return{
                    filters: {
                        "action":action,
                    }
                }
            }
        } ,
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".control-label").remove();
    $(el).find(".visually-hidden").remove();

    input.set_value(work_station)
    input.refresh()
    return input
}

function get_input_class(colour, action , master){
    colour = colour.replaceAll(" ","-")
    action = action.replaceAll(" ","-")
    master = master.replaceAll(" ","-")
    return colour+"-"+action+"-"+master;
}

function get_items(){
    Object.keys(items.value).forEach(colour => {
        for(let i = 0; i < items.value[colour].length ; i++){
            let input = items.value[colour][i]['work_station']
            items.value[colour][i]['work_station'] = input.get_value() 
        }
    })
    return items.value
}

defineExpose({
    load_data,
    set_attributes,
    get_items,
})
</script>
<style scoped>
.form-group{
	margin-bottom:0 !important;
}
</style>