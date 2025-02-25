<template>
    <div ref="root">
        <div v-if="items">
            <h4>Incompleted Cut Quantity</h4>        
        </div>
        <table class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td>
                <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                    <tr>
                        <th>S.No.</th>
                        <th v-for="(j, idx) in i.attributes" :key="idx">{{ j }}</th>
                        <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                            {{ j }}
                        </th>
                    </tr>
                    <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                        <td>{{item1_index + 1}}</td>
                        <td v-for="(k, idx) in i.attributes" :key="idx">{{j.attributes[k]}}</td>
                        <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                            <div v-for="(panel,idx2) in Object.keys(j.values[k])" :key='idx2'>
                                <span v-if="j.values[k][panel] > 0">
                                    {{panel}} {{j.values[k][panel]}}
                                </span>
                            </div>
                        </td>
                    </tr>
                </table>
                </td>
            </tr>
        </table>
    </div>  
</template>

<script setup>
import {ref} from 'vue';

let items = ref(null)
function load_data(item){
    try {
        items.value = JSON.parse(item);
    } catch(e) {
        console.log(e);
    }
}

defineExpose({
    load_data,
})
</script>
