import frappe
from frappe.utils import today, nowdate, nowtime
from production_api.mrp_stock.utils import get_stock_balance
from production_api.utils import MyCustomException

def execute():
    grn_list = frappe.db.sql(
    """
        SELECT name FROM `tabGoods Received Note` WHERE against = 'Work Order' AND docstatus = 1
        AND DATE(creation) BETWEEN %(from_date)s AND %(to_date)s
        AND is_rework = 0 AND is_return = 0 AND additional_grn = 0
    """, {
        "from_date": "2025-06-21",
        "to_date": today()
    }, as_dict=True)
    received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
    against = {}
    for grn in grn_list:
        grn_doc = frappe.get_doc("Goods Received Note", grn['name'])
        against.setdefault(grn_doc.against_id, {})
        for row in grn_doc.grn_deliverables:
            key = (row.item_variant, grn_doc.lot, grn_doc.supplier)
            against[grn_doc.against_id].setdefault(key, 0)
            against[grn_doc.against_id][key] += row.quantity

    for against_id in against:
        items = []
        supplier_id = None
        for key in against[against_id]:
            variant, lot, supplier = key
            supplier_id = supplier
            balance = get_stock_balance(variant, supplier, received_type)
            used_qty = against[against_id][key]
            cur_qty = 0
            if balance >= used_qty:
                cur_qty = balance - used_qty
            else:
                cur_qty = balance
            items.append({
                "item_variant": variant,
				"lot": lot,
				"received_type": received_type,
				"qty": cur_qty,
            })	
        grouped_items = get_grouped_items(items)
        table_index = -1
        row_index = -1
        final_list = []
        for (lot, item, received_type, stage), items in grouped_items.items():
            sorted_items = sorted(items, key=lambda x: x['item_variant'])
            table_index += 1
            row_index += 1
            primary = frappe.get_cached_value("Item", item, "primary_attribute")
            for item in sorted_items:
                if not primary:
                    row_index += 1
                d = {
                    "item": item['item_variant'],
                    "qty": item['qty'],
                    "lot": lot,
                    "received_type": received_type,
                    "uom": item['uom'],
                    'table_index': table_index,
                    'row_index': row_index,
                    "warehouse": supplier_id,
                    "allow_zero_valuation_rate": 1,
                }
                if item['qty'] == 0:
                    d['make_qty_zero'] = 1

                final_list.append(d)     

        if len(final_list) > 0:
            try:
                doc = frappe.new_doc("Stock Reconciliation")
                doc.purpose = "Stock Reconciliation"
                doc.default_warehouse = supplier_id
                doc.set("items", final_list)
                doc.save(ignore_permissions=True)
                doc.submit()
            except MyCustomException:
                pass
            
def get_grouped_items(selected_items):
    grouped_items = {}
    for item in selected_items:
        variant = item['item_variant']
        doc = frappe.get_cached_doc("Item Variant", variant)
        primary_attr, uom = frappe.get_cached_value("Item", doc.item, ["primary_attribute", "default_unit_of_measure"])
        attr_details = get_variant_attr_values(doc, primary_attr)
        key = (item['lot'], doc.item, item['received_type'], attr_details)
        item['uom'] = uom
        if key not in grouped_items:
            grouped_items[key] = []
        grouped_items[key].append(item)
    return grouped_items    

def get_variant_attr_values(doc, primary_attr):
	attrs = []
	for attr in doc.attributes:
		if attr.attribute != primary_attr:
			attrs.append(attr.attribute_value)
	attrs.sort()
	if attrs:
		attrs = tuple(attrs)
	else:
		attrs = None			
	return attrs        