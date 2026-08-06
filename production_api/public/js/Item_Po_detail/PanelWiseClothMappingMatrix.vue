<template>
	<div v-if="matrix" ref="matrixRoot" class="pwm-card">
		<div class="pwm-head">
			<h4>Cloth Mapping Matrix</h4>
			<span>{{ completeCount }} / {{ totalCount }} complete</span>
		</div>

		<div v-if="matrix.panels.length > 1 || currentPanel?.panel_value" class="pwm-tabs">
			<button
				v-for="panel in matrix.panels"
				:key="panel.group_id"
				type="button"
				class="pwm-tab"
				:class="{ active: panel.group_id === activePanel }"
				@click="activePanel = panel.group_id"
			>
				{{ panel.panel_value || "All" }}
			</button>
		</div>

		<div v-if="currentPanel" class="pwm-scroll">
			<table class="pwm-table">
				<thead>
					<tr>
						<th class="pwm-row-label">{{ rowHeading }}</th>
						<th v-for="packing in currentPanel.packing_values" :key="packing">
							<span>{{ packing === singleValueKey ? "Cloth" : packing }}</span>
							<select
								v-if="!locked"
								class="form-control input-sm pwm-fill"
								value=""
								@change="fillColumn(packing, $event)"
							>
								<option value="">Fill column</option>
								<option v-for="cloth in matrix.cloth_options" :key="cloth" :value="cloth">
									{{ cloth }}
								</option>
							</select>
						</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, rowIndex) in currentPanel.rows" :key="rowKey(row)">
						<th class="pwm-row-label">{{ rowLabel(row) }}</th>
						<td
							v-for="(packing, packingIndex) in currentPanel.packing_values"
							:key="packing"
						>
							<select
								v-if="!locked"
								v-model="cellFor(row, packing).cloth"
								class="form-control input-sm pwm-input"
								:data-pwm-row="rowIndex"
								:data-pwm-column="packingIndex"
								@change="markDirty"
								@keydown="handleVerticalKeydown($event, rowIndex, packingIndex)"
							>
								<option value="">Select Cloth</option>
								<option v-for="cloth in matrix.cloth_options" :key="cloth" :value="cloth">
									{{ cloth }}
								</option>
							</select>
							<span v-else>{{ cellFor(row, packing).cloth || "—" }}</span>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const singleValueKey = "__single__";
const matrix = ref(null);
const matrixRoot = ref(null);
const activePanel = ref("");
const locked = ref(false);

const currentPanel = computed(() =>
	(matrix.value?.panels || []).find((panel) => panel.group_id === activePanel.value)
);
const rowHeading = computed(() =>
	(matrix.value?.other_attributes || []).join(" / ") || "Mapping"
);
const totalCount = computed(() =>
	(matrix.value?.panels || []).reduce(
		(total, panel) => total + panel.rows.length * panel.packing_values.length,
		0
	)
);
const completeCount = computed(() =>
	(matrix.value?.panels || []).reduce(
		(total, panel) =>
			total +
			panel.rows.reduce(
				(rowTotal, row) =>
					rowTotal +
					panel.packing_values.filter((packing) => cellFor(row, packing).cloth).length,
				0
			),
		0
	)
);

function load_data(payload, isLocked = false) {
	matrix.value = payload?.matrix || null;
	locked.value = Boolean(isLocked);
	activePanel.value = matrix.value?.panels?.[0]?.group_id || "";
}

function cellFor(row, packing) {
	row.values ||= {};
	row.values[packing] ||= { cloth: null };
	return row.values[packing];
}

function rowKey(row) {
	return (matrix.value?.other_attributes || [])
		.map((attribute) => row.attribute_values?.[attribute] || "")
		.join("\u001f") || "single";
}

function rowLabel(row) {
	return (matrix.value?.other_attributes || [])
		.map((attribute) => row.attribute_values?.[attribute] || "—")
		.join(" / ") || "Cloth";
}

function markDirty() {
	if (typeof cur_frm !== "undefined") cur_frm.dirty();
}

function fillColumn(packing, event) {
	const cloth = event.target.value;
	if (!cloth || !currentPanel.value) return;
	currentPanel.value.rows.forEach((row) => {
		cellFor(row, packing).cloth = cloth;
	});
	event.target.value = "";
	markDirty();
}

function handleVerticalKeydown(event, rowIndex, packingIndex) {
	if (event.key !== "ArrowDown" || !(event.ctrlKey || event.shiftKey)) return;
	event.preventDefault();
	const target = matrixRoot.value?.querySelector(
		`[data-pwm-row="${Number(rowIndex) + 1}"][data-pwm-column="${packingIndex}"]`
	);
	target?.focus();
}

function get_data() {
	return matrix.value ? JSON.parse(JSON.stringify(matrix.value)) : null;
}

defineExpose({ load_data, get_data });
</script>

<style scoped>
.pwm-card {
	margin-top: 12px;
	border: 1px solid var(--border-color, #dfe3e8);
	border-radius: 12px;
	background: var(--card-bg, #fff);
	overflow: hidden;
}
.pwm-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 13px 16px;
	border-bottom: 1px solid var(--border-color, #e5e7eb);
	background: var(--subtle-fg, #f8fafc);
}
.pwm-head h4 {
	margin: 0;
	font-size: 14px;
}
.pwm-head span {
	color: var(--text-muted, #64748b);
	font-size: 11px;
}
.pwm-tabs {
	display: flex;
	gap: 6px;
	padding: 10px 14px;
	overflow-x: auto;
	border-bottom: 1px solid var(--border-color, #e5e7eb);
}
.pwm-tab {
	padding: 6px 10px;
	border: 1px solid transparent;
	border-radius: 7px;
	background: transparent;
	color: var(--text-muted, #64748b);
	font-size: 11px;
	font-weight: 600;
	white-space: nowrap;
}
.pwm-tab.active {
	border-color: #bfe2dc;
	background: #eef9f7;
	color: #0f766e;
}
.pwm-scroll {
	padding: 12px 14px 14px;
	overflow-x: auto;
}
.pwm-table {
	width: 100%;
	min-width: 560px;
	border-collapse: separate;
	border-spacing: 0;
	border: 1px solid var(--border-color, #e5e7eb);
	border-radius: 9px;
	overflow: hidden;
}
.pwm-table th,
.pwm-table td {
	min-width: 140px;
	padding: 7px;
	border-right: 1px solid var(--border-color, #e5e7eb);
	border-bottom: 1px solid var(--border-color, #e5e7eb);
	text-align: left;
}
.pwm-table tr:last-child td,
.pwm-table tr:last-child th {
	border-bottom: 0;
}
.pwm-table th:last-child,
.pwm-table td:last-child {
	border-right: 0;
}
.pwm-table thead th {
	background: var(--subtle-fg, #f8fafc);
	font-size: 11px;
}
.pwm-row-label {
	position: sticky;
	left: 0;
	z-index: 1;
	width: 150px;
	min-width: 150px !important;
	background: var(--card-bg, #fff);
}
thead .pwm-row-label {
	z-index: 2;
	background: var(--subtle-fg, #f8fafc);
}
.pwm-fill {
	margin-top: 5px;
	font-weight: 400;
}
.pwm-input,
.pwm-fill {
	height: 31px;
	font-size: 11px;
}
</style>
