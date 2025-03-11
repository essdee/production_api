<template>
    <div ref="root">
        <div v-if="show_title">
            <h4>Summary</h4>
        </div>
        <table class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <table class="table table-sm table-bordered" v-if="i.items && i.items.length">
                    <thead>
                        <tr>
                            <th>S.No.</th>
                            <th>{{ i.pack_attr }}</th>
                            <th v-if="i.is_set_item">{{ i.set_attr }}</th>
                            <th>Details</th>
                            <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="(j, item1_index) in i.items" :key="item1_index">
                            <tr>
                                <td :rowspan="is_manual ? 2 : 3">{{ item1_index + 1 }}</td>
                                <td :rowspan="is_manual ? 2 : 3">
                                    {{ j.attributes[i.pack_attr] }}
                                    <span v-if="j.attributes[i.pack_attr] && i.is_set_item">
                                        ({{ j.item_keys['major_colour'] }})
                                    </span>
                                </td>
                                <td v-if="i.is_set_item" :rowspan="is_manual ? 2 : 3">
                                    {{ j.attributes[i.set_attr] }}
                                </td>
                                <td>Planned</td>
                                <td v-for="attr in Object.keys(j.values)" :key="attr">
                                    <div v-if="j.values[attr]['qty'] > 0">{{ j.values[attr]['qty'] }}</div>
                                    <div v-else>--</div>
                                </td>
                            </tr>
                            <tr v-if="!is_manual">
                                <td>Delivered</td>
                                <td v-for="attr in Object.keys(j.values)" :key="attr">
                                    <div v-if="j.values[attr]['delivered'] > 0">{{ j.values[attr]['delivered'] }}</div>
                                    <div v-else>--</div>
                                </td>
                            </tr>
                            <tr>
                                <td>Received</td>
                                <td v-for="attr in Object.keys(j.values)" :key="attr">
                                    <div v-if="j.values[attr]['received'] > 0">{{ j.values[attr]['received'] }}</div>
                                    <div v-else>--</div>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </tr>
        </table>

        <h3>Additional Deliverables</h3>
        <table class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in deliverables_item" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0  && check_primary_table(i.items)">
						<tr>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <template v-if="check_primary_row(j.values)">
                                <td>{{ j.name }}</td>
                                <td>{{ j.lot }}</td>
                                <td v-for="attr in i.attributes" :key="attr"> 
                                    {{ j.attributes[attr] }} 
                                    <span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
                                    <span v-else-if="attr == 'Colour' && !j.is_set_item && j.attributes[attr] != j.item_keys['major_colour'] && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
                                </td>
                                <td v-for="attr in j.values" :key="attr">
                                    <div v-if='attr.pending_qty < 0'>
                                        {{ attr.pending_qty * -1}}
                                        <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                                    </div>
                                    <div v-else> -- </div>
                                </td>
                            </template>    
						</tr>
					</table>
				</td>
				<td v-else>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0 && check_non_primary_table(i.items)">
						<tr>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Quantity</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <template v-if='j.values["default"].pending_qty < 0'>
                                <td>{{ j.name }}</td>
                                <td>{{ j.lot }}</td>
                                <td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
                                <td>
                                    <div v-if='j.values["default"].pending_qty < 0'>
                                        {{ j.values["default"].pending_qty * -1 }}
                                        <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                                    </div>
                                    <div v-else> -- </div>
                                </td>
                            </template>
    					</tr>
					</table>
				</td>
			</tr>
		</table>
    </div>
</template>

<script setup>
import { ref } from 'vue';

let is_manual = cur_frm.doc.is_manual_entry;
let items = ref([]);
let show_title = ref(false);
let deliverables_item = ref([])

function load_data(item, delivered_items) {
    items.value = item;
    if (item.length > 0) {
        show_title.value = true;
    }
    deliverables_item.value = delivered_items
}

function check_primary_table(primary_items){
    for (let i = 0; i < primary_items.length; i++) {
        for (let key of Object.keys(primary_items[i].values)) {
            if (primary_items[i].values[key]['pending_qty'] < 0) {
                return true;
            }
        }
    }
    return false;
}

function check_primary_row(primary_row){
    for (let key of Object.keys(primary_row)) {
        if (primary_row[key]['pending_qty'] < 0) {
            return true;
        }
    }
    return false
}

function check_non_primary_table(non_prime_items){
    for (let i = 0; i < non_prime_items.length; i++) {
        if (non_prime_items[i].values["default"]['pending_qty'] < 0) {
            return true;
        }
    }
    return false;
}

defineExpose({
    load_data,
});
</script>

<style scoped>
.input-field {
    margin-bottom: -5;
}
</style>
