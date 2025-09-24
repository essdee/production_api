<template>
    <div>
        <div style="width:100%;" v-if="items && Object.keys(items).length > 0">
            <div v-for="part_value in Object.keys(items['ocr_data'])" style="width:100%;">
                <div style="display:flex;width:100%;gap:20px;">
                    <div style="width:80%;">
                        <table class="table table-sm table-sm-bordered bordered-table">
                            <thead class="dark-border">
                                <tr>
                                    <th :colspan="2">{{ item_name }} <span v-if="part_value != 'Item'"> {{ part_value }} </span></th>
                                    <th v-for="size in items.primary_values">
                                        {{ size }}
                                    </th>
                                    <th>Total</th>
                                </tr>
                            </thead>
                            <tbody class="dark-border">
                                <tr>
                                    <th :colspan="2">Cutting Qty</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['cutting_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['cutting'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Finishing Inward</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['dc_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['dc_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference</th>
                                    <td v-for="size in items.primary_values" 
                                        :style="get_style(items['ocr_data'][part_value]['total'][size]['dc_qty'] - items['ocr_data'][part_value]['total'][size]['cutting_qty'])">
                                        {{ items['ocr_data'][part_value]['total'][size]['dc_qty'] - items['ocr_data'][part_value]['total'][size]['cutting_qty'] }}
                                    </td>
                                    <th :style="get_style(items['ocr_data'][part_value]['dc_qty'] - items['ocr_data'][part_value]['cutting'])">
                                        {{ items['ocr_data'][part_value]['dc_qty'] - items['ocr_data'][part_value]['cutting'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Packed Box</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['packed_box'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['packed_box'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Packed Box Qty</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['packed_box_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['packed_box_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference</th>
                                    <td v-for="size in items.primary_values" 
                                        :style="get_style(items['ocr_data'][part_value]['total'][size]['packed_box_qty'] - items['ocr_data'][part_value]['total'][size]['dc_qty'])">
                                        {{ items['ocr_data'][part_value]['total'][size]['packed_box_qty'] - items['ocr_data'][part_value]['total'][size]['dc_qty'] }}
                                    </td>
                                    <th :style="get_style(items['ocr_data'][part_value]['packed_box_qty'] - items['ocr_data'][part_value]['dc_qty'])">
                                        {{ items['ocr_data'][part_value]['packed_box_qty'] - items['ocr_data'][part_value]['dc_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :rowspan="Object.keys(items['ocr_data'][part_value]['data']).length + 1"
                                    style="vertical-align: middle;">Rejection Pieces</th>
                                </tr>
                                <template v-for="colour in Object.keys(items['ocr_data'][part_value]['data'])">
                                    <tr>
                                        <th>{{ colour.split("@")[0] }}</th>
                                        <td v-for="size in items.primary_values">
                                            <span v-if="items['ocr_data'][part_value]['data'][colour]['values'][size]['rejected'] != 0">
                                                {{ items['ocr_data'][part_value]['data'][colour]['values'][size]['rejected'] }}
                                            </span>
                                            <span v-else>
                                                --
                                            </span>    
                                        </td>
                                        <th>
                                            {{ items['ocr_data'][part_value]['data'][colour]['colour_total']['rejected'] }}
                                        </th>
                                    </tr>
                                </template>
                                <tr>
                                    <th :colspan="2">Total</th>
                                    <th v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['rejected'] }}
                                    </th>
                                    <th>
                                        {{ items['ocr_data'][part_value]['rejected'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :rowspan="Object.keys(items['ocr_data'][part_value]['data']).length + 1"
                                    style="vertical-align: middle;">Loose Piece</th>
                                </tr>
                                <template v-for="colour in Object.keys(items['ocr_data'][part_value]['data'])">
                                    <tr>
                                        <th>{{ colour.split("@")[0] }}</th>
                                        <td v-for="size in items.primary_values">
                                            <span v-if="items['ocr_data'][part_value]['data'][colour]['values'][size]['loose_piece'] != 0">
                                                {{ items['ocr_data'][part_value]['data'][colour]['values'][size]['loose_piece'] }}
                                            </span>
                                            <span v-else>
                                                --
                                            </span>    
                                        </td>
                                        <th>
                                            {{ items['ocr_data'][part_value]['data'][colour]['colour_total']['loose_piece'] }}
                                        </th>
                                    </tr>
                                </template>
                                <tr>
                                    <th :colspan="2">Total</th>
                                    <th v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['loose_piece'] }}
                                    </th>
                                    <th>
                                        {{ items['ocr_data'][part_value]['loose_piece'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :rowspan="Object.keys(items['ocr_data'][part_value]['data']).length + 1"
                                    style="vertical-align: middle;">Loose Piece Set</th>
                                </tr>
                                <template v-for="colour in Object.keys(items['ocr_data'][part_value]['data'])">
                                    <tr>
                                        <th>{{ colour.split("@")[0] }}</th>
                                        <td v-for="size in items.primary_values">
                                            <span v-if="items['ocr_data'][part_value]['data'][colour]['values'][size]['loose_piece_set'] != 0">
                                                {{ items['ocr_data'][part_value]['data'][colour]['values'][size]['loose_piece_set'] }}
                                            </span>
                                            <span v-else>
                                                --
                                            </span>    
                                        </td>
                                        <th>
                                            {{ items['ocr_data'][part_value]['data'][colour]['colour_total']['loose_piece_set'] }}
                                        </th>
                                    </tr>
                                </template>
                                <tr>
                                    <th :colspan="2">Total</th>
                                    <th v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['loose_piece_set'] }}
                                    </th>
                                    <th>
                                        {{ items['ocr_data'][part_value]['loose_piece_set'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :rowspan="Object.keys(items['ocr_data'][part_value]['data']).length + 1"
                                    style="vertical-align: middle;">Rework Pieces</th>
                                </tr>
                                <template v-for="colour in Object.keys(items['ocr_data'][part_value]['data'])">
                                    <tr>
                                        <th>{{ colour.split("@")[0] }}</th>
                                        <td v-for="size in items.primary_values">
                                            <span v-if="items['ocr_data'][part_value]['data'][colour]['values'][size]['pending'] != 0">
                                                {{ items['ocr_data'][part_value]['data'][colour]['values'][size]['pending'] }}
                                            </span>
                                            <span v-else>
                                                --
                                            </span>    
                                        </td>
                                        <th>
                                            {{ items['ocr_data'][part_value]['data'][colour]['colour_total']['pending'] }}
                                        </th>
                                    </tr>
                                </template>
                                <tr>
                                    <th :colspan="2">Total</th>
                                    <th v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['pending'] }}
                                    </th>
                                    <th>
                                        {{ items['ocr_data'][part_value]['pending'] }}
                                    </th>
                                </tr>
                            </tbody>    
                        </table>
                    </div>
                    <div style="width:20%;">    
                        <table class="table table-sm table-sm-bordered bordered-table">
                            <thead class="dark-border">
                                <tr>
                                    <th>{{ part_value }}</th>
                                    <th>Difference</th>
                                </tr>
                            </thead>
                            <tbody class="dark-border">    
                                <tr>
                                    <td>Cut to Dispatch</td>
                                    <td> 
                                        {{ get_percentage(items['ocr_data'][part_value]['cutting'], items['ocr_data'][part_value]['packed_box_qty']) }}
                                    </td>
                                </tr>
                                <tr>
                                    <td>Cut to Inward</td>
                                    <td>
                                        {{ get_percentage(items['ocr_data'][part_value]['cutting'], items['ocr_data'][part_value]['dc_qty']) }}
                                    </td>
                                </tr>
                                <tr>
                                    <td>Inward to Dispatch</td>
                                    <td>
                                        {{ get_percentage(items['ocr_data'][part_value]['dc_qty'], items['ocr_data'][part_value]['packed_box_qty']) }}
                                    </td>
                                </tr>
                                <tr>
                                    <td>Loose Piece</td>
                                    <td>
                                        {{ get_percentage(items['ocr_data'][part_value]['dc_qty'], items['ocr_data'][part_value]['loose_piece']) }}
                                    </td>
                                </tr>
                                <tr>
                                    <td>Rejection</td>
                                    <td>
                                        {{ get_percentage(items['ocr_data'][part_value]['dc_qty'], items['ocr_data'][part_value]['rejected']) }}
                                    </td>
                                </tr>
                                <tr>
                                    <td>Rework</td>
                                    <td>
                                        {{ get_percentage(items['ocr_data'][part_value]['cutting'], items['ocr_data'][part_value]['pending']) }}
                                    </td>
                                </tr>
                            </tbody>    
                        </table>
                    </div>    
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import {ref} from 'vue'

let items = ref(null)
let item_name = cur_frm.doc.item
function load_data(data){
    items.value = data
}

function get_percentage(val1, val2){
    let x = val2/val1
    x = x * 100
    if(typeof(x) != "number"){
        x = 0
    }
    return x.toFixed(2)+"%"
}

function get_style(val){
    if(val < 0){
        return {"background":"#f57f87"};
    }
    else if(val > 0){
        return {"background":"#98ebae"}
    }
    return {"background":"#67b0b8"};
}

defineExpose({
    load_data,
})

</script>

<style scoped>
.bordered-table {
    width: 100%;
    border: 1px solid #ccc;
    border-collapse: collapse;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 3px 3px;
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}

.dark-border{
    border: 2px solid black;
}
</style>