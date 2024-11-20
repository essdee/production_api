<template>
	<table v-if="docstatus !== 0" class="table table-sm table-bordered">
		<tr v-for="(i, item_index) in items" :key="item_index">
			<td v-if="i.primary_attribute">
				<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
					<tr>
						<th>S.No.</th>
						<th>Item</th>
						<th>Lot</th>
						<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
						<th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
					</tr>
					<tr v-for="(j, item1_index) in i.items" :key="item1_index">
						<td>{{ item1_index + 1 }}</td>
						<td>{{ j.name }}</td>
						<td>{{ j.lot }}</td>
						<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
						<td v-for="attr in j.values" :key="attr">
							<div v-if='attr.delivered_quantity > 0'>
								{{ attr.delivered_quantity}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
							</div>
							<div v-else> -- </div>
						</td>
					</tr>
				</table>
			</td>
			<td v-else>
				<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
					<tr>
						<th>S.No.</th>
						<th>Item</th>
						<th>Lot</th>
						<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
						<th>Delivered Quantity</th>
					</tr>
					<tr v-for="(j, item1_index) in i.items" :key="item1_index">
						<td>{{ item1_index + 1 }}</td>
						<td>{{ j.name }}</td>
						<td>{{ j.lot }}</td>
						<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
						<td>
							<div v-if='j.values["default"].delivered_quantity > 0'>
								{{ j.values["default"].delivered_quantity}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
							</div>
							<div v-else> -- </div>
						</td>
					</tr>
				</table>
			</td>
		</tr>
	</table>
	<table v-else class="table table-sm table-bordered">
		<tr v-for="(i, item_index) in items" :key="item_index">
			<td v-if="i.primary_attribute">
				<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
					<tr>
						<th>S.No.</th>
						<th>Item</th>
						<th>Lot</th>
						<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
						<th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
					</tr>
					<tr v-for="(j, item1_index) in i.items" :key="item1_index">
						<td>{{ item1_index + 1 }}</td>
						<td>{{ j.name }}</td>
						<td>{{ j.lot }}</td>
						<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
						<td v-for="attr in j.values" :key="attr">
							{{ attr.qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
							<form>
								<input class="form-control" type="number"
									v-model.number="attr.delivered_quantity" min="0"
									step="0.001" @blur="make_dirty()"/>
							</form>
						</td>
					</tr>
				</table>
			</td>
			<td v-else>
				<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
					<tr>
						<th>S.No.</th>
						<th>Item</th>
						<th>Lot</th>
						<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
						<th>Pending Quantity</th>
					</tr>
					<tr v-for="(j, item1_index) in i.items" :key="item1_index">
						<td>{{ item1_index + 1 }}</td>
						<td>{{ j.name }}</td>
						<td>{{ j.lot }}</td>
						<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
						<td>
							{{ j.values["default"].qty}}
							<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
							<form>
								<input class="form-control" type="number"
									v-model.number="j.values['default']['delivered_quantity']"
									min="0" step="0.001" @blur="make_dirty()"/>
							</form>
						</td>
					</tr>
				</table>
			</td>
		</tr>
	</table>
</template>
	
<script setup>
import { reactive, ref } from 'vue';

const props = defineProps(['items']);
const docstatus = ref(cur_frm.doc.docstatus);
const deliverables_item = reactive([...props.items]);

function update_status() {
	docstatus.value = cur_frm.doc.docstatus;
}

function make_dirty(){
	cur_frm.dirty();
}

defineExpose({
	deliverables_item,
	update_status,
})

</script>
<style scoped>
.table-container {
	padding: 16px;
}
.styled-table {
	width: 100%;
	border-collapse: collapse;
	border: 1px solid #ccc;
}
.styled-table th,
.styled-table td {
	padding: 8px;
	border: 1px solid #ccc;
}
.styled-table thead tr {
	background-color: #696969;
	color: #fff;
}
.styled-table tbody tr:hover {
	background-color: #f5f5f5;
}
.editable-input {
		width: 100%;
		padding: 4px;
		border: 1px solid #ccc;
		border-radius: 4px;
		box-sizing: border-box;
}
</style>
	