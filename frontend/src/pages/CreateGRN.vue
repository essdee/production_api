<template>
    <div class="flex flex-col w-full rounded-md shadow-sm bg-white p-5 m-6 space-y-3">
        <span class="font-bold text-2xl mb-1">Goods Received Note</span>
        <div class="flex flex-row space-x-4">
            <div class="basis-1/2">
                <label> Supplier:</label>
                <Autocomplete
                :options="supplierOptions"
                v-model="selectedSupplier"
                v-on:update:modelValue="onSelectSupplier"
                placeholder="Select a supplier"
                :loading="suppliers.loading"
                />
            </div>
            <div class="basis-1/2">
                <Input inputClass="w-full" label="Against" type="select" :options="['Purchase Order']" />
            </div>
        </div>
        <div class="flex">
            <div class="basis-1/2 pr-2">
                <label>Purchase Order:</label>
                <Autocomplete
                :disabled="!selectedSupplier"
                :options="purchaseOrderOptions"
                v-on:update:modelValue="onSelectPurchaseOrder"
                v-model="selectedPO"
                placeholder="Select a Purchase Order"
                />
            </div>
        </div>
        <div class="flex flex-row space-x-4">
            <div class="basis-1/2">
                <label> Delivery Location:</label>
                <Autocomplete
                :options="deliveryOptions"
                v-model="deliveryLocation"
                placeholder="Select a delivery Location"
                :loading="deliveryLocations.loading"
                />
            </div>
            <div class="basis-1/2">
                <label>Delivery Date</label>
                <DatePicker 
                    v-model="deliveryDate"
                    inputClass="w-full"
                    :formatValue="(val) => val.split('-').reverse().join('-')"
                />
            </div>
        </div>
        <div>
            <div v-if="poItems">
                <label>Purchase Order Items</label>
                <table class="w-full">
                    <tr v-for="(i, item_index) in poItems" :key="item_index">
                        <td v-if="i.primary_attribute">
                            <!-- <table class="w-full border border-separate border-spacing-y-3 border-slate-500 table-auto" v-if="i.items && i.items.length > 0"> -->
                            <table class="table table-bordered" v-if="i.items && i.items.length > 0">
                                <thead >
                                    <tr>
                                        <th>S.No.</th>
                                        <th>Item</th>
                                        <th>Lot</th>
                                        <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                                        <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                                        <th>Comments</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                        <td>{{ item1_index + 1 }}</td>
                                        <td>{{ j.name }}</td>
                                        <td>{{ j.lot }}</td>
                                        <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                                        <td v-for="attr in j.values" :key="attr">
                                            <div v-if="attr.qty">
                                                {{ attr.qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom }}</span>
                                                <span v-if="attr.secondary_qty">
                                                     ({{ attr.secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                                </span>
                                                <Input type="number" v-model="attr.received" label="Qty"/>
                                                <Input v-if="attr.secondary_qty" type="number" v-model="attr.secondary_received" label="Secondary Qty"/>
                                            </div>
                                            <div v-else class="text-center">
                                                ---
                                            </div>
                                        </td>
                                        <td>{{ j.comments }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        <td v-else>
                            <table class="table table-bordered" v-if="i.items && i.items.length > 0">
                                <thead>
                                    <tr>
                                        <th>S.No.</th>
                                        <th>Item</th>
                                        <th>Lot</th>
                                        <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                                        <th>Total Quantity</th>
                                        <th>Received Quantity</th>
                                        <th>Comments</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                        <td>{{ item1_index + 1 }}</td>
                                        <td>{{ j.name }}</td>
                                        <td>{{ j.lot }}</td>
                                        <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                                        <td>
                                            {{ j.values['default'].qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                            <span v-if="j.values['default'].secondary_qty">
                                                <br>
                                                ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                            </span>
                                        </td>
                                        <td>
                                            <Input type="number" v-model="j.values['default'].received" />
                                            <Input v-if="j.values['default'].secondary_qty" type="number" v-model="j.values['default'].secondary_received" label="Secondary Qty"/>
                                        </td>
                                        <td>{{ j.comments }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup>
import { Autocomplete, DatePicker, Input } from 'frappe-ui';
import { supplierList } from "@/data/supplier";

import { ref, computed, watch } from 'vue'
import { purchaseOrdersForSupplier, purchaseOrderItems } from "@/data/purchase_order.js"

const suppliers = supplierList({});
const selectedSupplier = ref(null);
const purchaseOrderOptions = ref(null);
const selectedPO = ref(null);
const poItems = ref(null);
const getToday = () => {
    // get today's date in yyyy-mm-dd format using DateFormatter
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, '0');
    const mm = String(today.getMonth() + 1).padStart(2, '0'); //January is 0!
    const yyyy = today.getFullYear();
    return yyyy + '-' + mm + '-' + dd;
};
const deliveryDate = ref(getToday());
const deliveryLocation = ref(null);
const deliveryLocations = supplierList({});

const onSelectSupplier = async function (event) {
    selectedPO.value = null;
    poItems.value = null;
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

const deliveryOptions = computed(() => {
    if (deliveryLocations.list.loading) return {};
    return deliveryLocations.data.map(supplier => {
        return {
            label: supplier.supplier_name,
            value: supplier.name
        }
    })
})
</script>