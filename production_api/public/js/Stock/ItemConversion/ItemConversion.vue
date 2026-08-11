<template>
    <div class="item-conversion">
        <div class="item-conversion-summary">
            <div>
                <span class="text-muted">From Value</span>
                <strong>{{ format_currency_value(from_total) }}</strong>
            </div>
            <div>
                <span class="text-muted">To Value</span>
                <strong>{{ format_currency_value(to_total) }}</strong>
            </div>
            <div :class="difference_class">
                <span>Difference</span>
                <strong>{{ format_currency_value(difference) }}</strong>
                <small v-if="has_difference">Value not matched</small>
            </div>
        </div>

        <h5>From Item</h5>
        <item-lot-fetcher
            :items="from_items"
            :other-inputs="other_inputs"
            :table-fields="from_table_fields"
            :qty-fields="from_qty_fields"
            :allow-secondary-qty="true"
            :args="from_args"
            :edit="docstatus == 0"
            :validate-qty="true"
            :validate="validate_single_selection"
            @itemadded="from_updated"
            @itemupdated="from_updated"
            @itemremoved="from_updated">
        </item-lot-fetcher>

        <h5 class="mt-4 mb-1">To Item</h5>
        <p v-if="docstatus == 0" class="small text-muted">
            Rate is calculated automatically when there is one target row.
        </p>
        <item-lot-fetcher
            :items="to_items"
            :other-inputs="other_inputs"
            :table-fields="to_table_fields"
            :qty-fields="to_qty_fields"
            :allow-secondary-qty="true"
            :args="to_args"
            :edit="docstatus == 0"
            :validate-qty="true"
            :validate="validate_single_selection"
            @itemadded="to_updated"
            @itemupdated="to_updated"
            @itemremoved="to_updated">
        </item-lot-fetcher>
    </div>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";
import EventBus from "../../bus.js";
import ItemLotFetcher from "../../components/ItemLotFetch.vue";

const docstatus = ref(cur_frm.doc.docstatus);
const from_items = ref([]);
const to_items = ref([]);

const other_inputs = ref([
    {
        name: "remarks",
        parent: "remarks-control",
        df: {
            fieldtype: "Data",
            fieldname: "remarks",
            label: "Remarks",
        },
    },
    {
        name: "received_type",
        parent: "received-type-control",
        df: {
            fieldtype: "Link",
            fieldname: "received_type",
            label: "Received Type",
            options: "GRN Item Type",
            reqd: true,
        },
    },
]);

const from_table_fields = ref([
    {
        name: "rate",
        label: "Valuation Rate",
        uses_primary_attribute: 1,
    },
    {
        name: "remarks",
        label: "Remarks",
    },
    {
        name: "received_type",
        label: "Received Type",
    },
]);

const to_table_fields = ref([
    {
        name: "rate",
        label: "Calculated Rate",
        uses_primary_attribute: 1,
    },
    {
        name: "remarks",
        label: "Remarks",
    },
    {
        name: "received_type",
        label: "Received Type",
    },
]);

const from_qty_fields = ref([]);
const to_qty_fields = ref([]);

const from_args = ref({
    docstatus: cur_frm.doc.docstatus,
    can_edit: function() {
        return true;
    },
    can_create: function() {
        return get_quantity_values(from_items.value).length < 1;
    },
    can_remove: function() {
        return true;
    },
    item_query: function() {
        const filters = { is_stock_item: 1 };
        if (cur_frm.doc.from_item) {
            filters.name = cur_frm.doc.from_item;
        }
        return { filters };
    },
});

const to_args = ref({
    docstatus: cur_frm.doc.docstatus,
    can_edit: function() {
        return true;
    },
    can_create: function() {
        return get_quantity_values(to_items.value).length < 1;
    },
    can_remove: function() {
        return true;
    },
    item_query: function() {
        const filters = { is_stock_item: 1 };
        if (cur_frm.doc.to_item) {
            filters.name = cur_frm.doc.to_item;
        }
        return { filters };
    },
});

const from_total = computed(() => get_items_total(from_items.value));
const to_total = computed(() => get_items_total(to_items.value));
const difference = computed(() => round_currency(from_total.value - to_total.value));
const has_difference = computed(() => Math.abs(difference.value) > 0.001);
const difference_class = computed(() => {
    return has_difference.value ? "text-danger" : "text-success";
});

function to_number(value) {
    value = Number(value);
    return Number.isFinite(value) ? value : 0;
}

function round_currency(value) {
    return Math.round(to_number(value) * 1000) / 1000;
}

function round_rate(value) {
    return Number(to_number(value).toFixed(9));
}

function get_quantity_values(groups) {
    const values = [];
    (groups || []).forEach((group) => {
        (group.items || []).forEach((item) => {
            Object.values(item.values || {}).forEach((value) => {
                if (to_number(value.qty) > 0) values.push(value);
            });
        });
    });
    return values;
}

function auto_balance_single_to_rate() {
    const target_values = get_quantity_values(to_items.value);
    if (target_values.length !== 1 || from_total.value <= 0) return false;

    target_values[0].rate = round_rate(
        from_total.value / to_number(target_values[0].qty)
    );
    return true;
}

function validate_single_selection(item) {
    const selected = Object.values(item.values || {}).filter(
        (value) => to_number(value.qty) > 0
    );
    if (selected.length === 1) return true;

    frappe.show_alert({
        message: __("Enter quantity for exactly one item row."),
        indicator: "red",
    });
    return false;
}

function get_items_total(groups) {
    let total = 0;
    (groups || []).forEach((group) => {
        (group.items || []).forEach((item) => {
            Object.values(item.values || {}).forEach((value) => {
                // Preserve valuation-rate precision; only the final amount is
                // rounded to currency precision.
                total += to_number(value.qty) * to_number(value.rate);
            });
        });
    });
    return round_currency(total);
}

function format_currency_value(value) {
    const formatted = frappe.format(to_number(value), { fieldtype: "Currency" });
    const div = document.createElement("div");
    div.innerHTML = formatted;
    return div.textContent || div.innerText || formatted;
}

function sync_totals() {
    // Only a draft may be dirtied — set_value on a submitted doc flips it to "Not Saved".
    if (cur_frm.doc.docstatus != 0) return;
    const values = {
        from_total_amount: from_total.value,
        to_total_amount: to_total.value,
        difference_amount: difference.value,
    };

    Object.keys(values).forEach((fieldname) => {
        if (to_number(cur_frm.doc[fieldname]) !== values[fieldname]) {
            cur_frm.set_value(fieldname, values[fieldname]);
        }
    });
}

function update_status() {
    docstatus.value = cur_frm.doc.docstatus;
    from_args.value.docstatus = cur_frm.doc.docstatus;
    to_args.value.docstatus = cur_frm.doc.docstatus;
}

function load_data(data) {
    from_items.value = data.from_items || [];
    to_items.value = data.to_items || [];
    // Submitted/cancelled docs show their stored rates — refetching valuation here
    // would read post-submission stock (including this doc's own ledger entries).
    if (cur_frm.doc.docstatus != 0) return;
    nextTick(async () => {
        await apply_from_valuation_rates();
        auto_balance_single_to_rate();
        sync_totals();
    });
}

function get_items() {
    return {
        from_items: from_items.value,
        to_items: to_items.value,
        from_total_amount: from_total.value,
        to_total_amount: to_total.value,
        difference_amount: difference.value,
        has_difference: has_difference.value,
    };
}

function updated() {
    nextTick(sync_totals);
    EventBus.$emit("item_conversion_updated", true);
}

async function from_updated() {
    await apply_from_valuation_rates();
    auto_balance_single_to_rate();
    updated();
}

function to_updated() {
    auto_balance_single_to_rate();
    updated();
}

function get_value_attributes(group, item, key) {
    const attributes = { ...(item.attributes || {}) };
    if (group.primary_attribute && key !== "default") {
        attributes[group.primary_attribute] = key;
    }
    return attributes;
}

function fetch_valuation_rate(args) {
    return new Promise((resolve) => {
        frappe.call({
            method: "production_api.mrp_stock.doctype.item_conversion.item_conversion.get_item_conversion_valuation_rate",
            args: args,
            no_spinner: true,
            callback: function(r) {
                resolve(r.message || {});
            },
        });
    });
}

async function apply_from_valuation_rates() {
    const calls = [];
    (from_items.value || []).forEach((group) => {
        (group.items || []).forEach((item) => {
            Object.entries(item.values || {}).forEach(([key, value]) => {
                if (!to_number(value.qty)) {
                    value.rate = 0;
                    return;
                }

                calls.push(
                    fetch_valuation_rate({
                        item: item.name,
                        attributes: JSON.stringify(get_value_attributes(group, item, key)),
                        lot: item.lot,
                        received_type: item.received_type,
                        uom: item.default_uom,
                        warehouse: cur_frm.doc.warehouse,
                        posting_date: cur_frm.doc.posting_date,
                        posting_time: cur_frm.doc.posting_time,
                    }).then((data) => {
                        value.rate = to_number(data.rate);
                    })
                );
            });
        });
    });

    await Promise.all(calls);
}

async function refresh_from_rates() {
    await apply_from_valuation_rates();
    auto_balance_single_to_rate();
    sync_totals();
}

defineExpose({
    from_items,
    to_items,
    load_data,
    update_status,
    get_items,
    refresh_from_rates,
});
</script>

<style scoped>
.item-conversion-summary {
    align-items: center;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    justify-content: flex-end;
    margin-bottom: 16px;
    padding: 8px 10px;
}

.item-conversion-summary > div {
    align-items: center;
    display: flex;
    gap: 6px;
    min-height: 28px;
}

.item-conversion-summary small {
    font-weight: 600;
}
</style>
