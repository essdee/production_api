<template>
    <div class="item-detail frappe-control">
        <div class="d-fleex flex-row flex" v-if="d && d.length > 0">
            <div class="m-2 p-2 address-box text-center" v-for="item in d" :key="item.name">
                <h5>{{ item.name }}</h5>
                <p>{{ item.value }}</p>
            </div>
        </div>
    </div>
</template>

<script>
// Used in Item and Supplier to list all price and lead time
export default {
    name: 'item-detail',
    props: ['type', 'data'],
    data() {
        return {
            d: [
                {name: 'Item1', value: 20},
                {name: 'Item2', value: 30},
                {name: 'Item3', value: 40},
                {name: 'Item4', value: 50},
                {name: 'Item5', value: 60},
                {name: 'Item6', value: 70},
            ]
        };
    }
}
</script>