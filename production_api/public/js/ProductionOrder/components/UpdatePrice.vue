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
          <!-- <tr>
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
          </tr> -->
        </tbody>
      </table>
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
let sourceAvailability = ref({
  sales_mrp: false,
  box_sticker_mrp: false,
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
  return items;
}

function load_data(data) {
  let payload = JSON.parse(JSON.stringify(data || {}));
  const normalizedItems = getNormalizedItems(payload.items);
  primary_values.value = getNormalizedPrimaryValues(
    payload.primary_values,
    normalizedItems,
  );
  box_qty.value = {};
  total_qty.value = 0;
  sourceAvailability.value = {
    sales_mrp: false,
    box_sticker_mrp: false,
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
    sourceAvailability.value.sales_mrp =
      sourceAvailability.value.sales_mrp || Boolean(row.has_sales_mrp);
    sourceAvailability.value.box_sticker_mrp =
      sourceAvailability.value.box_sticker_mrp ||
      Boolean(row.has_box_sticker_mrp);
  });

  selected_source.value = getSelectedSourceFromRows() || "production_order_mrp";
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
