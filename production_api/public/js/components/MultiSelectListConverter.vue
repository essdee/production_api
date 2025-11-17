<template>
    <div>  
        <div class="border-style">
            <label style="font-weight: 600; color: #333;">Select Type</label>
            <select v-model="select_value" class="select-style" @blur="convert_list()">
                <option v-for="option in options">{{ option }}</option>
            </select>
            <select v-model="list_type" class="select-style" @blur="convert_list()">
                <option v-for="option in list_type_options">{{ option }}</option>
            </select>
            <label style="font-weight: 600; color: #333;">Enter Values</label>
            <textarea v-model="text_area_val" rows="4" cols="50" class="textarea-style" @blur="convert_list()"></textarea>
        </div>    
    </div> 
</template>    

<script setup>

import {ref, watch} from 'vue';

const props = defineProps({
    items_list: {
        type: Array,
        default: () => []
    }
})
let select_value = ref(null)
let list_type = ref(null)
let text_area_val = ref(null)
let options = ref([])
let list_type_options = ['Comma Separated', 'List Type']
let list = ref([])

function convert_list(){
    if (list_type.value == 'List Type' && text_area_val.value){
        let result = text_area_val.value.split("\n").map(line => line.trim()).filter(line => line !== "");
        console.log(result)
        list.value = result
    }
    else if(list_type.value == 'Comma Separated' && text_area_val.value){
        let result = text_area_val.value.split(",")
        console.log(result)
        list.value = result
    }
}

watch(
    () => props.items_list,
    (newItems) => {
        options.value = newItems 
    },
    { immediate: true }
)

defineExpose({
    select_value,
    list,
})

</script>

<style scoped>
.border-style{
    display: flex; 
    flex-direction: column; 
    gap: 10px; 
    width: 100%; 
    padding: 16px; 
    background: #f9fafb; 
    border: 1px solid #dcdcdc; 
    border-radius: 10px; 
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}
.select-style{
    padding: 8px 10px; 
    border-radius: 6px; 
    border: 1px solid #ccc; 
    font-size: 14px;
    outline: none;
}
.textarea-style{
    padding: 10px; 
    border-radius: 6px; 
    border: 1px solid #ccc; 
    resize: vertical; 
    font-size: 14px; 
    line-height: 1.5;
    outline: none;
}
.button-style{
    background-color: #2e7d32; 
    color: white; 
    border: none; 
    padding: 8px 12px; 
    border-radius: 6px; 
    font-weight: 500;
    cursor: pointer;
    transition: 0.2s ease;
}
</style>