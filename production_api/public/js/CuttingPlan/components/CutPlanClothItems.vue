<template>
    <div ref="root">
        <table v-if='docstatus !== 0' class="table table-sm table-bordered">
            <table v-if="items && items.length > 0" class="table table-sm table-bordered">
                <tr>
                    <th>S.No.</th>
                    <th>Cloth</th>
                    <th>Cloth Type</th>
                    <th>Colour</th>
                    <th>Dia</th>
                    <th>Required Weight</th>
                    <th>Weight</th>
                </tr>
                <tr v-for="(i, item1_index) in items" :key="item1_index">
                    <td>{{item1_index + 1}}</td>
                    <td>{{ i.cloth_item_variant }}</td>
                    <td>{{ i.cloth_type }}</td>
                    <td>{{ i.colour }}</td>
                    <td>{{ i.dia }}</td>
                    <td>{{ i.required_weight }}</td>
                    <td>{{ i.weight }}</td>
                </tr>
            </table>
        </table>
        <table v-else class="table table-sm table-bordered">
            <table v-if="items && items.length > 0" class="table table-sm table-bordered">
                <tr>
                    <th>S.No.</th>
                    <th>Cloth</th>
                    <th>Cloth Type</th>
                    <th>Colour</th>
                    <th>Dia</th>
                    <th>Required Weight</th>
                    <th>Weight</th>
                </tr>
                <tr v-for="(i, item1_index) in items" :key="item1_index">
                    <td>{{item1_index + 1}}</td>
                    <td>{{ i.item }}</td>
                    <td>{{ i.cloth_type }}</td>
                    <td>{{ i.colour }}</td>
                    <td>{{ i.dia }}</td>
                    <td>{{ i.required_weight }}</td>
                    <td>
                        <form>
                            <input
                                class="form-control"
                                type="number"
                                v-model.number="i.weight"
                                min="0"
                                step="0.001"
                                @blur="update_doc()"
                            />
                        </form>
                    </td>
                </tr>
            </table>
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
