<template>
    <div
      class="flex items-center justify-between">
      
        <Autocomplete
        :options="supplierOptions"
        v-model="selectedSupplier"
        v-on:update:modelValue="onSelectSupplier"
        placeholder="Select a supplier"
        :loading="suppliers.loading"
        />
        <Autocomplete
        :disabled="!selectedSupplier"
        :options="purchaseOrderOptions"
        v-on:update:modelValue="onSelectPurchaseOrder"
        v-model="selectedPO"
        placeholder="Select a Purchase Order"
        />

        <div v-if="poItems">
            <!-- <li v-for="item in poItems">
                {{ item }}
            </li> -->
            <table v-for="item in poItems" class="table table-sm table-bordered">
                <tr>
                    <th>S.No.</th>
                    <th>Item</th>
                    <th>Lot</th>
                    <th v-for="attr in item.attributes" :key="attr">{{ attr }}</th>
                    <th>Quantity</th>
                    <th>Rate</th>
                    <th>Delivery Location</th>
                    <th>Delivery Date</th>
                    <th>Comments</th>
                </tr>
                <tr v-for="(j, item1_index) in item.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in item.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td>
                                {{ j.values['default'].qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="j.values['default'].secondary_qty">
                                    <br>
                                    ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <td>{{ j.values['default'].rate }}</td>
                            <td>{{ j.delivery_location }}</td>
                            <td>{{ j.delivery_date }}</td>
                            <td>{{ j.comments }}</td>
                        </tr>
            </table>

        </div>
    </div>
</template>

<script setup>
import { Autocomplete } from 'frappe-ui';
import { suppliers } from "@/data/supplier";

import { ref, computed, watch } from 'vue'
import { purchaseOrdersForSupplier, purchaseOrderItems } from "@/data/purchase_order.js"

const selectedSupplier = ref(null);
const purchaseOrderOptions = ref(null);
const selectedPO = ref(null);
const poItems = ref(null);

const onSelectSupplier = async function (event) {
    if(!selectedSupplier.value) return;
    let pos = await purchaseOrdersForSupplier(selectedSupplier.value.value).fetch();
    purchaseOrderOptions.value = pos.map(po => { return { label: po.name, value: po.name }});
}

const onSelectPurchaseOrder = async function (event) {
    if(!selectedPO) return;
    let items = await purchaseOrderItems(event.value).fetch();
    poItems.value = items
}

const supplierOptions = computed(() => {
    if (suppliers.list.loading) return {};
    return suppliers.data.map(supplier => {
        return {
            label: supplier.supplier_name,
            value: supplier.name
        }
    })
})
 
</script>