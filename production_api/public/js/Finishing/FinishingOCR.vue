<template>
    <div>
        <div class="ocr-tab-nav">
            <button
                type="button"
                class="ocr-tab-button"
                :class="{ active: active_tab === 'ocr_details' }"
                @click="active_tab = 'ocr_details'"
            >
                OCR Details
            </button>
            <button
                type="button"
                class="ocr-tab-button"
                :class="{ active: active_tab === 'consumption_details' }"
                @click="active_tab = 'consumption_details'"
            >
                Consumption Details
            </button>
            <button
                type="button"
                class="ocr-tab-button"
                :class="{ active: active_tab === 'stock_balance' }"
                @click="active_tab = 'stock_balance'"
            >
                Stock balance
            </button>
        </div>
        <div style="width:100%;" v-if="items && Object.keys(items).length > 0" v-show="active_tab === 'ocr_details'">
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
                                    <th :colspan="2">Total Inward (D) (C + D1 + D2)</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['total_inward'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['total_inward'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Finishing Inward ( E )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['dc_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['dc_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Transferred ( F )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['transferred'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['transferred'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference ( (E + F) - D )</th>
                                    <td v-for="size in items.primary_values" 
                                        :style="get_style(
                                            items['ocr_data'][part_value]['total'][size]['transferred'] +
                                            items['ocr_data'][part_value]['total'][size]['dc_qty'] - 
                                            items['ocr_data'][part_value]['total'][size]['total_inward']
                                        )">
                                        {{ 
                                            items['ocr_data'][part_value]['total'][size]['transferred'] +
                                            items['ocr_data'][part_value]['total'][size]['dc_qty'] - 
                                            items['ocr_data'][part_value]['total'][size]['total_inward'] 
                                        }}
                                    </td>
                                    <th :style="get_style(
                                            items['ocr_data'][part_value]['transferred'] + 
                                            items['ocr_data'][part_value]['dc_qty'] - 
                                            items['ocr_data'][part_value]['total_inward']
                                        )">
                                        {{ items['ocr_data'][part_value]['dc_qty'] - items['ocr_data'][part_value]['total_inward'] }}
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
                                    <th :colspan="2">Packed Box Qty(In Pieces) ( G )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['packed_box_qty'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['packed_box_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference ( G - E )</th>
                                    <td v-for="size in items.primary_values" 
                                        :style="get_style(items['ocr_data'][part_value]['total'][size]['packed_box_qty'] - items['ocr_data'][part_value]['total'][size]['dc_qty'])">
                                        {{ items['ocr_data'][part_value]['total'][size]['packed_box_qty'] - items['ocr_data'][part_value]['total'][size]['dc_qty'] }}
                                    </td>
                                    <th :style="get_style(items['ocr_data'][part_value]['packed_box_qty'] - items['ocr_data'][part_value]['dc_qty'])">
                                        {{ items['ocr_data'][part_value]['packed_box_qty'] - items['ocr_data'][part_value]['dc_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Dispatched Box</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['dispatched_box'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['dispatched_box'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Dispatched Piece(In Pieces) ( H )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['dispatched_piece'] }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['dispatched_piece'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Difference ( H - G )</th>
                                    <td v-for="size in items.primary_values"
                                        :style="get_style(items['ocr_data'][part_value]['total'][size]['dispatched_piece'] - items['ocr_data'][part_value]['total'][size]['packed_box_qty'])">
                                        {{ items['ocr_data'][part_value]['total'][size]['dispatched_piece'] - items['ocr_data'][part_value]['total'][size]['packed_box_qty'] }}
                                    </td>
                                    <th :style="get_style(items['ocr_data'][part_value]['dispatched_piece'] - items['ocr_data'][part_value]['packed_box_qty'])">
                                        {{ items['ocr_data'][part_value]['dispatched_piece'] - items['ocr_data'][part_value]['packed_box_qty'] }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Order Qty ( O )</th>
                                    <td v-for="size in items.primary_values">
                                        {{ items['ocr_data'][part_value]['total'][size]['order_qty'] || 0 }}
                                    </td>
                                    <th>
                                        {{ items['ocr_data'][part_value]['order_qty'] || 0 }}
                                    </th>
                                </tr>
                                <tr>
                                    <th :colspan="2">Order to Dispatch Diff ( O - H )</th>
                                    <td v-for="size in items.primary_values"
                                        :style="get_style((items['ocr_data'][part_value]['total'][size]['order_qty'] || 0) - items['ocr_data'][part_value]['total'][size]['dispatched_piece'])">
                                        {{ (items['ocr_data'][part_value]['total'][size]['order_qty'] || 0) - items['ocr_data'][part_value]['total'][size]['dispatched_piece'] }}
                                    </td>
                                    <th :style="get_style((items['ocr_data'][part_value]['order_qty'] || 0) - items['ocr_data'][part_value]['dispatched_piece'])">
                                        {{ (items['ocr_data'][part_value]['order_qty'] || 0) - items['ocr_data'][part_value]['dispatched_piece'] }}
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
                                    <th :colspan="2">Unaccountable (( G + I + J + K + L ) - (B + D1 + D2 ))</th>
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
                                    <td>Order to Dispatch</td>
                                    <td>
                                        {{ get_percentage(get_order_to_dispatch(part_value)) }}%
                                    </td>
                                    <td>{{ (100 - get_percentage(get_order_to_dispatch(part_value))).toFixed(2) }}%</td>
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
        <div v-show="active_tab === 'consumption_details'" class="ocr-tab-panel">
            <div v-if="consumption_loading" class="consumption-loading">
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                <span>Loading consumption details...</span>
            </div>
            <div v-else-if="consumption_error" class="alert alert-danger">
                {{ consumption_error }}
            </div>
            <div v-else-if="!has_consumption_data" class="text-muted consumption-empty">
                Nothing to show
            </div>
            <div v-else>
                <div v-for="process in consumption_data.processes" :key="process.process" class="consumption-process">
                    <div class="consumption-process-title">{{ process.process }}</div>
                    <div v-for="(group, group_index) in process.groups" :key="process.process + '-' + group_index" class="table-responsive">
                        <table class="table table-sm table-sm-bordered bordered-table consumption-table">
                            <thead class="dark-border">
                                <tr>
                                    <th>Item</th>
                                    <th v-for="attr in group.attributes" :key="attr">{{ attr }}</th>
                                    <th>Received Type</th>
                                    <template v-if="group.primary_attribute">
                                        <th v-for="attr in group.primary_attribute_values" :key="attr">
                                            {{ attr }}
                                        </th>
                                    </template>
                                    <th v-else>Quantity</th>
                                    <th>Total</th>
                                </tr>
                            </thead>
                            <tbody class="dark-border">
                                <tr v-for="(item, item_index) in group.items" :key="item_index">
                                    <td>{{ item.item }}</td>
                                    <td v-for="attr in group.attributes" :key="attr">
                                        {{ item.attributes[attr] || "--" }}
                                    </td>
                                    <td>{{ item.received_type || "--" }}</td>
                                    <template v-if="group.primary_attribute">
                                        <td v-for="attr in group.primary_attribute_values" :key="attr" :title="get_sources_title(item, attr)">
                                            <span v-if="get_cell_quantity(item, attr)">{{ format_qty(get_cell_quantity(item, attr)) }}</span>
                                            <span v-else>--</span>
                                        </td>
                                    </template>
                                    <td v-else :title="get_sources_title(item, 'default')">
                                        <span v-if="get_cell_quantity(item, 'default')">{{ format_qty(get_cell_quantity(item, 'default')) }}</span>
                                        <span v-else>--</span>
                                    </td>
                                    <td>{{ format_qty(item.total_quantity) }}</td>
                                </tr>
                                <tr class="consumption-total-row">
                                    <th :colspan="2 + group.attributes.length">Total</th>
                                    <template v-if="group.primary_attribute">
                                        <th v-for="attr in group.primary_attribute_values" :key="attr">
                                            <span v-if="group.total_details[attr]">{{ format_qty(group.total_details[attr]) }}</span>
                                            <span v-else>--</span>
                                        </th>
                                    </template>
                                    <th v-else>
                                        <span v-if="group.total_details.default">{{ format_qty(group.total_details.default) }}</span>
                                        <span v-else>--</span>
                                    </th>
                                    <th>{{ format_qty(group.overall_total) }}</th>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        <div v-show="active_tab === 'stock_balance'" class="ocr-tab-panel">
            <div v-if="stock_balance_loading" class="consumption-loading">
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                <span>Loading stock balance...</span>
            </div>
            <div v-else-if="stock_balance_error" class="alert alert-danger">
                {{ stock_balance_error }}
            </div>
            <div v-else-if="!has_stock_balance_data" class="text-muted consumption-empty">
                Nothing to show
            </div>
            <div v-else>
                <div v-for="warehouse in stock_balance_data.warehouses" :key="warehouse.warehouse" class="consumption-process">
                    <div class="consumption-process-title">{{ get_warehouse_title(warehouse) }}</div>
                    <div v-for="(group, group_index) in warehouse.groups" :key="warehouse.warehouse + '-' + group_index" class="table-responsive">
                        <table class="table table-sm table-sm-bordered bordered-table consumption-table">
                            <thead class="dark-border">
                                <tr>
                                    <th>Item</th>
                                    <th v-for="attr in group.attributes" :key="attr">{{ attr }}</th>
                                    <th>Received Type</th>
                                    <th>UOM</th>
                                    <template v-if="group.primary_attribute">
                                        <th v-for="attr in group.primary_attribute_values" :key="attr">
                                            {{ attr }}
                                        </th>
                                    </template>
                                    <th v-else>Balance Qty</th>
                                    <th>Total</th>
                                </tr>
                            </thead>
                            <tbody class="dark-border">
                                <tr v-for="(item, item_index) in group.items" :key="item_index">
                                    <td>{{ item.item }}</td>
                                    <td v-for="attr in group.attributes" :key="attr">
                                        {{ item.attributes[attr] || "--" }}
                                    </td>
                                    <td>{{ item.received_type || "--" }}</td>
                                    <td>{{ item.stock_uom || "--" }}</td>
                                    <template v-if="group.primary_attribute">
                                        <td v-for="attr in group.primary_attribute_values" :key="attr">
                                            <span v-if="get_cell_quantity(item, attr)">{{ format_qty(get_cell_quantity(item, attr)) }}</span>
                                            <span v-else>--</span>
                                        </td>
                                    </template>
                                    <td v-else>
                                        <span v-if="get_cell_quantity(item, 'default')">{{ format_qty(get_cell_quantity(item, 'default')) }}</span>
                                        <span v-else>--</span>
                                    </td>
                                    <td>{{ format_qty(item.total_quantity) }}</td>
                                </tr>
                                <tr class="consumption-total-row">
                                    <th :colspan="3 + group.attributes.length">Total</th>
                                    <template v-if="group.primary_attribute">
                                        <th v-for="attr in group.primary_attribute_values" :key="attr">
                                            <span v-if="group.total_details[attr]">{{ format_qty(group.total_details[attr]) }}</span>
                                            <span v-else>--</span>
                                        </th>
                                    </template>
                                    <th v-else>
                                        <span v-if="group.total_details.default">{{ format_qty(group.total_details.default) }}</span>
                                        <span v-else>--</span>
                                    </th>
                                    <th>{{ format_qty(group.overall_total) }}</th>
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
import {computed, ref} from 'vue'

let items = ref(null)
let active_tab = ref("ocr_details")
let consumption_data = ref(null)
let consumption_loading = ref(false)
let consumption_error = ref("")
let stock_balance_data = ref(null)
let stock_balance_loading = ref(false)
let stock_balance_error = ref("")
let item_name = cur_frm.doc.item
function load_data(data){
    items.value = data
}

const has_consumption_data = computed(() => {
    return Boolean(
        consumption_data.value &&
        consumption_data.value.processes &&
        consumption_data.value.processes.some(process => {
            return process.groups && process.groups.some(group => group.items && group.items.length > 0)
        })
    )
})

const has_stock_balance_data = computed(() => {
    return Boolean(
        stock_balance_data.value &&
        stock_balance_data.value.warehouses &&
        stock_balance_data.value.warehouses.some(warehouse => {
            return warehouse.groups && warehouse.groups.some(group => group.items && group.items.length > 0)
        })
    )
})

function load_consumption_data(doc_name){
    if(!doc_name){
        return
    }
    consumption_loading.value = true
    consumption_error.value = ""
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan.finishing_plan.get_fp_consumption_details",
        args: {
            doc_name: doc_name,
        },
        callback: function(r) {
            consumption_data.value = r.message || {processes: []}
            consumption_loading.value = false
        },
        error: function() {
            consumption_error.value = "Unable to load consumption details."
            consumption_loading.value = false
        }
    })
}

function load_stock_balance_data(doc_name){
    if(!doc_name){
        return
    }
    stock_balance_loading.value = true
    stock_balance_error.value = ""
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan.finishing_plan.get_fp_stock_balance_details",
        args: {
            doc_name: doc_name,
        },
        callback: function(r) {
            stock_balance_data.value = r.message || {warehouses: []}
            stock_balance_loading.value = false
        },
        error: function() {
            stock_balance_error.value = "Unable to load stock balance."
            stock_balance_loading.value = false
        }
    })
}

function get_cell_quantity(item, attr){
    if(!item || !item.values || !item.values[attr]){
        return 0
    }
    return item.values[attr].quantity || 0
}

function get_warehouse_title(warehouse){
    if(!warehouse){
        return ""
    }
    if(warehouse.warehouse_name && warehouse.warehouse_name !== warehouse.warehouse){
        return warehouse.warehouse_name + " - " + warehouse.warehouse
    }
    return warehouse.warehouse || warehouse.warehouse_name || ""
}

function get_sources_title(item, attr){
    if(!item || !item.values || !item.values[attr] || !item.values[attr].sources){
        return ""
    }
    return item.values[attr].sources.map(source => source.source_name).filter(Boolean).join(", ")
}

function format_qty(value){
    let qty = Number(value || 0)
    if(Number.isInteger(qty)){
        return qty
    }
    return Number(qty.toFixed(3))
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
    return  (items.value['ocr_data'][part_value]['total'][size]['packed_box_qty'] + 
            items.value['ocr_data'][part_value]['total'][size]['rejected'] + 
            items.value['ocr_data'][part_value]['total'][size]['loose_piece_set'] +
            items.value['ocr_data'][part_value]['total'][size]['loose_piece'] +
            items.value['ocr_data'][part_value]['total'][size]['pending']) - 
            (items.value['ocr_data'][part_value]['total'][size]['sewing_received'] +
            items.value['ocr_data'][part_value]['total'][size]['old_lot'] + 
            items.value['ocr_data'][part_value]['total'][size]['ironing_excess'])
}

function get_total(part_value){
    return (items.value['ocr_data'][part_value]['packed_box_qty'] + 
            items.value['ocr_data'][part_value]['rejected'] + 
            items.value['ocr_data'][part_value]['loose_piece_set'] +
            items.value['ocr_data'][part_value]['loose_piece'] +
            items.value['ocr_data'][part_value]['pending']) -
            (items.value['ocr_data'][part_value]['sewing_received'] +
            items.value['ocr_data'][part_value]['old_lot'] + 
            items.value['ocr_data'][part_value]['ironing_excess'])
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
                items.value['ocr_data'][part_value]['ironing_excess'] - 
                items.value['ocr_data'][part_value]['transferred'],
        "val2": items.value['ocr_data'][part_value]['dispatched_piece']
    }
}

function get_cut_to_inward(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'],
        "val2": items.value['ocr_data'][part_value]['sewing_received'],
    }
}

function get_order_to_dispatch(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['order_qty'] || 0,
        "val2": items.value['ocr_data'][part_value]['dispatched_piece'],
    }
}

function get_inward_to_dispatch(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['sewing_received'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'] - 
                items.value['ocr_data'][part_value]['transferred'], 
        "val2": items.value['ocr_data'][part_value]['dispatched_piece']
    }
}

function get_loose_piece(part_value){
    return {
        "val1": items.value['ocr_data'][part_value]['cutting'] +
                items.value['ocr_data'][part_value]['old_lot'] + 
                items.value['ocr_data'][part_value]['ironing_excess'], 
        "val2": items.value['ocr_data'][part_value]['loose_piece'] +
                items.value['ocr_data'][part_value]['loose_piece_set'], 
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
                items.value['ocr_data'][part_value]['pending'] +
                items.value['ocr_data'][part_value]['transferred'] 
            )
    }
}

defineExpose({
    load_data,
    load_consumption_data,
    load_stock_balance_data,
})

</script>

<style scoped>
.ocr-tab-nav {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid #d1d8dd;
    margin-bottom: 12px;
}

.ocr-tab-button {
    appearance: none;
    background: transparent;
    border: 0;
    border-bottom: 2px solid transparent;
    color: #4c5a67;
    cursor: pointer;
    font-weight: 600;
    padding: 8px 12px;
}

.ocr-tab-button.active {
    border-bottom-color: #2490ef;
    color: #1f272e;
}

.ocr-tab-panel {
    min-height: 80px;
}

.consumption-loading {
    align-items: center;
    color: #4c5a67;
    display: flex;
    gap: 8px;
    min-height: 120px;
}

.consumption-empty {
    align-items: center;
    display: flex;
    min-height: 120px;
}

.consumption-process {
    margin-bottom: 18px;
}

.consumption-process-title {
    background: #f8f9fa;
    border: 1px solid #d1d8dd;
    border-bottom: 0;
    font-weight: 700;
    padding: 8px 10px;
}

.consumption-table {
    margin-bottom: 0;
}

.consumption-total-row th {
    background: #eef2f5;
}

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
