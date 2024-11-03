<template>
    <div ref="root">
        <table v-if='docstatus !== 0' class="table table-sm table-bordered">
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
                            <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                <div v-if="j.values[k] > 0">
                                    {{j.values[k] }}
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
                            <template v-if='j.values.qty > 0'>
                                <td>
                                    {{j.values.qty}}
                                </td>
                            </template>
                            <template v-else>
                                <td>--</td>
                            </template>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <table v-else class="table table-sm table-bordered">
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
                            <td v-for="(k, idx) in Object.keys(j.values)" :key="idx">
                                <form>
                                    <input
                                        class="form-control"
                                        type="number"
                                        v-model.number="j.values[k]"
                                        min="0"
                                        @blur="update_doc()"
                                    />
                                </form>
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
                            <td>
                                <form>
                                    <input
                                        class="form-control"
                                        type="number"
                                        v-model.number="j.values.qty"
                                        min="0"
                                        @blur="update_doc()"
                                    />
                                </form>
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
let show_title = ref(false)
let docstatus = ref(0)
function load_data(item){
    docstatus.value = cur_frm.doc.docstatus
    items.value = item;
    if(item.length > 0){
        show_title.value = true
    }
}
function update_doc(){
    cur_frm.dirty()
}
function get_items(){
    return items.value
}

defineExpose({
    load_data,
    get_items,
})
</script>
