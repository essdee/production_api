
<template>
    <div ref="root" class="table-container">
        <table class="table table-sm table-bordered" v-if="items.length > 0">
            <thead>
                <tr>
                    <th>S.No</th>
                    <th>Item Variant</th>
                    <th>Lot</th>
                    <th>Expected Delivery Date</th>
                    <th>Delivery Date</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="(item, index) in item_data" :key="item.id">
                    <td>{{ index + 1 }}</td>
                    <td>{{ item.item_variant }}</td>
                    <td>{{ item.lot }}</td>
                    <td>{{ item.delivery_date }}</td>
                    <td>
                        <div :class="'delivery-date-' + index"></div>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import { reactive, ref, onMounted, nextTick } from 'vue';

const props = defineProps(['items']);
const item_data = reactive([...props.items]);
const root = ref(null);
const sample_doc = ref({});

onMounted(() => {
    item_data.forEach((item, index) => {
        createFrappeDateField(index);
    });
});

function createFrappeDateField(index) {
    let el = root.value;
    $(el).find(".delivery-date-" + index).html("");

    let date_field = frappe.ui.form.make_control({
        parent: $(el).find(".delivery-date-" + index),
        df: {
            fieldtype: 'Date',
            fieldname: `new_delivery_date_${index}`,
            change: function() {
                item_data[index].new_delivery_date = this.get_value();
            }
        },
        doc: sample_doc.value,
        render_input: true
    });
    date_field.set_value(item_data[index].delivery_date)

    nextTick(() => {
        $(el).find(".control-label").remove();
    });
}

defineExpose({
    item_data,
})

</script>

<style scoped>
.table-container {
    margin: 20px;
}
.styled-table {
    width: 100%;
    border-collapse: collapse;
}
.styled-table th, .styled-table td {
    border: 1px solid #ddd;
    padding: 8px;
}
.styled-table th {
    background-color: #f2f2f2;
}
</style>
