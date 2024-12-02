<template>
    <div ref="root">
        <div v-if="items">
            <h4>Completed Cut Quantity</h4>        
        </div>
        <table class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <template v-if="!i.is_set_item">
                    <td>
                        <strong>Panels:</strong>
                        <div v-for="(panel,index) in i[i.stiching_attr]" :key="panel" class="panel-column">
                            {{ panel }}<span v-if="index < i[i.stiching_attr].length - 1">,</span>
                        </div>
                    </td>
                </template>
            </tr>
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td>
                    <table v-if="i.items && i.items.length > 0" class="table table-sm table-bordered">
                        <tr>
                            <th>S.No.</th>
                            <th v-for="(j, idx) in i.final_state_attr" :key="idx">{{ j }}</th>
                            <th v-for="(j, idx) in i.primary_attribute_values" :key="idx">
                                {{ j }}
                            </th>
                            <th v-if="i.is_set_item">Panels</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{item1_index + 1}}</td>
                            <td v-for="(k, idx) in j.attributes" :key="idx">{{k}}</td>
                            <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                <div v-if="j.values[k] > 0">
                                    {{ j.values[k] }}
                                </div>
                                <div v-else>--</div>
                            </td>
                            <td v-if='i.is_set_item'>
                                <div v-for="panel in i[i.stiching_attr][j.attributes[i.set_item_attr]]" :key="panel">
                                    {{panel}}
                                </div>
                            </td>
                
                        </tr>
                        <tr>
                            <td>Total</td>
                            <td v-for="(j, idx) in i.final_state_attr" :key="idx"></td>
                            <td v-for="(j, idx) in i.total_qty" :key="idx">{{j}}</td>
                            <td></td>
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
        console.log(e)
    }
}

defineExpose({
    load_data,
})
</script>
<style scoped>
.panel-column {
    display: inline; /* Display items in a single line */
}
</style>
