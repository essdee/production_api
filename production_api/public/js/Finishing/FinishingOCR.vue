<template>
    <div>
        <div style="width:100%;" v-if="items && Object.keys(items).length > 0">
            <div v-for="part_value in Object.keys(items['ocr_data'])" style="width:100%;">
                <div style="display:flex;width:100%;gap:20px;">
                    <div style="width:75%;">
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
                                    <th :colspan="2">Cutting Qty ( A )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['cutting_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['cutting'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Sewing Received ( B )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['sewing_received'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['sewing_received'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference ( A - B )</th>
                                    <td v-for="size in items.primary_values" 
                                        :style="get_style(items['ocr_data'][part_value]['total'][size]['sewing_received'] - items['ocr_data'][part_value]['total'][size]['cutting_qty'])">
                                        {{ items['ocr_data'][part_value]['total'][size]['sewing_received'] - items['ocr_data'][part_value]['total'][size]['cutting_qty'] }}
                                    </td>
                                    <th :style="get_style(items['ocr_data'][part_value]['sewing_received'] - items['ocr_data'][part_value]['cutting'])">
                                        {{ items['ocr_data'][part_value]['sewing_received'] - items['ocr_data'][part_value]['cutting'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Sewing Received ( C )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['sewing_received'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['sewing_received'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Old Lot ( D1 )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['old_lot'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['old_lot'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Ironing Excess ( D2 )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['ironing_excess'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['ironing_excess'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Finishing Inward ( D3 )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['dc_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['dc_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference ( D3 - C )</th>
                                    <td v-for="size in items.primary_values" 
                                        :style="get_style(items['ocr_data'][part_value]['total'][size]['dc_qty'] - items['ocr_data'][part_value]['total'][size]['sewing_received'])">
                                        {{ items['ocr_data'][part_value]['total'][size]['dc_qty'] - items['ocr_data'][part_value]['total'][size]['sewing_received'] }}
                                    </td>
                                    <th :style="get_style(items['ocr_data'][part_value]['dc_qty'] - items['ocr_data'][part_value]['sewing_received'])">
                                        {{ items['ocr_data'][part_value]['dc_qty'] - items['ocr_data'][part_value]['sewing_received'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Total Inward ( D ) (D1 + D2 + D3)</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['total_inward'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['total_inward'] }}
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
                                    <th :colspan="2">Packed Box Qty(In Pieces) ( E )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['packed_box_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['packed_box_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference ( E - D )</th>
                                    <td v-for="size in items.primary_values" 
                                        :style="get_style(items['ocr_data'][part_value]['total'][size]['packed_box_qty'] - items['ocr_data'][part_value]['total'][size]['total_inward'])">
                                        {{ items['ocr_data'][part_value]['total'][size]['packed_box_qty'] - items['ocr_data'][part_value]['total'][size]['total_inward'] }}
                                    </td>
                                    <th :style="get_style(items['ocr_data'][part_value]['packed_box_qty'] - items['ocr_data'][part_value]['total_inward'])">
                                        {{ items['ocr_data'][part_value]['packed_box_qty'] - items['ocr_data'][part_value]['total_inward'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :rowspan="Object.keys(items['ocr_data'][part_value]['data']).length + 1"
                                    style="vertical-align: middle;">Rejection Pieces ( I )</th>
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
                                <tr style="background-color: darkgray;">
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
                                    style="vertical-align: middle;">Loose Piece ( J )</th>
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
                                <tr style="background-color: darkgray;">
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
                                    style="vertical-align: middle;">Loose Piece Set ( K )</th>
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
                                <tr style="background-color: darkgray;">
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
                                    style="vertical-align: middle;">Rework Pieces ( L )</th>
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
                                <tr style="background-color: darkgray;">
                                    <th :colspan="2">Total</th>
                                    <th v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['pending'] }}
                                    </th>
                                    <th>
                                        {{ items['ocr_data'][part_value]['pending'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference  ( I + J + K + L + E + (B-A) - A )</th>
                                    <th v-for="size in items.primary_values" :style="get_style(get_total_difference(part_value, size))">
                                        {{ get_total_difference(part_value, size) }}
                                    </th>
                                    <th :style="get_style(get_total(part_value))">
                                        {{ get_total(part_value) }}
                                    </th>
                                </tr>
                            </tbody>    
                        </table>
                    </div>
                    <div style="width:25%;">    
                        <table class="table table-sm table-sm-bordered bordered-table">
                            <thead class="dark-border">
                                <tr>
                                    <th>{{ part_value }}</th>
                                    <th></th>
                                    <th>Difference</th>
                                </tr>
                            </thead>
                            <tbody class="dark-border">    
                                <tr>
                                    <td>Cut to Dispatch</td>
                                    <td> 
                                        {{ get_percentage(get_cut_to_dispatch(part_value)) }}%
                                    </td>
                                    <td>{{ (100 - get_percentage(get_cut_to_dispatch(part_value))).toFixed(2) }}%</td>
                                </tr>
                                <tr>
                                    <td>Cut to Inward</td>
                                    <td>
                                        {{ get_percentage(get_cut_to_inward(part_value)) }}%
                                    </td>
                                    <td>{{ (100 - get_percentage(get_cut_to_inward(part_value))).toFixed(2) }}%</td>
                                </tr>
                                <tr>
                                    <td>Inward to Dispatch</td>
                                    <td>
                                        {{ get_percentage(get_inward_to_dispatch(part_value)) }}%
                                    </td>
                                    <td>{{ (100 - get_percentage(get_inward_to_dispatch(part_value))).toFixed(2) }}%</td>
                                </tr>
                                <tr>
                                    <td>Loose Piece</td>
                                    <td>
                                        {{ get_percentage(get_loose_piece(part_value)) }}%
                                    </td>
                                    <td></td>
                                </tr>
                                <tr>
                                    <td>Rejection</td>
                                    <td>
                                        {{ get_percentage(get_rejection(part_value)) }}%
                                    </td>
                                    <td></td>
                                </tr>
                                <tr>
                                    <td>Rework</td>
                                    <td>
                                        {{ get_percentage(get_rework(part_value)) }}%
                                    </td>
                                    <td></td>
                                </tr>
                                <tr>
                                    <td>Finishing Not Received</td>
                                    <td>
                                        {{ get_percentage(get_not_received(part_value), make_pos=true) }}%
                                    </td>
                                    <td></td>
                                </tr>
                                <tr>
                                    <td>OCR Complete</td>
                                    <td>{{ (get_ocr_value(part_value)).toFixed(2) }}%</td>
                                    <td>{{ (100 - get_ocr_value(part_value)).toFixed(2) }}%</td>
                                </tr>
                                <tr>
                                    <td>Unaccountable</td>
                                    <td>-{{ get_percentage(get_unaccountable(part_value), make_pos=true) }}%</td>
                                    <td></td>
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

function get_percentage(val_dict, make_pos=false){
    let val1 = val_dict['val1']
    let val2 = val_dict['val2']
    let x = val2/val1
    x = x * 100
    if (isNaN(x)) {  
        x = 0
    }
    if(make_pos && x < 0){
        x = x * -1
    }
    return parseFloat(x.toFixed(2))
}

function get_style(val){
    if(val < 0){
        return {"background":"#f57f87"};
    }
    else if(val > 0){
        return {"background":"#98ebae"}
    }
    return {"background":"#ebc96e"};
}

function get_total_difference(part_value, size){
    return items.value['ocr_data'][part_value]['total'][size]['pending'] +
        items.value['ocr_data'][part_value]['total'][size]['loose_piece_set'] +
        items.value['ocr_data'][part_value]['total'][size]['loose_piece'] +
        items.value['ocr_data'][part_value]['total'][size]['rejected'] +
        items.value['ocr_data'][part_value]['total'][size]['packed_box_qty'] +
        (items.value['ocr_data'][part_value]['total'][size]['sewing_received'] - 
        items.value['ocr_data'][part_value]['total'][size]['cutting_qty'] ) -
        items.value['ocr_data'][part_value]['total'][size]['cutting_qty']
}

function get_total(part_value){
    return items.value['ocr_data'][part_value]['pending'] +
        items.value['ocr_data'][part_value]['loose_piece_set'] +
        items.value['ocr_data'][part_value]['loose_piece'] +
        items.value['ocr_data'][part_value]['rejected'] +
        items.value['ocr_data'][part_value]['packed_box_qty'] +
        (items.value['ocr_data'][part_value]['sewing_received'] - 
        items.value['ocr_data'][part_value]['cutting']) -
        items.value['ocr_data'][part_value]['cutting']
}

function get_ocr_value(part_value){
    return get_percentage(get_cut_to_dispatch(part_value)) + get_percentage(get_loose_piece(part_value)) +
        get_percentage(get_rejection(part_value)) + get_percentage(get_rework(part_value)) +
        get_percentage(get_not_received(part_value), make_pos=true)
}

function get_cut_to_dispatch(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'] + 
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'],
        "val2": items.value['ocr_data'][part_value]['packed_box_qty'],
    }
}

function get_cut_to_inward(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'],
        "val2": items.value['ocr_data'][part_value]['sewing_received'],
    }
}

function get_inward_to_dispatch(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['sewing_received'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'], 
        "val2": items.value['ocr_data'][part_value]['packed_box_qty']
    }
}

function get_loose_piece(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'], 
        "val2": items.value['ocr_data'][part_value]['loose_piece'],
    }
}

function get_rejection(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'], 
        "val2": items.value['ocr_data'][part_value]['rejected'],
    }
}

function get_rework(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'], 
        "val2": items.value['ocr_data'][part_value]['pending']
    }
}

function get_not_received(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'],
        "val2": items.value['ocr_data'][part_value]['sewing_received'] - items.value['ocr_data'][part_value]['cutting']
    }
}

function get_unaccountable(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'],
        "val2": items.value['ocr_data'][part_value]['sewing_received'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'] -
                (items.value['ocr_data'][part_value]['packed_box_qty'] + 
                items.value['ocr_data'][part_value]['rejected'] + 
                items.value['ocr_data'][part_value]['loose_piece_set'] +
                items.value['ocr_data'][part_value]['loose_piece'] +
                items.value['ocr_data'][part_value]['pending'])
    }
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