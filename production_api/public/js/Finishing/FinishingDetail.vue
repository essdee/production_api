<template>
    <div>
        <table class="table table-sm table-sm-bordered bordered-table" v-if="items && Object.keys(items).length > 0">
            <thead class="dark-border">
                <tr>
                    <th style="width:20px;">S.No</th>
                    <th style="width:20px;">Colour</th>
                    <th style="width:20px;" v-if="items.is_set_item">{{ items['set_attr'] }}</th>
                    <th style="width:150px;">Type</th>
                    <th v-for="size in items.primary_values" :key="size">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <template  v-for="(colour, idx) in Object.keys(items['data']['data'])" :key="colour">
                    <tr>
                        <td :rowspan="6">{{ idx + 1 }}</td>
                        <td :rowspan="6">{{ colour.split("@")[0] }}</td>
                        <td :rowspan="6" v-if="items.is_set_item">{{ items['data']['data'][colour]['part'] }}</td>
                        <td>Cutting Qty</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['data'][colour]["values"][size]['cutting'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['data'][colour]['colour_total']['cutting'] ?? 0 }}</strong></td>
                    </tr>
                    <tr>
                        <td>{{ process }} Delivered</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['data'][colour]["values"][size]['delivered'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['data'][colour]['colour_total']['delivered'] ?? 0 }}</strong></td>
                    </tr>
                    <tr>
                        <td>Difference</td>
                        <td v-for="size in items.primary_values" :key="size" 
                            :style="get_style(items['data']['data'][colour]['values'][size]['cut_sew_diff'] ?? 0)">
                            {{
                                items['data']['data'][colour]['values'][size]['cut_sew_diff'] ?? 0
                            }}
                        </td>
                        <td :style="get_style(items['data']['data'][colour]['colour_total']['cut_sew_diff'] ?? 0)">
                            <strong>{{ items['data']['data'][colour]['colour_total']['cut_sew_diff'] ?? 0 }}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td>{{ process }} Delivered</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['data'][colour]["values"][size]['delivered'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['data'][colour]['colour_total']['delivered'] ?? 0 }}</strong></td>
                    </tr>
                    <tr>
                        <td>{{ process }} Received</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['data'][colour]["values"][size]['received'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['data'][colour]['colour_total']['received'] ?? 0 }}</strong></td>
                    </tr>
                    <tr>
                        <td>Difference</td>
                        <td v-for="size in items.primary_values" :key="size" 
                            :style="get_style(items['data']['data'][colour]['values'][size]['difference'] ?? 0)">
                            {{
                                items['data']['data'][colour]['values'][size]['difference'] ?? 0
                            }}
                        </td>
                        <td :style="get_style(items['data']['data'][colour]['colour_total']['difference'] ?? 0)">
                            <strong>{{ items['data']['data'][colour]['colour_total']['difference'] ?? 0 }}</strong>
                        </td>
                    </tr>
                </template>    
                <template  v-for="(part, idx) in Object.keys(items['data']['total'])" :key="part">
                    <tr style="background-color: bisque;">
                        <td :rowspan="6"></td>
                        <td :rowspan="6">Total</td>
                        <td :rowspan="6" v-if="items.is_set_item">{{ part }}</td>
                        <td>Cutting Qty</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['total'][part][size]['cutting'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['over_all'][part]['cutting'] }}</strong></td>
                    </tr>
                    <tr style="background-color: bisque;">
                        <td>{{ process }} Delivered</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['total'][part][size]['delivered'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['over_all'][part]['delivered'] }}</strong></td>
                    </tr>
                    <tr style="background-color: bisque;">
                        <td>Difference</td>
                        <td v-for="size in items.primary_values" :key="size" 
                            :style="get_style(items['data']['total'][part][size]['cut_sew_diff'] ?? 0)">
                            {{
                                items['data']['total'][part][size]['cut_sew_diff'] ?? 0
                            }}
                        </td>
                        <td :style="get_style(items['data']['over_all'][part]['cut_sew_diff'])">
                            {{ items['data']['over_all'][part]['cut_sew_diff'] }}
                        </td>
                    </tr>
                    <tr style="background-color: bisque;">
                        <td>{{ process }} Delivered</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['total'][part][size]['delivered'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['over_all'][part]['delivered'] }}</strong></td>
                    </tr>
                    <tr style="background-color: bisque;">
                        <td>{{ process }} Received</td>
                        <td v-for="size in items.primary_values" :key="size">
                            {{
                                items['data']['total'][part][size]['received'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ items['data']['over_all'][part]['received'] }}</strong></td>
                    </tr>
                    <tr style="background-color: bisque;">
                        <td>Difference</td>
                        <td v-for="size in items.primary_values" :key="size" 
                            :style="get_style(items['data']['total'][part][size]['difference'] ?? 0)">
                            {{
                                items['data']['total'][part][size]['difference'] ?? 0
                            }}
                        </td>
                        <td :style="get_style(items['data']['over_all'][part]['difference'] ?? 0)">
                            {{ items['data']['over_all'][part]['difference'] ?? 0 }}
                        </td>
                    </tr>
                </template>    
            </tbody>
        </table>
    </div>
</template>

<script setup>

import { ref } from 'vue';

let items = ref(null)
let process = cur_frm.doc.finishing_process

function load_data(data){
    items.value = data
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


defineExpose({
    load_data
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
    padding: 6px 8px;
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