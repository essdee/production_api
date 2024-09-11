<template>
    <div ref="root">
        <div v-if="show_title" class="pt-5">
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
                            <td>{{item1_index + 1}}</td>
                            <td v-for="(k, idx) in j.attributes" :key="idx">{{k}}</td>
                            <td v-for="(k, idx) in j.values" :key="idx">
                                <div v-if="k > 0">{{k}}</div>
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
                            <th>Qty</th>
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

let items = ref(null)
let show_title = ref(false)
function load_data(item){
    items.value = item;
    if(item.length > 0){
        show_title.value = true
    }
}
defineExpose({
    load_data,
})
</script>
