<template>
	<div ref="root" class="frappe-control">
		<table class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Received Type</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
							<th>Comments</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
							</td>
							<td>
								{{j.received_type}}
							</td>
							<td v-for="attr in j.values" :key="attr">
								<div v-if="attr.received">
									{{ attr.received}}
									<span v-if="j.default_uom">{{" " + j.default_uom}}</span>
								</div>
								<div v-else class="text-center">---</div>
							</td>
							<td>{{ j.comments }}</td>
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
							<th>Received Type</th>
							<th>Quantity</th>
							<th>Comments</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
							</td>
							<td>{{j.received_type}}</td>
							<td>
								{{ j.values["default"].received}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
							</td>
							<td>{{ j.comments }}</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>
	</div>
</template>

<script setup>
import EventBus from "../../bus";

import { ref, onMounted, computed, watch } from "vue";
const root = ref(null);
let i = 0;
const items = ref([]);
let is_rework = cur_frm.doc.is_rework

function load_data(data) {
  	if (data) {
        items.value = data
	}
}

defineExpose({
	items,
	load_data,
});
</script>