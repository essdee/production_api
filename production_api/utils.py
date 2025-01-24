import frappe
from frappe.utils import flt
from frappe.query_builder.builder import Order as OrderBy

def get_bin(item_code, warehouse, lot):
	bin = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse, "lot": lot})
	if not bin:
		bin_obj = _create_bin(item_code, warehouse, lot)
	else:
		bin_obj = frappe.get_doc("Bin", bin)
	bin_obj.flags.ignore_permissions = True
	return bin_obj

def get_or_make_bin(item_code: str, warehouse: str, lot: str, received_type: str) -> str:
	bin_record = frappe.get_cached_value("Bin", {"item_code": item_code, "warehouse": warehouse, "lot": lot, "received_type": received_type})
	if not bin_record:
		bin_obj = _create_bin(item_code, warehouse, lot, received_type)
		bin_record = bin_obj.name
	return bin_record

def _create_bin(item_code, warehouse, lot, received_type):
	"""Create a bin and take care of concurrent inserts."""

	bin_creation_savepoint = "create_bin"
	try:
		frappe.db.savepoint(bin_creation_savepoint)
		bin_obj = frappe.get_doc(doctype="Bin", item_code=item_code, warehouse=warehouse, lot=lot, received_type=received_type)
		bin_obj.flags.ignore_permissions = 1
		bin_obj.insert()
	except frappe.UniqueValidationError:
		frappe.db.rollback(save_point=bin_creation_savepoint)  # preserve transaction in postgres
		bin_obj = frappe.get_last_doc("Bin", {"item_code": item_code, "warehouse": warehouse, 'lot' : lot, "received_type": received_type})

	return bin_obj

def get_unreserved_qty(item,reserved_qty_details):
    
    existing_reserved_qty = reserved_qty_details.get(item['voucher_detail_no'],0)
    bin = get_or_make_bin(item['item_name'],item['warehouse'],item['lot'])
    bin_doc = frappe.get_cached_doc("Bin",bin)
    return bin_doc.actual_qty - existing_reserved_qty

def get_item_variant_stock(item :str, warehouse: str, lot: str) -> float:
    
    sle = frappe.qb.DocType("Stock Ledger Entry")
    
    query =  (
		frappe.qb.from_(sle)
		.select(
			sle.qty_after_transaction
		)
		.where((sle.item == item) & (sle.warehouse == warehouse) & (sle.lot == lot))
		.orderby(sle.creation,OrderBy.desc)
		.limit(1)
	)
    sle_ent =query.run(as_dict=True)
    if len(sle_ent) == 0:
        return 0
    return flt(sle_ent[0]['qty_after_transaction'])
    