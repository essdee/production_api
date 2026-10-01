<template>
  <div ref="root" class="box-container">
    <div class="section">
      <table class="styled-table">
        <thead>
          <tr>
            <th>Size</th>
            <th v-for="(value, index) in primary_values" :key="index">
              {{ value }}
            </th>
            <th>Total</th>
            <th>Select</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Qty</td>
            <td v-for="(value, index) in primary_values" :key="index">
              <input
                type="number"
                v-model.number="box_qty[value].qty"
                :disabled="true"
                class="styled-input"
              />
            </td>
            <td>{{ total_qty }}</td>
            <td></td>
          </tr>
          <tr>
            <td>Ratio</td>
            <td v-for="(value, index) in primary_values" :key="index">
              <input
                type="number"
                :value="displayValue(box_qty[value].ratio)"
                :disabled="true"
                class="styled-input"
              />
            </td>
            <td></td>
            <td></td>
          </tr>
          <tr>
            <td>Sales Item MRP</td>
            <td v-for="(value, index) in primary_values" :key="index">
              <input
                type="number"
                :value="displayValue(box_qty[value].sales_mrp)"
                :disabled="true"
                class="styled-input"
              />
            </td>
            <td></td>
            <td>
              <label class="option-label">
                <input
                  type="radio"
                  name="mrp-source"
                  value="sales_mrp"
                  v-model="selected_source"
                  :disabled="!sourceAvailability.sales_mrp"
                />
                <span>Use</span>
              </label>
            </td>
          </tr>
          <tr>
            <td>Box Sticker MRP</td>
            <td v-for="(value, index) in primary_values" :key="index">
              <input
                type="number"
                :value="displayValue(box_qty[value].box_sticker_mrp)"
                :disabled="true"
                class="styled-input"
              />
            </td>
            <td></td>
            <td>
              <label class="option-label">
                <input
                  type="radio"
                  name="mrp-source"
                  value="box_sticker_mrp"
                  v-model="selected_source"
                  :disabled="!sourceAvailability.box_sticker_mrp"
                />
                <span>Use</span>
              </label>
            </td>
          </tr>
          <tr>
            <td>Production Order MRP</td>
            <td v-for="(value, index) in primary_values" :key="index">
              <input
                type="number"
                :value="displayValue(box_qty[value].production_order_mrp)"
                :disabled="true"
                class="styled-input"
              />
            </td>
            <td></td>
            <td>
              <label class="option-label">
                <input
                  type="radio"
                  name="mrp-source"
                  value="production_order_mrp"
                  v-model="selected_source"
                />
                <span>Use</span>
              </label>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="lots.length" class="section lot-section">
      <div class="section-heading lot-section-heading">
        <strong>Lot-wise MRP</strong>
        <div class="lot-bulk-controls">
          <span class="bulk-label">Update all:</span>
          <label
            v-for="source in lotSourceOptions"
            :key="`bulk-${source.value}`"
            :class="[
              'lot-source-option',
              { disabled: !lotSourceAvailable(source.value) },
            ]"
          >
            <input
              type="radio"
              name="lot-source-all"
              :value="source.value"
              v-model="bulk_lot_source"
              :disabled="!lotSourceAvailable(source.value)"
            />
            <span>{{ source.label }}</span>
          </label>
          <button
            type="button"
            class="btn btn-primary btn-xs"
            :disabled="
              !bulk_lot_source ||
              !lotSourceAvailable(bulk_lot_source) ||
              !hasUnlockedLots()
            "
            @click="applyLotSourceToAll"
          >
            Update All
          </button>
          <span class="bulk-hint">Unprinted lots only</span>
        </div>
      </div>
      <div class="table-scroll">
        <table class="styled-table lot-table">
          <thead>
            <tr>
              <th>Lot</th>
              <th>Status</th>
              <th>Price Source</th>
              <th v-for="size in primary_values" :key="size">{{ size }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lot in lots" :key="lot.lot">
              <td class="lot-name">{{ lot.lot }}</td>
              <td>
                <span
                  :class="['status-pill', lotStatusClass(lot)]"
                >
                  {{ lotStatusLabel(lot) }}
                </span>
              </td>
              <td class="lot-source-cell">
                <span v-if="lot.locked" class="locked-source">
                  Sticker snapshot
                </span>
                <div v-else class="lot-source-options">
                  <label
                    v-for="source in lotSourceOptions"
                    :key="source.value"
                    :class="[
                      'lot-source-option',
                      { disabled: !lotSourceAvailable(source.value) },
                    ]"
                  >
                    <input
                      type="radio"
                      :name="`lot-source-${lot.lot}`"
                      :value="source.value"
                      v-model="lot.selected_source"
                      :disabled="!lotSourceAvailable(source.value)"
                      @change="applyLotSource(lot, source.value)"
                    />
                    <span>{{ source.label }}</span>
                  </label>
                  <span v-if="lot.selected_source === 'manual'" class="custom-source">
                    Custom
                  </span>
                </div>
              </td>
              <td
                v-for="size in primary_values"
                :key="size"
                class="lot-price-cell"
              >
                <template v-if="lot.locked">
                  <div class="effective-price">
                    {{ displayValue(lotPrice(lot, size).effective_mrp) }}
                  </div>
                </template>
                <template v-else>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    v-model="lotPrice(lot, size).override_mrp"
                    :placeholder="String(selectedPpoMrp(size) || '')"
                    class="styled-input"
                    @input="markLotManual(lot)"
                  />
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const root = ref(null);
const primary_values = ref([]);
let box_qty = ref({});
let total_qty = ref(0);
let selected_source = ref("production_order_mrp");
let lots = ref([]);
let bulk_lot_source = ref(null);
const lotSourceOptions = [
  { value: "sales_mrp", label: "Sales Item" },
  { value: "box_sticker_mrp", label: "Box Sticker" },
];
let sourceAvailability = ref({
  sales_mrp: false,
  box_sticker_mrp: false,
  production_order_mrp: true,
});

function normalizeKey(value) {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function getNormalizedPrimaryValues(values, items = {}) {
  const normalized = [];
  const seen = new Set();
  (values || []).forEach((value) => {
    const key = normalizeKey(value);
    if (!key || seen.has(key)) return;
    seen.add(key);
    normalized.push(key);
  });

  if (!normalized.length) {
    Object.keys(items || {}).forEach((value) => {
      const key = normalizeKey(value);
      if (!key || seen.has(key)) return;
      seen.add(key);
      normalized.push(key);
    });
  }

  return normalized;
}

function getNormalizedItems(items = {}) {
  const normalized = {};
  Object.entries(items || {}).forEach(([key, value]) => {
    const normalizedKey = normalizeKey(key);
    if (!normalizedKey) return;
    normalized[normalizedKey] = value || {};
  });
  return normalized;
}

function get_items() {
  let items = JSON.parse(JSON.stringify(box_qty.value));
  Object.keys(items).forEach((key) => {
    items[key].selected_source = selected_source.value;
  });
  const lot_price_overrides = {};
  lots.value.forEach((lot) => {
    lot_price_overrides[lot.lot] = {};
    primary_values.value.forEach((size) => {
      const value = lotPrice(lot, size).override_mrp;
      lot_price_overrides[lot.lot][size] =
        value === "" || value === null || value === undefined
          ? null
          : Number(value);
    });
  });
  return { items, lot_price_overrides };
}

function load_data(data) {
  let payload = JSON.parse(JSON.stringify(data || {}));
  const normalizedItems = getNormalizedItems(payload.items);
  primary_values.value = getNormalizedPrimaryValues(
    payload.primary_values,
    normalizedItems
  );
  box_qty.value = {};
  total_qty.value = 0;
  sourceAvailability.value = {
    sales_mrp: false,
    box_sticker_mrp: false,
    production_order_mrp: true,
  };

  primary_values.value.forEach((key) => {
    let row = normalizedItems[key] || {};
    box_qty.value[key] = {
      qty: Number(row.qty || 0),
      ratio: Number(row.ratio || 0),
      sales_mrp: row.sales_mrp,
      box_sticker_mrp: row.box_sticker_mrp,
      production_order_mrp: Number(row.production_order_mrp || 0),
      has_sales_mrp: Boolean(row.has_sales_mrp),
      has_box_sticker_mrp: Boolean(row.has_box_sticker_mrp),
      selected_source: row.selected_source || "production_order_mrp",
    };
    total_qty.value += Number(row.qty || 0);
  });

  sourceAvailability.value.sales_mrp = primary_values.value.every((size) => {
    const row = box_qty.value[size] || {};
    return row.has_sales_mrp && Number(row.sales_mrp) > 0;
  });
  sourceAvailability.value.box_sticker_mrp = primary_values.value.every((size) => {
    const row = box_qty.value[size] || {};
    return row.has_box_sticker_mrp && Number(row.box_sticker_mrp) > 0;
  });

  selected_source.value = getSelectedSourceFromRows() || "production_order_mrp";
  bulk_lot_source.value = null;
  lots.value = (payload.lots || []).map((lot) => {
    const prices = {};
    primary_values.value.forEach((size) => {
      const price = (lot.prices || {})[size] || {};
      prices[size] = {
        ...price,
        override_mrp:
          price.override_mrp === null || price.override_mrp === undefined
            ? null
            : Number(price.override_mrp),
      };
    });
    const normalizedLot = { ...lot, prices, selected_source: null };
    normalizedLot.selected_source = inferLotSource(normalizedLot);
    return normalizedLot;
  });
}

function displayValue(value) {
  return value === null || value === undefined ? "" : value;
}

function getSelectedSourceFromRows() {
  for (const key of primary_values.value) {
    if (box_qty.value[key]?.selected_source) {
      return box_qty.value[key].selected_source;
    }
  }
  return null;
}

function lotPrice(lot, size) {
  if (!lot.prices[size]) {
    lot.prices[size] = {
      override_mrp: null,
      effective_mrp: selectedPpoMrp(size),
      printed_quantity: 0,
    };
  }
  return lot.prices[size];
}

function selectedPpoMrp(size) {
  const row = box_qty.value[size] || {};
  if (selected_source.value === "sales_mrp" && row.has_sales_mrp) {
    return row.sales_mrp;
  }
  if (selected_source.value === "box_sticker_mrp" && row.has_box_sticker_mrp) {
    return row.box_sticker_mrp;
  }
  return row.production_order_mrp;
}

function lotSourceValue(source, size) {
  const row = box_qty.value[size] || {};
  if (source === "sales_mrp") return row.sales_mrp;
  if (source === "box_sticker_mrp") return row.box_sticker_mrp;
  return null;
}

function lotSourceAvailable(source) {
  if (!primary_values.value.length) return false;
  return primary_values.value.every(
    (size) => Number(lotSourceValue(source, size)) > 0
  );
}

function applyLotSource(lot, source) {
  if (lot.locked || !lotSourceAvailable(source)) return;
  lot.selected_source = source;
  primary_values.value.forEach((size) => {
    const price = lotPrice(lot, size);
    price.override_mrp = Number(lotSourceValue(source, size));
    price.has_override = true;
  });
}

function hasUnlockedLots() {
  return lots.value.some((lot) => !lot.locked);
}

function applyLotSourceToAll() {
  const source = bulk_lot_source.value;
  if (!source || !lotSourceAvailable(source)) return;
  lots.value.forEach((lot) => {
    if (!lot.locked) applyLotSource(lot, source);
  });
}

function markLotManual(lot) {
  lot.selected_source = "manual";
}

function lotHasCompletePrice(lot) {
  return primary_values.value.every(
    (size) => Number(lotPrice(lot, size).override_mrp) > 0
  );
}

function samePrice(left, right) {
  return Math.abs(Number(left) - Number(right)) < 0.000001;
}

function inferLotSource(lot) {
  if (lot.locked) return "locked";
  if (!lotHasCompletePrice(lot)) return null;
  for (const source of lotSourceOptions) {
    if (
      lotSourceAvailable(source.value) &&
      primary_values.value.every((size) =>
        samePrice(
          lotPrice(lot, size).override_mrp,
          lotSourceValue(source.value, size)
        )
      )
    ) {
      return source.value;
    }
  }
  return "manual";
}

function lotStatusLabel(lot) {
  if (lot.locked) return "Printed · Locked";
  return lotHasCompletePrice(lot) ? "Price Set" : "Price Required";
}

function lotStatusClass(lot) {
  if (lot.locked) return "locked";
  return lotHasCompletePrice(lot) ? "set" : "required";
}

defineExpose({
  get_items,
  load_data,
});
</script>

<style scoped>
.box-container {
  padding: 10px 0;
  font-family: var(--font-stack);
}

.section {
  background: #fff;
  border: 1px solid #d1d8dd;
  border-radius: 4px;
  overflow: hidden;
}

.lot-section {
  margin-top: 14px;
}

.section-heading {
  padding: 7px 10px;
  border-bottom: 1px solid #d1d8dd;
}

.lot-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.lot-bulk-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.bulk-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.bulk-hint {
  font-size: 11px;
  color: #64748b;
}

.table-scroll {
  overflow-x: auto;
}

.lot-table {
  min-width: max-content;
}

.lot-table th,
.lot-table td {
  padding: 5px 7px;
}

.lot-table th {
  font-size: 12px;
}

.lot-table th:first-child,
.lot-table td:first-child {
  min-width: 86px;
}

.lot-table th:nth-child(2),
.lot-table td:nth-child(2) {
  min-width: 104px;
}

.lot-table th:nth-child(3),
.lot-table td:nth-child(3) {
  min-width: 132px;
}

.lot-name {
  white-space: nowrap;
  font-weight: 600;
}

.lot-price-cell {
  min-width: 84px;
}

.lot-table .styled-input {
  width: 72px;
  height: 26px;
  padding: 2px 5px;
}

.status-pill {
  display: inline-block;
  padding: 3px 7px;
  border-radius: 10px;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 600;
}

.status-pill.locked {
  background: #fee2e2;
  color: #991b1b;
}

.status-pill.set {
  background: #dcfce7;
  color: #166534;
}

.status-pill.required {
  background: #fef3c7;
  color: #92400e;
}

.lot-source-cell {
  text-align: left !important;
}

.lot-source-options {
  display: grid;
  gap: 3px;
}

.lot-source-option {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 500;
  color: #334155;
  cursor: pointer;
}

.lot-source-option.disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.locked-source,
.custom-source {
  white-space: nowrap;
  font-size: 11px;
  color: #64748b;
}

.effective-price {
  font-weight: 700;
}

.styled-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0;
  font-size: 13px;
  color: #1f2937;
}

.styled-table th {
  background-color: #f7fafc;
  color: #64748b;
  font-weight: 700;
  padding: 8px 12px;
  border-bottom: 1px solid #d1d8dd;
  border-right: 1px solid #d1d8dd;
  text-align: center;
}

.styled-table th:last-child {
  border-right: none;
}

.styled-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #d1d8dd;
  border-right: 1px solid #d1d8dd;
  text-align: center;
  vertical-align: middle;
}

.styled-table td:last-child {
  border-right: none;
}

.styled-table tr:last-child td {
  border-bottom: none;
}

.styled-table tr:hover {
  background-color: #f9fafb;
}

.styled-input {
  width: 100%;
  max-width: 92px;
  height: 28px;
  padding: 4px 8px;
  font-size: 13px;
  border: 1px solid #d1d8dd;
  border-radius: 4px;
  text-align: center;
  background-color: #fff;
  color: #111827;
  transition: border-color 0.1s ease;
  outline: none;
}

.styled-input:focus {
  border-color: #1b8dff;
  background-color: #fff;
}

.styled-input:disabled {
  background-color: #f3f3f3;
  cursor: not-allowed;
  border-color: #d1d8dd;
}

.option-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #475569;
}

input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

input[type="number"] {
  -moz-appearance: textfield;
  appearance: none;
}
</style>
