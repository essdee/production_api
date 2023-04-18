<template>
    <div
      class="flex items-center justify-between">
      
      <Autocomplete
        :options="suppliersOptions"
        v-model="selectedSupplier"
        v-on:update:modelValue="onSelectSupplier"
        placeholder="Select a supplier"
        :loading="suppliers.loading"
        />

        <Autocomplete
        :disabled="!selectedSupplier && !purchaseOrders.fetched"
        :options="purchaseOrders.data"
        v-model="selectedPO"
        v-on:update:modelValue="onSelectPO"
        placeholder="Select a Purchase Order"
        :loading="purchaseOrders.loading"
        />
    </div>
</template>

<script setup>
import { Autocomplete } from 'frappe-ui';
import { suppliers, suppliersOptions } from "@/data/supplier";
</script>
<script>
import {ref, computed} from 'vue'
import { purchaseOrderForSupplier } from "@/data/purchase_order.js"

export default {
    name: "GRN",
    data() {
         return {
             showDialog: false,
        }
    },
    methods: {
        onSelectSupplier: function(event) {
            if(!selectedSupplier.value) return;
            purchaseOrders = purchaseOrderForSupplier(selectedSupplier.value.value)
            purchaseOrders.fetch()
            console.log(purchaseOrders)
        },
    }
}

let selectedSupplier = ref(null)
let selectedPO = ref(null)
let purchaseOrders = {}

</script>