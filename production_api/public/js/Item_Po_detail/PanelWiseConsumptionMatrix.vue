<template>
	<div v-if="matrix" class="pwc-card">
		<div class="pwc-head">
			<h4>Panel-wise consumption matrix</h4>
			<div class="pwc-progress">{{ completeCount }} / {{ totalCount }} complete</div>
		</div>

		<div class="pwc-tabs">
			<button
				v-for="panel in matrix.panels"
				:key="panel.panel_value"
				type="button"
				class="pwc-tab"
				:class="{ active: panel.panel_value === activePanel }"
				@click="activePanel = panel.panel_value"
			>
				{{ panel.panel_value }}
			</button>
		</div>

		<div v-if="currentPanel" class="pwc-toolbar">
			<div>
				<strong>{{ currentPanel.panel_value }}</strong>
				<span>{{ currentPanel.rows.length }} {{ matrix.attributes.primary }} rows</span>
			</div>
			<div v-if="!locked" class="pwc-toolbar-actions">
				<div v-if="otherPanels.length" class="pwc-panel-fetch">
					<select
						v-model="sourcePanelValue"
						class="form-control input-sm"
						aria-label="Fetch details from panel"
					>
						<option value="">Select panel</option>
						<option
							v-for="panel in otherPanels"
							:key="panel.panel_value"
							:value="panel.panel_value"
						>
							{{ panel.panel_value }}
						</option>
					</select>
					<button
						type="button"
						class="pwc-apply-button"
						:disabled="!sourcePanelValue"
						@click="applyPanelDetails"
					>
						Apply
					</button>
				</div>
				<button
					v-if="currentPackingValues.length > 1"
					type="button"
					class="pwc-copy-button"
					@click="copyFirstColourToPanel"
				>
					Copy {{ currentPackingValues[0] }} across this panel
				</button>
			</div>
		</div>

		<div v-if="currentPanel" class="pwc-scroll">
			<table class="pwc-table">
				<thead>
					<tr>
						<th class="pwc-primary">{{ matrix.attributes.primary }}</th>
						<th v-for="packing in currentPackingValues" :key="packing">
							{{ packing }}
							<small>Dia · kg / piece</small>
						</th>
						<th v-if="!locked" class="pwc-action">Action</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in currentPanel.rows"
						:key="`${currentPanel.panel_value}::${row.primary_value}`"
					>
						<td class="pwc-primary-value">{{ row.primary_value }}</td>
						<td v-for="packing in currentPackingValues" :key="packing">
							<div v-if="!locked" class="pwc-cell">
								<div v-dia-link="cellFor(row, packing)" class="pwc-dia-link"></div>
								<input
									class="form-control input-sm pwc-input pwc-weight"
									type="text"
									inputmode="decimal"
									:value="formatKg(cellFor(row, packing).weight)"
									placeholder="0.0300"
									@change="setWeight(row, packing, $event)"
								/>
							</div>
							<span v-else>
								{{ cellFor(row, packing).dia || "—" }} ·
								{{ formatKg(cellFor(row, packing).weight) || "—" }}
							</span>
						</td>
						<td v-if="!locked" class="pwc-action">
							<button
								type="button"
								class="pwc-fill-button"
								title="Copy the first colour's consumption across this row"
								@click="copyFirstColourToRow(row)"
							>
								Fill →
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const matrix = ref(null);
const activePanel = ref("");
const sourcePanelValue = ref("");
const locked = ref(false);
let diaControlSequence = 0;

const currentPanel = computed(() =>
	(matrix.value?.panels || []).find((panel) => panel.panel_value === activePanel.value)
);
const otherPanels = computed(() =>
	(matrix.value?.panels || []).filter(
		(panel) => panel.panel_value !== activePanel.value
	)
);
const packingValuesFor = (panel) =>
	panel?.packing_values || matrix.value?.packing_values || [];
const currentPackingValues = computed(() => packingValuesFor(currentPanel.value));
const totalCount = computed(() =>
	(matrix.value?.panels || []).reduce(
		(total, panel) => total + panel.rows.length * packingValuesFor(panel).length,
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
					packingValuesFor(panel).filter(
						(packing) => {
							const cell = cellFor(row, packing);
							return cell.dia && Number(cell.weight) > 0;
						}
					).length,
				0
			),
		0
	)
);

function load_data(payload, isLocked = false) {
	matrix.value = payload?.matrix || null;
	locked.value = Boolean(isLocked);
	activePanel.value = matrix.value?.panels?.[0]?.panel_value || "";
	sourcePanelValue.value = "";
}

watch(activePanel, () => {
	sourcePanelValue.value = "";
});

function markDirty() {
	if (typeof cur_frm !== "undefined") cur_frm.dirty();
}

function cellFor(row, packing) {
	row.values ||= {};
	row.values[packing] ||= { dia: null, weight: null };
	return row.values[packing];
}

function bindDiaMenuPosition(el) {
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

function mountDiaLink(el, row) {
	const control = frappe.ui.form.make_control({
		parent: el,
		df: {
			fieldtype: "Link",
			fieldname: `panel_consumption_dia_${++diaControlSequence}`,
			options: "Item Attribute Value",
			placeholder: __("Select Dia"),
			only_select: true,
			get_query: () => ({
				filters: { attribute_name: "Dia" },
			}),
		},
		render_input: true,
		only_input: true,
	});
	const state = {
		control,
		row,
		initializing: true,
		syncing: false,
		syncSequence: 0,
	};
	el.__pwcDiaLink = state;
	Promise.resolve(control.set_value(row.dia || "")).then(() => {
		if (el.__pwcDiaLink !== state) return;
		state.initializing = false;
		state.cleanupMenuPosition = bindDiaMenuPosition(el);
		control.df.onchange = () => {
			if (state.initializing || state.syncing) return;
			const value = control.get_value() || null;
			if (state.row.dia !== value) {
				state.row.dia = value;
				markDirty();
			}
		};
	});
}

function syncDiaLink(el, row) {
	const state = el.__pwcDiaLink;
	if (!state) return;

	state.row = row;
	const value = row.dia || "";
	if (state.control.get_value() === value) return;

	const syncSequence = ++state.syncSequence;
	state.syncing = true;
	Promise.resolve(state.control.set_value(value)).finally(() => {
		if (el.__pwcDiaLink === state && state.syncSequence === syncSequence) {
			state.syncing = false;
		}
	});
}

const vDiaLink = {
	mounted(el, binding) {
		mountDiaLink(el, binding.value);
	},
	updated(el, binding) {
		syncDiaLink(el, binding.value);
	},
	beforeUnmount(el) {
		if (el.__pwcDiaLink) {
			el.__pwcDiaLink.cleanupMenuPosition?.();
			el.__pwcDiaLink.control.df.onchange = null;
			delete el.__pwcDiaLink;
		}
		$(el).empty();
	},
};

function parseWeight(value) {
	const normalized = String(value ?? "").trim();
	if (!normalized) return null;
	if (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(normalized)) {
		frappe.throw("Consumption must be a positive kg value, for example 0.0300.");
	}
	const parsed = Number(normalized);
	if (!Number.isFinite(parsed) || parsed <= 0) {
		frappe.throw("Consumption must be greater than zero, for example 0.0300.");
	}
	return Number(parsed.toFixed(4));
}

function formatKg(value) {
	if (value === null || value === undefined || value === "") return "";
	return Number(value).toFixed(4);
}

function setWeight(row, packing, event) {
	const value = parseWeight(event.target.value);
	cellFor(row, packing).weight = value;
	event.target.value = formatKg(value);
	markDirty();
}

function copyFirstColourToRow(row) {
	const first = currentPackingValues.value[0];
	const source = cellFor(row, first);
	if (!source.dia || !(Number(source.weight) > 0)) {
		frappe.msgprint(`Enter ${first} Dia and consumption first.`);
		return;
	}
	currentPackingValues.value.forEach((packing) => {
		row.values[packing] = { dia: source.dia, weight: source.weight };
	});
	markDirty();
}

function copyFirstColourToPanel() {
	const first = currentPackingValues.value[0];
	const missing = currentPanel.value.rows.find((row) => {
		const cell = cellFor(row, first);
		return !cell.dia || !(Number(cell.weight) > 0);
	});
	if (missing) {
		frappe.msgprint(
			`Enter ${first} Dia and consumption for ${missing.primary_value} first.`
		);
		return;
	}
	currentPanel.value.rows.forEach((row) => {
		const source = cellFor(row, first);
		currentPackingValues.value.forEach((packing) => {
			row.values[packing] = { dia: source.dia, weight: source.weight };
		});
	});
	markDirty();
}

function mappedSourcePacking(sourcePanel, targetPanel, targetPacking, targetIndex) {
	const sourcePackings = packingValuesFor(sourcePanel);
	const targetPackings = packingValuesFor(targetPanel);
	if (sourcePackings.includes(targetPacking)) return targetPacking;
	if (sourcePackings.length === targetPackings.length) {
		return sourcePackings[targetIndex];
	}
	if (sourcePackings.length === 1) return sourcePackings[0];
	return null;
}

function applyPanelDetails() {
	const sourcePanel = (matrix.value?.panels || []).find(
		(panel) => panel.panel_value === sourcePanelValue.value
	);
	const targetPanel = currentPanel.value;
	if (!sourcePanel || !targetPanel) {
		frappe.msgprint("Select a panel to fetch details from.");
		return;
	}

	const sourceRows = new Map(
		sourcePanel.rows.map((row) => [row.primary_value, row])
	);
	const copiedRows = [];
	for (const targetRow of targetPanel.rows) {
		const sourceRow = sourceRows.get(targetRow.primary_value);
		if (!sourceRow) {
			frappe.msgprint(
				`${targetRow.primary_value} is missing in panel ${sourcePanel.panel_value}.`
			);
			return;
		}

		const copiedValues = {};
		const targetPackings = packingValuesFor(targetPanel);
		for (const [targetIndex, targetPacking] of targetPackings.entries()) {
			const sourcePacking = mappedSourcePacking(
				sourcePanel,
				targetPanel,
				targetPacking,
				targetIndex
			);
			if (!sourcePacking) {
				frappe.msgprint(
					`Cannot match ${targetPacking} in ${targetPanel.panel_value} with a ` +
						`colour column in ${sourcePanel.panel_value}.`
				);
				return;
			}
			const sourceCell = cellFor(sourceRow, sourcePacking);
			if (!sourceCell.dia || !(Number(sourceCell.weight) > 0)) {
				frappe.msgprint(
					`Enter Dia and consumption for ${sourcePanel.panel_value}, ` +
						`${sourceRow.primary_value}, ${sourcePacking} first.`
				);
				return;
			}
			copiedValues[targetPacking] = {
				dia: sourceCell.dia,
				weight: sourceCell.weight,
			};
		}
		copiedRows.push({ targetRow, copiedValues });
	}

	copiedRows.forEach(({ targetRow, copiedValues }) => {
		targetRow.values = copiedValues;
	});
	markDirty();
	frappe.show_alert({
		message: `Details fetched from ${sourcePanel.panel_value}.`,
		indicator: "green",
	});
}

function get_data() {
	if (!matrix.value) return null;
	for (const panel of matrix.value.panels) {
		for (const row of panel.rows) {
			for (const packing of packingValuesFor(panel)) {
				const cell = cellFor(row, packing);
				if (!cell.dia) {
					frappe.throw(
						`Enter Dia for ${panel.panel_value}, ${row.primary_value}, ${packing}.`
					);
				}
				if (!(Number(cell.weight) > 0)) {
					frappe.throw(
						`Enter consumption for ${panel.panel_value}, ${row.primary_value}, ` +
						`${packing} (0.0300 means 30 grams).`
					);
				}
			}
		}
	}
	return JSON.parse(JSON.stringify(matrix.value));
}

defineExpose({ load_data, get_data });
</script>

<style scoped>
.pwc-card {
	border: 1px solid var(--border-color, #dfe3e8);
	border-radius: 14px;
	background: var(--card-bg, #fff);
	overflow: hidden;
	margin-top: 14px;
	box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}
.pwc-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	padding: 18px 20px;
	background: linear-gradient(135deg, #f4fbfa 0%, var(--card-bg, #fff) 72%);
	border-bottom: 1px solid var(--border-color, #e5e7eb);
}
.pwc-head h4 {
	margin: 0;
	font-size: 16px;
	font-weight: 700;
	letter-spacing: -0.01em;
	color: var(--text-color, #1f2937);
}
.pwc-progress {
	flex: 0 0 auto;
	padding: 6px 10px;
	border-radius: 999px;
	border: 1px solid #c9e8e2;
	background: #eaf7f4;
	color: #0f766e;
	font-size: 11px;
	font-weight: 700;
}
.pwc-tabs {
	display: flex;
	gap: 7px;
	padding: 12px 16px;
	overflow-x: auto;
	border-bottom: 1px solid var(--border-color, #e5e7eb);
	background: var(--subtle-fg, #f8fafc);
}
.pwc-tab {
	border: 1px solid transparent;
	border-radius: 8px;
	background: transparent;
	padding: 7px 12px;
	color: var(--text-muted, #64748b);
	font-size: 12px;
	font-weight: 600;
	white-space: nowrap;
	transition: all 0.15s ease;
}
.pwc-tab.active {
	border-color: #bfe2dc;
	background: var(--card-bg, #fff);
	color: #0f766e;
	box-shadow: 0 2px 7px rgba(15, 118, 110, 0.1);
}
.pwc-toolbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 13px 16px;
	background: var(--card-bg, #fff);
}
.pwc-toolbar strong {
	display: block;
	font-size: 13px;
	color: var(--text-color, #1f2937);
}
.pwc-toolbar span {
	display: block;
	margin-top: 2px;
	color: var(--text-muted, #64748b);
	font-size: 10px;
}
.pwc-toolbar-actions,
.pwc-panel-fetch {
	display: flex;
	align-items: center;
	gap: 8px;
}
.pwc-panel-fetch select {
	min-width: 170px;
	height: 32px;
}
.pwc-copy-button,
.pwc-apply-button,
.pwc-fill-button {
	border: 1px solid var(--border-color, #dfe3e8);
	border-radius: 8px;
	background: var(--card-bg, #fff);
	color: var(--text-color, #334155);
	font-size: 11px;
	font-weight: 600;
	line-height: 1.2;
	transition: all 0.15s ease;
}
.pwc-copy-button {
	padding: 7px 11px;
}
.pwc-apply-button {
	padding: 7px 14px;
	border-color: #0f766e;
	background: #0f766e;
	color: #fff;
}
.pwc-apply-button:disabled {
	border-color: var(--border-color, #dfe3e8);
	background: var(--subtle-fg, #f1f5f9);
	color: var(--text-muted, #94a3b8);
	cursor: not-allowed;
}
.pwc-fill-button {
	padding: 6px 9px;
	white-space: nowrap;
}
.pwc-copy-button:hover,
.pwc-apply-button:not(:disabled):hover,
.pwc-fill-button:hover {
	border-color: #75bdb3;
	background: #eef9f7;
	color: #0f766e;
}
.pwc-scroll {
	overflow-x: auto;
	padding: 0 16px 16px;
}
.pwc-cell {
	display: grid;
	grid-template-columns: minmax(120px, 1fr) minmax(90px, 0.65fr);
	gap: 7px;
	align-items: center;
}
.pwc-table {
	min-width: 850px;
	margin: 0;
	table-layout: fixed;
	width: 100%;
	overflow: hidden;
	border: 1px solid var(--border-color, #e5e7eb);
	border-radius: 10px;
	border-spacing: 0;
	border-collapse: separate;
}
.pwc-table th {
	padding: 10px 9px;
	border-right: 1px solid var(--border-color, #e5e7eb);
	border-bottom: 1px solid var(--border-color, #e5e7eb);
	background: var(--subtle-fg, #f8fafc);
	color: var(--text-color, #475569);
	font-size: 11px;
	font-weight: 700;
	text-align: left;
	vertical-align: bottom;
}
.pwc-table th:last-child,
.pwc-table td:last-child {
	border-right: 0;
}
.pwc-table th small {
	display: block;
	margin-top: 2px;
	color: var(--text-muted, #94a3b8);
	font-size: 9px;
	font-weight: 500;
}
.pwc-table td {
	padding: 8px;
	border-right: 1px solid var(--border-color, #e5e7eb);
	border-bottom: 1px solid var(--border-color, #e5e7eb);
	background: var(--card-bg, #fff);
	vertical-align: middle;
}
.pwc-table tbody tr:last-child td {
	border-bottom: 0;
}
.pwc-table tbody tr:hover td {
	background: var(--subtle-fg, #fafcfd);
}
.pwc-primary,
.pwc-dia {
	width: 125px;
}
.pwc-primary-value {
	color: var(--text-color, #334155);
	font-weight: 700;
}
.pwc-input {
	height: 32px;
	border: 1px solid var(--border-color, #dfe3e8);
	border-radius: 8px;
	background: var(--control-bg, #fff);
	box-shadow: none;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.pwc-input:focus {
	border-color: #55aaa0;
	box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.1);
}
.pwc-dia-link {
	min-width: 108px;
}
.pwc-dia-link :deep(.frappe-control),
.pwc-dia-link :deep(.form-group),
.pwc-dia-link :deep(.control-input-wrapper) {
	margin: 0;
}
.pwc-dia-link :deep(.control-label) {
	display: none;
}
.pwc-dia-link :deep(.control-input),
.pwc-dia-link :deep(.awesomplete),
.pwc-dia-link :deep(input) {
	width: 100%;
}
.pwc-dia-link :deep(input) {
	height: 32px;
	border-radius: 8px;
}
.pwc-weight {
	min-width: 92px;
	font-variant-numeric: tabular-nums;
}
.pwc-action {
	width: 78px;
	text-align: center;
}
@media (max-width: 900px) {
	.pwc-toolbar,
	.pwc-toolbar-actions {
		align-items: stretch;
		flex-direction: column;
	}
	.pwc-panel-fetch select {
		min-width: 0;
		flex: 1;
	}
}
</style>
