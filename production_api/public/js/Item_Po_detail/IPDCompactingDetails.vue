<template>
	<div class="ipd-compacting-card">
		<div class="ipd-compacting-head">
			<div>
				<h4>Compacting Details</h4>
			</div>
			<div class="ipd-compacting-progress">
				{{ completedCount }} / {{ rows.length }} complete
			</div>
		</div>

		<div v-if="!rows.length" class="ipd-compacting-empty">
			No compacting combinations are available. Save the panel-wise consumption
			and Cloth Mapping first.
		</div>

		<div v-else class="ipd-compacting-groups">
			<section
				v-for="group in clothGroups"
				:key="group.cloth_item"
				class="ipd-compacting-group"
				:class="{ 'is-compact': group.dias.length === 1 }"
			>
				<div class="ipd-compacting-group-head">
					<div class="ipd-compacting-group-title">
						<h5>{{ group.cloth_item }}</h5>
						<span>{{ group.completedCount }} / {{ group.totalCount }} complete</span>
					</div>
					<div
						v-if="canWrite && group.dias.length > 1"
						class="ipd-compacting-copy-tools"
					>
						<span>Copy colour:</span>
						<div
							v-colour-template-link="{ group, disabled: false }"
							class="ipd-compacting-link ipd-compacting-copy-colour-link"
						></div>
						<button
							type="button"
							class="btn btn-default btn-sm"
							:disabled="false"
							@click="copyColourToBlanks(group)"
						>
							Copy to blanks
						</button>
					</div>
				</div>
				<div class="table-responsive ipd-compacting-matrix-wrap">
					<table class="table table-bordered ipd-compacting-table">
						<thead>
							<tr>
								<th class="ipd-compacting-colour-column">
									{{ packingAttribute || "Packing Attribute" }}
								</th>
								<th
									v-for="dia in group.dias"
									:key="dia"
									class="ipd-compacting-dia-column"
								>
									<span>{{ dia }}</span>
									<div
										v-column-fill-dia-link="{
											group,
											inputDia: dia,
											disabled: !canWrite,
										}"
										class="ipd-compacting-link ipd-compacting-column-fill"
									></div>
								</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="colourRow in group.colourRows"
								:key="colourRow.packing_attribute_value"
							>
								<th class="ipd-compacting-colour-column">
									{{ colourRow.packing_attribute_value }}
								</th>
								<td
									v-for="(cell, index) in colourRow.cells"
									:key="group.dias[index]"
									class="ipd-compacting-cell"
								>
									<div
										v-if="cell"
										v-compacting-dia-link="{
											cell,
											disabled: !canWrite,
										}"
										class="ipd-compacting-link"
									></div>
									<span v-else class="text-muted">—</span>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const itemProductionDetail = ref("");
const packingAttribute = ref("");
const rows = ref([]);
const modified = ref(null);
const canWrite = ref(false);
const templateColours = ref({});
let linkControlSequence = 0;

const completedCount = computed(
	() => rows.value.filter((row) => Boolean(row.compacting_dia)).length
);

function compareValues(left, right) {
	return String(left).localeCompare(String(right), undefined, {
		numeric: true,
		sensitivity: "base",
	});
}

const clothGroups = computed(() => {
	const groups = new Map();
	rows.value.forEach((row) => {
		if (!groups.has(row.cloth_item)) {
			groups.set(row.cloth_item, {
				cloth_item: row.cloth_item,
				dias: new Set(),
				packingValues: new Set(),
				cells: new Map(),
			});
		}
		const group = groups.get(row.cloth_item);
		group.dias.add(row.input_dia);
		group.packingValues.add(row.packing_attribute_value);
		group.cells.set(
			[row.packing_attribute_value, row.input_dia].join("\u0000"),
			row
		);
	});

	return [...groups.values()]
		.sort((left, right) => compareValues(left.cloth_item, right.cloth_item))
		.map((group) => {
			const dias = [...group.dias].sort(compareValues);
			const packingValues = [...group.packingValues].sort(compareValues);
			const groupRows = [...group.cells.values()];
			return {
				cloth_item: group.cloth_item,
				dias,
				colourRows: packingValues.map((packingValue) => ({
					packing_attribute_value: packingValue,
					cells: dias.map((dia) =>
						group.cells.get([packingValue, dia].join("\u0000")) || null
					),
				})),
				completedCount: groupRows.filter((row) => Boolean(row.compacting_dia)).length,
				totalCount: groupRows.length,
			};
		});
});

function bindLinkMenuPosition(el) {
	const input = el.querySelector("input");
	const menu = el.querySelector(".awesomplete > ul");
	if (!input || !menu) return () => {};

	let animationFrame = null;
	const positionMenu = () => {
		if (animationFrame !== null) cancelAnimationFrame(animationFrame);
		animationFrame = requestAnimationFrame(() => {
			animationFrame = null;
			if (!input.isConnected || !menu.isConnected) return;

			const rect = input.getBoundingClientRect();
			const viewportWidth = document.documentElement.clientWidth;
			const viewportHeight = document.documentElement.clientHeight;
			const gap = 4;
			const edge = 12;
			const width = Math.min(
				Math.max(rect.width, 220),
				Math.max(120, viewportWidth - edge * 2)
			);
			const left = Math.min(
				Math.max(rect.left, edge),
				Math.max(edge, viewportWidth - width - edge)
			);
			const availableBelow = viewportHeight - rect.bottom - gap - edge;
			const availableAbove = rect.top - gap - edge;
			const openAbove = availableBelow < 160 && availableAbove > availableBelow;
			const available = Math.max(80, openAbove ? availableAbove : availableBelow);
			const maxHeight = Math.min(300, available);

			menu.style.setProperty("position", "fixed", "important");
			menu.style.setProperty("left", `${left}px`, "important");
			menu.style.setProperty("right", "auto", "important");
			menu.style.setProperty("width", `${width}px`, "important");
			menu.style.setProperty("min-width", `${width}px`, "important");
			menu.style.setProperty("max-width", `${width}px`, "important");
			menu.style.setProperty("max-height", `${maxHeight}px`, "important");
			menu.style.setProperty("overflow-y", "auto", "important");
			menu.style.setProperty("z-index", "1060", "important");
			if (openAbove) {
				menu.style.setProperty("top", "auto", "important");
				menu.style.setProperty(
					"bottom",
					`${viewportHeight - rect.top + gap}px`,
					"important"
				);
			} else {
				menu.style.setProperty("top", `${rect.bottom + gap}px`, "important");
				menu.style.setProperty("bottom", "auto", "important");
			}
		});
	};

	for (const eventName of ["focus", "click", "input", "awesomplete-open"]) {
		input.addEventListener(eventName, positionMenu);
	}
	window.addEventListener("scroll", positionMenu, true);
	window.addEventListener("resize", positionMenu);

	return () => {
		if (animationFrame !== null) cancelAnimationFrame(animationFrame);
		for (const eventName of ["focus", "click", "input", "awesomplete-open"]) {
			input.removeEventListener(eventName, positionMenu);
		}
		window.removeEventListener("scroll", positionMenu, true);
		window.removeEventListener("resize", positionMenu);
	};
}

function mountLinkControl(el, { value, disabled, placeholder, getQuery }) {
	const state = {
		control: null,
		binding: null,
		disabled: Boolean(disabled),
		initializing: true,
		syncing: false,
		syncSequence: 0,
		getQuery,
		onChange: () => {},
	};
	state.control = frappe.ui.form.make_control({
		parent: el,
		df: {
			fieldtype: "Link",
			fieldname: `ipd_compacting_link_${++linkControlSequence}`,
			options: "Item Attribute Value",
			placeholder,
			only_select: true,
			read_only: state.disabled,
			get_query: () => state.getQuery(),
		},
		render_input: true,
		only_input: true,
	});
	el.__ipdCompactingLink = state;
	Promise.resolve(state.control.set_value(value || "")).then(() => {
		if (el.__ipdCompactingLink !== state) return;
		state.initializing = false;
		state.cleanupMenuPosition = bindLinkMenuPosition(el);
		state.control.df.onchange = () => {
			if (state.initializing || state.syncing) return;
			state.onChange(state.control.get_value() || "");
		};
	});
	return state;
}

function syncLinkControl(state, value) {
	const nextValue = value || "";
	if (state.control.get_value() === nextValue) return;
	const syncSequence = ++state.syncSequence;
	state.syncing = true;
	Promise.resolve(state.control.set_value(nextValue)).finally(() => {
		if (state.syncSequence === syncSequence) state.syncing = false;
	});
}

function updateLinkDisabled(state, disabled) {
	const nextDisabled = Boolean(disabled);
	if (state.disabled === nextDisabled) return;
	state.disabled = nextDisabled;
	state.control.df.read_only = nextDisabled;
	state.control.refresh();
}

function unmountLinkControl(el) {
	const state = el.__ipdCompactingLink;
	if (!state) return;
	state.cleanupMenuPosition?.();
	state.control.df.onchange = null;
	delete el.__ipdCompactingLink;
	$(el).empty();
}

const diaQuery = () => ({ filters: { attribute_name: "Dia" } });

const vCompactingDiaLink = {
	mounted(el, binding) {
		const state = mountLinkControl(el, {
			value: binding.value.cell.compacting_dia,
			disabled: binding.value.disabled,
			placeholder: __("Select Dia"),
			getQuery: diaQuery,
		});
		state.binding = binding.value;
		state.onChange = (value) => {
			state.binding.cell.compacting_dia = value;
			markDirty();
		};
	},
	updated(el, binding) {
		const state = el.__ipdCompactingLink;
		if (!state) return;
		state.binding = binding.value;
		updateLinkDisabled(state, binding.value.disabled);
		syncLinkControl(state, binding.value.cell.compacting_dia);
	},
	beforeUnmount: unmountLinkControl,
};

const vColumnFillDiaLink = {
	mounted(el, binding) {
		const state = mountLinkControl(el, {
			value: "",
			disabled: binding.value.disabled,
			placeholder: "",
			getQuery: diaQuery,
		});
		state.binding = binding.value;
		state.onChange = (value) => {
			if (!value) return;
			fillDiaColumn(
				state.binding.group,
				state.binding.inputDia,
				value
			);
			syncLinkControl(state, "");
		};
	},
	updated(el, binding) {
		const state = el.__ipdCompactingLink;
		if (!state) return;
		state.binding = binding.value;
		updateLinkDisabled(state, binding.value.disabled);
	},
	beforeUnmount: unmountLinkControl,
};

const vColourTemplateLink = {
	mounted(el, binding) {
		let state;
		state = mountLinkControl(el, {
			value: templateColours.value[binding.value.group.cloth_item],
			disabled: binding.value.disabled,
			placeholder: __("Select Colour"),
			getQuery: () => ({
				filters: {
					attribute_name: packingAttribute.value,
					name: [
						"in",
						state.binding.group.colourRows.map(
							(row) => row.packing_attribute_value
						),
					],
				},
			}),
		});
		state.binding = binding.value;
		state.onChange = (value) => {
			templateColours.value[state.binding.group.cloth_item] = value;
		};
	},
	updated(el, binding) {
		const state = el.__ipdCompactingLink;
		if (!state) return;
		state.binding = binding.value;
		updateLinkDisabled(state, binding.value.disabled);
		syncLinkControl(
			state,
			templateColours.value[binding.value.group.cloth_item]
		);
	},
	beforeUnmount: unmountLinkControl,
};

function markDirty() {
	if (typeof cur_frm !== "undefined") cur_frm.dirty();
}

function showFillResult(count, message) {
	frappe.show_alert({
		message: count ? message : __("No cells were available to update"),
		indicator: count ? "green" : "orange",
	});
}

function fillDiaColumn(group, inputDia, compactingDia) {
	if (!compactingDia || !canWrite.value) {
		return;
	}

	const columnIndex = group.dias.indexOf(inputDia);
	let filled = 0;
	group.colourRows.forEach((colourRow) => {
		const cell = colourRow.cells[columnIndex];
		if (cell) {
			cell.compacting_dia = compactingDia;
			filled += 1;
		}
	});
	if (filled) markDirty();
	showFillResult(
		filled,
		__("Updated {0} cell(s) in {1}", [filled, inputDia])
	);
}

function copyColourToBlanks(group) {
	if (!canWrite.value) {
		return;
	}
	const sourceName = templateColours.value[group.cloth_item];
	const sourceRow = group.colourRows.find(
		(row) => row.packing_attribute_value === sourceName
	);
	if (!sourceRow) {
		return;
	}

	let filled = 0;
	sourceRow.cells.forEach((sourceCell, columnIndex) => {
		if (!sourceCell?.compacting_dia) {
			return;
		}
		group.colourRows.forEach((targetRow) => {
			const targetCell = targetRow.cells[columnIndex];
			if (targetCell && !targetCell.compacting_dia) {
				targetCell.compacting_dia = sourceCell.compacting_dia;
				filled += 1;
			}
		});
	});
	if (filled) markDirty();
	showFillResult(
		filled,
		__("Copied {0} value(s) from {1}", [filled, sourceName])
	);
}

function load_data(payload) {
	itemProductionDetail.value = payload?.item_production_detail || "";
	packingAttribute.value = payload?.packing_attribute || "";
	rows.value = (payload?.rows || []).map((row) => ({
		cloth_item: row.cloth_item,
		packing_attribute_value: row.packing_attribute_value,
		input_dia: row.input_dia,
		compacting_dia: row.compacting_dia || "",
	}));
	modified.value = payload?.modified || null;
	canWrite.value = Boolean(payload?.can_write);
	const previousTemplates = templateColours.value;
	templateColours.value = Object.fromEntries(
		clothGroups.value.map((group) => {
			const availableColours = group.colourRows.map(
				(row) => row.packing_attribute_value
			);
			const previous = previousTemplates[group.cloth_item];
			return [
				group.cloth_item,
				availableColours.includes(previous) ? previous : availableColours[0],
			];
		})
	);
}

function get_data() {
	return {
		rows: JSON.parse(JSON.stringify(rows.value)),
		expected_modified: modified.value,
	};
}

defineExpose({ load_data, get_data });
</script>

<style scoped>
.ipd-compacting-card {
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-md);
	background: var(--card-bg, #fff);
	padding: 12px;
}

.ipd-compacting-head {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 16px;
	margin-bottom: 14px;
}

.ipd-compacting-head h4 {
	margin: 0 0 4px;
}

.ipd-compacting-progress {
	white-space: nowrap;
	color: var(--text-muted);
	font-size: var(--text-sm);
}

.ipd-compacting-table {
	margin: 0;
	width: max-content;
	min-width: 0;
	table-layout: fixed;
}

.ipd-compacting-table td,
.ipd-compacting-table th {
	vertical-align: middle;
	padding: 5px 7px;
}

.ipd-compacting-groups {
	display: grid;
	gap: 12px;
}

.ipd-compacting-group {
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-md);
	overflow: hidden;
}

.ipd-compacting-group.is-compact {
	width: fit-content;
	max-width: 100%;
}

.ipd-compacting-group.is-compact .ipd-compacting-matrix-wrap {
	overflow-x: hidden;
}

.ipd-compacting-group-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 10px 12px;
	background: var(--subtle-fg, #f8fafc);
}

.ipd-compacting-group-title {
	display: flex;
	align-items: baseline;
	gap: 10px;
}

.ipd-compacting-group-head h5 {
	margin: 0;
	font-weight: 600;
}

.ipd-compacting-group-title span,
.ipd-compacting-copy-tools > span {
	color: var(--text-muted);
	white-space: nowrap;
}

.ipd-compacting-copy-tools {
	display: flex;
	align-items: center;
	gap: 7px;
}

.ipd-compacting-copy-colour-link {
	width: 120px;
}

.ipd-compacting-link :deep(.frappe-control),
.ipd-compacting-link :deep(.form-group) {
	max-width: none;
	margin-bottom: 0;
}

.ipd-compacting-link :deep(.link-field) {
	width: 100%;
}

.ipd-compacting-matrix-wrap {
	margin-bottom: 0;
	overflow-x: auto;
	overflow-y: hidden;
}

.ipd-compacting-colour-column {
	position: sticky;
	left: 0;
	z-index: 1;
	width: 140px;
	min-width: 140px;
	max-width: 140px;
	background: var(--card-bg, #fff);
}

thead .ipd-compacting-colour-column {
	z-index: 2;
	background: var(--subtle-fg, #f8fafc);
}

.ipd-compacting-dia-column {
	width: 124px;
	min-width: 124px;
	max-width: 124px;
	text-align: center;
}

.ipd-compacting-dia-column span,
.ipd-compacting-dia-column small {
	display: block;
}

.ipd-compacting-dia-column small {
	margin-top: 2px;
	color: var(--text-muted);
	font-weight: 400;
}

.ipd-compacting-column-fill {
	width: 108px;
	margin: 5px auto 0;
	font-weight: 400;
}

.ipd-compacting-cell {
	width: 124px;
	min-width: 124px;
	max-width: 124px;
	text-align: center;
}

.ipd-compacting-cell .ipd-compacting-link {
	width: 108px;
	margin: 0 auto;
}

.ipd-compacting-empty {
	padding: 24px 12px;
	text-align: center;
	color: var(--text-muted);
}

</style>
