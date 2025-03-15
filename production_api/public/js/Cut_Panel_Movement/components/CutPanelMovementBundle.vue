<template>
    <div>
        <div v-if="items.is_set_item">
            <div v-for="colour in Object.keys(items.data)" :key="colour">
                {{ get_part_and_length(colour) }}
                <table class="table table-sm table-bordered" v-if="items.data[colour] && items.data[colour].length > 0">
                    <tr>
                        <th class='table-head' :colspan="2">
                            <span v-if='docstatus == 0'>
                                <input type='checkbox' @change='update_table(colour, $event.target.checked)'>
                            </span>
                            <strong>Lot No:</strong> {{ lot }}
                        </th>
                        <th class='table-head' :colspan="3"><strong>Style Name:</strong> {{ item }}</th>
                        <th class='table-head' :colspan="part_length + 1"><strong>Colour:</strong> {{ colour }}</th>
                    </tr>
                    <tr>
                        <td class='table-data' style="width:10%;"><strong>S.No</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Lay No</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Bundle No</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Size</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Shade</strong></td>
                        <td class='table-data' v-for="panel in (items.panels[part] || [])" :key="panel"><strong>{{ panel }}</strong></td>
                        <td v-if="items.panels[part].length > 1" class='table-data' style="width:10%;"><strong>Total</strong></td>
                    </tr>
                    <tr v-for="(row, index) in items.data[colour]" :key="index">
                        <td class='table-data' style="width:10%;">
                            {{ index + 1 }}
                            <span v-if='docstatus == 0'>
                                <input type='checkbox' v-model="row.bundle_moved" @change='update_row(row, colour, index)'>
                            </span>
                        </td>
                        <td class='table-data' style="width:10%;">{{ row.lay_no }}</td>
                        <td class='table-data' style="width:10%;">{{ row.bundle_no }}</td>
                        <td class='table-data' style="width:10%;">{{ row.size }}</td>
                        <td class='table-data' style="width:10%;">{{ row.shade }}</td>
                        <template v-for="panel in (items.panels?.[part] || [])" :key="panel">
                            <td class='table-data'>
                                <span v-if="docstatus == 0">
                                    <span v-if='row[panel] && row[panel] > 0'>
                                        {{ row[panel] }}
                                        <input type='checkbox' v-model="row[panel+'_moved']" @change='update_panel(row, panel+"_moved")'>
                                    </span>
                                    <span v-else>0</span>
                                </span>
                                <span v-else>
                                    <span v-if='row[panel] && row[panel] > 0 && row[panel+"_moved"]'>{{ row[panel] }}</span>
                                    <span v-else>0</span>
                                </span>
                            </td>
                        </template>
                        <td v-if="items.panels[part].length > 1" class='table-data'><strong>{{row.total}}</strong></td>
                    </tr>
                    <tr v-if="items.total_pieces">
                        <td class='table-data' style="width:10%;"><strong>Total</strong></td>
                        <td class='table-data' style="width:10%;"></td>
                        <td class='table-data' style="width:10%;"></td>
                        <td class='table-data' style="width:10%;"></td>
                        <td class='table-data' style="width:10%;"></td>
                        <template v-for="panel in (items.panels[part] || [])" :key="panel">
                            <td class='table-data'>
                                <strong>
                                    <span v-if='items.total_pieces[colour][panel]'>
                                        {{items.total_pieces[colour][panel]}}
                                    </span>
                                    <span v-else>
                                        0
                                    </span>
                                </strong>
                            </td>
                        </template>
                        <td class='table-data'><strong>{{items.total_bundles[colour]}}</strong></td>
                    </tr>
                </table>
            </div>
        </div>
        <div v-else-if="items.data">
            <div v-for="colour in Object.keys(items.data)" :key="colour">
                <table class="table table-sm table-bordered">
                    <tr>
                        <th class='table-head' :colspan="2">
                            <span v-if='docstatus == 0'>
                                <input type='checkbox' @change='update_table(colour, $event.target.checked)'>
                            </span>
                            <strong>Lot No:</strong> {{ lot }}
                        </th>
                        <th class='table-head' :colspan="3"><strong>Style Name:</strong> {{ item }}</th>
                        <th class='table-head' :colspan="items.panels.length"><strong>Colour:</strong> {{ colour }}</th>
                    </tr>
                    <tr>
                        <td class='table-data' style="width:10%;"><strong>S.No</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Lay No</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Bundle No</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Size</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Shade</strong></td>
                        <td class='table-data' v-for="panel in (items.panels || [])" :key="panel"><strong>{{ panel }}</strong></td>
                        <td class='table-data' style="width:10%;"><strong>Total</strong></td>
                    </tr>
                    <tr v-for="(row, index) in items.data[colour]" :key="index">
                        <td class='table-data' style="width:10%;">
                            {{ index + 1 }}
                            <span v-if='docstatus == 0'>
                                <input type='checkbox' v-model="row.bundle_moved" @change='update_row(row, colour, index)'>
                            </span>
                        </td>
                        <td class='table-data' style="width:10%;">{{ row.lay_no }}</td>
                        <td class='table-data' style="width:10%;">{{ row.bundle_no }}</td>
                        <td class='table-data' style="width:10%;">{{ row.size }}</td>
                        <td class='table-data' style="width:10%;">{{ row.shade }}</td>
                        <template v-for="panel in (items.panels || [])" :key="panel">
                            <td class='table-data'>
                                <span v-if="docstatus == 0">
                                    <span v-if='row[panel] && row[panel] > 0'>
                                        {{ row[panel] }}
                                        <input type='checkbox' v-model="row[panel+'_moved']" @change='update_panel(row, panel+"_moved")'>
                                    </span>
                                    <span v-else>0</span>
                                </span>
                                <span v-else>
                                    <span v-if='row[panel] && row[panel] > 0 && row[panel+"_moved"]'>{{ row[panel] }}</span>
                                    <span v-else>0</span>
                                </span>
                            </td>
                        </template>
                        <td v-if="items.panels.length > 1" class='table-data'><strong>{{row.total}}</strong></td>
                    </tr>
                    <tr v-if="items.total_pieces">
                        <td class='table-data' style="width:10%;"><strong>Total</strong></td>
                        <td class='table-data' style="width:10%;"></td>
                        <td class='table-data' style="width:10%;"></td>
                        <td class='table-data' style="width:10%;"></td>
                        <td class='table-data' style="width:10%;"></td>
                        <template v-for="panel in (items.panels || [])" :key="panel">
                            <td class='table-data'>
                                <strong>
                                    <span v-if='items.total_pieces[colour][panel]'>
                                        {{items.total_pieces[colour][panel]}}
                                    </span>
                                    <span v-else>
                                        0
                                    </span>
                                </strong>
                            </td>
                        </template>
                        <td class='table-data'><strong>{{items.total_bundles[colour]}}</strong></td>
                    </tr>
                </table>
            </div>
        </div>
        <div v-if="items.accessory_data && items.accessory_data.length > 0">
            <h3>Accessories</h3>
            <table class="table table-sm table-bordered" style="width:100%;">
                <tr>
                    <th class='table-head' style="width:10%;"><strong>S.No</strong></th>
                    <th class='table-head' style="width:15%;"><strong>Cloth Type</strong></th>
                    <th class='table-head' style="width:20%;"><strong>Colour</strong></th>
                    <th class='table-head' style="width:15%;"><strong>Shade</strong></th>
                    <th class='table-head' style="width:15%;"><strong>Dia</strong></th>
                    <th class='table-head' style="width:25%;"><strong>Weight</strong></th>
                </tr>
                <tr v-for="(data, idx) in items.accessory_data" :key="data">
                    <td class='table-data'>{{ idx + 1 }}</td>
                    <td class='table-data'>{{ data.cloth_type }}</td>
                    <td class='table-data'>{{ data.colour }}</td>
                    <td class='table-data'>{{ data.shade }}</td>
                    <td class='table-data'>{{ data.dia }}</td>
                    <td>
                        <div v-if="docstatus == 0">
                            Accessory Used: {{ data.weight }} Kg's
                            <input type="number" step="0.001" class="form-control" v-model="data.moved_weight" @blur="update_doc()"/>
                        </div>
                        <div v-else>
                            Accessory Moved: {{data.moved_weight}} Kg's
                        </div>
                    </td>
                </tr>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';

let items = ref({});
let splits = ref([]);
let length = ref(0);
let part = ref(null)
let part_length = ref(0);
let lot = null;
let item = null;
let docstatus = cur_frm.doc.docstatus

function load_data(data) {
    items.value = data;
    lot = cur_frm.doc.lot;
    item = cur_frm.doc.item;
}

function update_row(item, colour, index, bundle_moved = 0){
    let return_val = false
    if(items.value.is_set_item){
        let pt = get_part(colour)
        for(let i = 0 ; i < items.value['panels'][pt].length ; i++){
            let panel = items.value['panels'][pt][i]
            if(item.hasOwnProperty(panel)){
                if(bundle_moved == 0){
                    if(item.bundle_moved == 1 || item.bundle_moved == true){
                        return_val = true
                        items.value['data'][colour][index][panel+"_moved"] = true
                    }
                    else{
                        return_val = false
                        items.value['data'][colour][index][panel+"_moved"] = false
                    }
                }
                else if(bundle_moved == true){
                    items.value['data'][colour][index][panel+"_moved"] = true
                }
                else{
                    items.value['data'][colour][index][panel+"_moved"] = false
                }
            }
        }
    }
    else{
        for(let i = 0 ; i < items.value['panels'].length ; i++){
            let panel = items.value['panels'][i]
            if(item.hasOwnProperty(panel)){
                if(bundle_moved == 0){
                    if(item.bundle_moved == 1 || item.bundle_moved == true){
                        return_val = true
                        items.value['data'][colour][index][panel+"_moved"] = true
                    }
                    else{
                        return_val = false
                        items.value['data'][colour][index][panel+"_moved"] = false
                    }
                }
                else if(bundle_moved == true){
                    items.value['data'][colour][index][panel+"_moved"] = true
                }
                else{
                    items.value['data'][colour][index][panel+"_moved"] = false
                }
            }
        }
    }
    update_doc()
    return return_val
}

function update_panel(item, panel){
    update_doc()
    if(item.panel == 1 || item.panel == true){
        return true
    }
    return false
}

function update_table(colour, val){
    for(let i = 0 ; i < items.value['data'][colour].length ; i++){
        items.value['data'][colour][i]['bundle_moved'] = val
        update_row(items.value['data'][colour][i],colour, i, val)
    }
}

function update_doc(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function get_part_and_length(colour) {
    part.value = get_part(colour)
    let x = items.value['panels'][part.value].length
    part_length.value = x;
}

function get_part(colour){
    let spl = colour.split("-");
    let len = spl.length;
    return spl[len - 1]
}

function get_items(){
    return items.value
}

defineExpose({
    load_data,
    get_items
});

</script>

<style>
.table-head, .table-data {
    text-align:center !important;
}
</style>
