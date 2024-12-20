<template>
    <div>
        <div v-if="costing_list">
            <table class="table table-sm table-bordered">
                <thead>
                    <th>S.No</th>
                    <th>Avg Rate / Pcs</th>
                    <th>Total Qty</th>
                    <th>Profit % (Markdown)</th>
                    <th></th>
                </thead>
                <tbody>
                    <tr v-for="(c, i) in costing_list">
                        <td>{{ i+1 }}</td>
                        <td>{{ c.avg_rate_per_piece }}</td>
                        <td>{{ c.total_qty }}</td>
                        <td>{{ c.profit_percent_markdown }}</td>
                        <td>
                            <a :href="'/app/lotwise-item-profit/' + encodeURIComponent(c.name)" class="btn btn-default btn-xs">
                                Open
                            </a>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <h6 v-else>There is no costing for this Product</h6>
    </div>
</template>

<script setup>
import { ref } from 'vue';
const costing_list = ref(cur_frm.doc.__onload.costing_list);
</script>