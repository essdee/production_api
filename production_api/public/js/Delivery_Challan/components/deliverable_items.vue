<template>
		<div>
			<div class="table-container">
				<table class="styled-table" v-if="items.length > 0">
					<thead>
						<tr>
							<th>S.No</th>
							<th>Item Variant</th>
							<th>Lot</th>
							<th>Pending Quantity</th>
							<th>Deliver Quantity</th>
							<th>Rate</th>
							<th>UOM</th>
							<th>Comments</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="item, index in deliverables_item" :key="item.id">
							<td>{{ index + 1 }}</td>
							<td>{{ item.item_variant }}</td>
							<td>{{ item.lot }}</td>
							<td> {{item.pending_quantity}} </td>
							<td v-if="docstatus == 0">
								<input type="number" v-model.number="item.qty" 
									class="editable-input" @click="make_dirty()"
									@input="check(item.qty)" min="0" step="0.001"
								/>
							</td>
							<td v-else> {{item.qty}} </td>
							<td>{{ item.rate }}</td>
							<td>{{ item.uom }}</td>
							<td v-if="docstatus === 0">
								<input type="text" v-model="item.comments" 
									class="editable-input" @click="make_dirty()"
								/>
							</td>
							<td v-else>{{ item.comments }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
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
function check(qty){
	if(qty < 0){
		frappe.msgprint("Only positive quantity is acceptable")
	}
}
defineExpose({deliverables_item,update_status})

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
	