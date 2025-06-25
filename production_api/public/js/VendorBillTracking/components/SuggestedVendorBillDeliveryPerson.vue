<template>
    <div ref="root">
        <div v-if="supplier" class="mb-3">
            <div class="input-group">
                <input type="text" class="form-control me-1" placeholder="Search delivery person..."
                    v-model="searchQuery" />
            </div>
        </div>

        <transition name="fade" mode="out-in">
            <div v-if="suggested_delivery_persons.length > 0" key="list" class="card shadow-sm border mb-4">
                <div class="card-header bg-light font-weight-bold">
                    Delivery Persons
                </div>
                <div class="card-body p-3">
                    <transition-group name="list-fade" tag="div" class="d-flex flex-column gap-3">
                        <div v-for="i in suggested_delivery_persons" :key="i.delivery_person + i.delivery_mob_no"
                            class="delivery-person-item border-bottom pb-3 d-flex justify-content-between align-items-center">
                            <div>
                                <div><strong>Name:</strong> {{ i.delivery_person }}</div>
                                <div class="text-muted"><small>Mobile:</small> {{ i.delivery_mob_no }}</div>
                            </div>
                            <div>
                                <button @click="setCurrFrmDeliveryPerson(i.delivery_mob_no)"
                                    class="btn btn-sm btn-outline-primary apply-btn">
                                    Apply
                                </button>
                            </div>
                        </div>
                    </transition-group>
                </div>
            </div>
            <div v-else-if="supplier && searchQuery" key="no-results" class="card shadow-sm border mb-4">
                <div class="card-header bg-light font-weight-bold">
                    Delivery Persons
                </div>
                <div class="card-body p-3 text-muted">
                    No delivery persons found for "{{ searchQuery }}".
                </div>
            </div>
            <div v-else-if="supplier" key="no-initial-results" class="card shadow-sm border mb-4">
                <div class="card-header bg-light font-weight-bold">
                    Delivery Persons
                </div>
                <div class="card-body p-3 text-muted">
                    Start typing to search for delivery persons or create a new one.
                </div>
            </div>
        </transition>

        <div v-if="supplier" class="text-end mt-2">
            <button class="btn btn-sm btn-secondary create-new-btn" @click="createNewDeliveryPerson">
                <i class="fa fa-plus me-1"></i> Create New Delivery Person
            </button>
        </div>
    </div>
</template>

<script setup>
import { ref, defineExpose } from 'vue';
import { watchDebounced } from '@vueuse/core';


const suggested_delivery_persons = ref([]);
const supplier = ref(null);
const searchQuery = ref('');

async function fetch_suggested_delivery_persons(query = '') {
    frappe.call({
        method: "production_api.production_api.doctype.vendor_bill_delivery_person.vendor_bill_delivery_person.get_last_ten_delivery_persons",
        args: {
            supplier: supplier.value,
            search: query
        },
        callback: (r) => {
            suggested_delivery_persons.value = r.message || [];
        }
    });
}

function setCurrFrmDeliveryPerson(mob) {
    cur_frm.set_value('delivery_mob_no', mob);
}

function createNewDeliveryPerson() {
    frappe.ui.form.make_quick_entry('Vendor Bill Delivery Person', {
        default_values: {
            supplier: supplier.value
        },
        callback: (d) => {
            cur_frm.set_value('delivery_mob_no', d.delivery_mob_no);
            fetch_suggested_delivery_persons();
        }
    });
}

function update_for_new_supplier(_supplier) {
    supplier.value = _supplier;
    fetch_suggested_delivery_persons();
}

watchDebounced(searchQuery, () => {
    onSearch()
}, {
    debounce: 300
})

function onSearch() {
    fetch_suggested_delivery_persons(searchQuery.value);
}

defineExpose({ update_for_new_supplier });
</script>

<style scoped>
.card-header {
    font-size: 1rem;
    font-weight: 600;
}

/* Transitions for overall card visibility */
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
    transform: translateY(10px);
}

/* Transitions for list items */
.list-fade-enter-active,
.list-fade-leave-active {
    transition: all 0.25s cubic-bezier(0.25, 1, 0.5, 1);
}

.list-fade-enter-from {
    opacity: 0;
    transform: translateY(12px);
}

.list-fade-leave-to {
    opacity: 0;
    transform: translateY(-12px);
    position: absolute;
    /* Ensures elements don't collapse during exit transition */
}

.list-fade-move {
    transition: transform 0.25s cubic-bezier(0.25, 1, 0.5, 1);
}

/* Custom Styles for better feel */
.input-group .form-control,
.input-group .btn {
    border-radius: 0.375rem;
    /* Bootstrap's default */
}

.input-group .form-control.me-1 {
    margin-right: 0.5rem !important;
    /* Adjust margin for better spacing */
}

.delivery-person-item:last-child {
    border-bottom: none !important;
    /* Remove border from last item */
    padding-bottom: 0 !important;
    /* Remove padding from last item */
}

.delivery-person-item {
    transition: background-color 0.2s ease-in-out;
}

/* Subtle hover effect for the list item */
.delivery-person-item:hover {
    background-color: #f8f9fa;
    /* Light grey background on hover */
}

.apply-btn {
    transition: all 0.2s ease-in-out;
}

.apply-btn:hover {
    transform: translateY(-1px);
    /* Slight lift on hover */
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    /* Subtle shadow */
}

.create-new-btn {
    transition: all 0.2s ease-in-out;
}

.create-new-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
</style>