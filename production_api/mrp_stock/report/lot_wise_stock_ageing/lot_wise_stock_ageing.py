# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt


from operator import itemgetter
from typing import Dict, List, Tuple, Union

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt


Filters = frappe._dict


def execute(filters: Filters = None) -> Tuple:
	to_date = filters["to_date"]
	columns = get_columns(filters)

	item_details = FIFOSlots(filters).generate()
	data = format_report_data(filters, item_details, to_date)

	chart_data = get_chart_data(data, filters)

	return columns, data, None, chart_data


def format_report_data(filters: Filters, item_details: Dict, to_date: str) -> List[Dict]:
	"Returns lot-grouped rows with indented per-rate split-up children."
	_func = itemgetter(1)
	data = []

	precision = cint(frappe.db.get_single_value("System Settings", "float_precision", cache=True))

	for key, item_dict in item_details.items():
		if not flt(item_dict.get("total_qty"), precision):
			continue

		details = item_dict["details"]

		fifo_queue = sorted(filter(_func, item_dict["fifo_queue"]), key=_func)

		if not fifo_queue:
			continue

		average_age = get_average_age(fifo_queue, to_date)
		earliest_age = date_diff(to_date, fifo_queue[0][1])
		latest_age = date_diff(to_date, fifo_queue[-1][1])
		range1, range2, range3, above_range3 = get_range_age(filters, fifo_queue, to_date, item_dict)

		total_qty = flt(item_dict.get("total_qty"), precision)
		total_value = flt(sum(flt(slot[0]) * flt(slot[2] if len(slot) > 2 else 0) for slot in fifo_queue), precision)

		parent_row = {
			"item": details.name,
			"item_name": details.item_name,
			"item_group": details.item_group,
			"brand": details.brand,
			"lot": details.lot,
		}

		if filters.get("show_warehouse_wise_stock"):
			parent_row["warehouse"] = details.warehouse

		parent_row.update(
			{
				"qty": total_qty,
				"average_age": average_age,
				"range1": range1,
				"range2": range2,
				"range3": range3,
				"above_range3": above_range3,
				"earliest": earliest_age,
				"latest": latest_age,
				"rate": flt(total_value / total_qty, precision) if total_qty else 0.0,
				"total_value": total_value,
				"stock_uom": details.stock_uom,
				"indent": 0,
			}
		)

		data.append(parent_row)

		# Per-rate split-up child rows
		rate_groups = {}
		for slot in fifo_queue:
			slot_qty = flt(slot[0])
			slot_rate = flt(slot[2] if len(slot) > 2 else 0)
			slot_date = slot[1]
			bucket = rate_groups.setdefault(slot_rate, {"qty": 0.0, "earliest_date": slot_date, "latest_date": slot_date})
			bucket["qty"] += slot_qty
			if slot_date < bucket["earliest_date"]:
				bucket["earliest_date"] = slot_date
			if slot_date > bucket["latest_date"]:
				bucket["latest_date"] = slot_date

		for slot_rate in sorted(rate_groups.keys()):
			bucket = rate_groups[slot_rate]
			child_qty = flt(bucket["qty"], precision)
			child_value = flt(child_qty * slot_rate, precision)
			child_row = {
				"item": "",
				"item_name": "",
				"item_group": "",
				"brand": "",
				"lot": "",
				"qty": child_qty,
				"earliest": date_diff(to_date, bucket["earliest_date"]),
				"latest": date_diff(to_date, bucket["latest_date"]),
				"rate": slot_rate,
				"total_value": child_value,
				"stock_uom": details.stock_uom,
				"indent": 1,
			}
			if filters.get("show_warehouse_wise_stock"):
				child_row["warehouse"] = ""
			data.append(child_row)

	return data


def get_average_age(fifo_queue: List, to_date: str) -> float:
	batch_age = age_qty = total_qty = 0.0
	for batch in fifo_queue:
		batch_age = date_diff(to_date, batch[1])

		if isinstance(batch[0], (int, float)):
			age_qty += batch_age * batch[0]
			total_qty += batch[0]
		else:
			age_qty += batch_age * 1
			total_qty += 1

	return flt(age_qty / total_qty, 2) if total_qty else 0.0


def get_range_age(filters: Filters, fifo_queue: List, to_date: str, item_dict: Dict) -> Tuple:

	precision = 3

	range1 = range2 = range3 = above_range3 = 0.0

	for item in fifo_queue:
		age = date_diff(to_date, item[1])
		qty = flt(item[0])

		if age <= filters.range1:
			range1 = flt(range1 + qty, precision)
		elif age <= filters.range2:
			range2 = flt(range2 + qty, precision)
		elif age <= filters.range3:
			range3 = flt(range3 + qty, precision)
		else:
			above_range3 = flt(above_range3 + qty, precision)

	return range1, range2, range3, above_range3


def get_columns(filters: Filters) -> List[Dict]:
	range_columns = []
	setup_ageing_columns(filters, range_columns)
	columns = [
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 100,
		},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 140},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 100,
		},
		{
			"label": _("Brand"),
			"fieldname": "brand",
			"fieldtype": "Link",
			"options": "Brand",
			"width": 100,
		},
		{
			"label": _("Lot"),
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"width": 120,
		},
	]

	if filters.get("show_warehouse_wise_stock"):
		columns += [
			{
				"label": _("Warehouse"),
				"fieldname": "warehouse",
				"fieldtype": "Link",
				"options": "Supplier",
				"width": 100,
			}
		]

	columns.extend(
		[
			{"label": _("Available Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 110},
			{"label": _("Average Age"), "fieldname": "average_age", "fieldtype": "Float", "width": 100},
		]
	)
	columns.extend(range_columns)
	columns.extend(
		[
			{"label": _("Earliest"), "fieldname": "earliest", "fieldtype": "Int", "width": 80},
			{"label": _("Latest"), "fieldname": "latest", "fieldtype": "Int", "width": 80},
			{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
			{"label": _("Total Value"), "fieldname": "total_value", "fieldtype": "Currency", "width": 130},
			{"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
		]
	)

	return columns


def get_chart_data(data: List, filters: Filters) -> Dict:
	if not data:
		return []

	labels, datapoints = [], []

	if filters.get("show_warehouse_wise_stock"):
		return {}

	parents = [row for row in data if row.get("indent", 0) == 0]
	parents.sort(key=lambda row: row.get("average_age") or 0, reverse=True)

	if len(parents) > 10:
		parents = parents[:10]

	for row in parents:
		labels.append(f"{row['item']} / {row.get('lot') or ''}")
		datapoints.append(row.get("average_age") or 0)

	return {
		"data": {"labels": labels, "datasets": [{"name": _("Average Age"), "values": datapoints}]},
		"type": "bar",
	}


def setup_ageing_columns(filters: Filters, range_columns: List):
	ranges = [
		f"0 - {filters['range1']}",
		f"{cint(filters['range1']) + 1} - {cint(filters['range2'])}",
		f"{cint(filters['range2']) + 1} - {cint(filters['range3'])}",
		_("{0} - Above").format(cint(filters["range3"]) + 1),
	]
	for i, label in enumerate(ranges):
		fieldname = "range" + str(i + 1)
		add_column(range_columns, label=_("Age ({0})").format(label), fieldname=fieldname)


def add_column(
	range_columns: List, label: str, fieldname: str, fieldtype: str = "Float", width: int = 140
):
	range_columns.append(dict(label=label, fieldname=fieldname, fieldtype=fieldtype, width=width))


class FIFOSlots:
	"""FIFO computed slots of inwarded stock per (item, lot), carrying rate."""

	def __init__(self, filters: Dict = None, sle: List = None):
		self.item_details = {}
		self.transferred_item_details = {}
		self.filters = filters
		self.sle = sle

	def generate(self) -> Dict:
		if self.sle is None:
			self.sle = self.__get_stock_ledger_entries()

		for d in self.sle:
			key, fifo_queue, transferred_item_key = self.__init_key_stores(d)

			if d.voucher_type == "Stock Reconciliation":
				prev_balance_qty = self.item_details[key].get("qty_after_transaction", 0)
				d.qty = flt(d.qty_after_transaction) - flt(prev_balance_qty)

			if d.qty > 0:
				self.__compute_incoming_stock(d, fifo_queue, transferred_item_key)
			else:
				self.__compute_outgoing_stock(d, fifo_queue, transferred_item_key)

			self.__update_balances(d, key)

		# Aggregate (item, warehouse, lot) -> (item, lot) unless warehouse-wise requested
		if not self.filters.get("show_warehouse_wise_stock"):
			self.item_details = self.__aggregate_details_by_item_lot(self.item_details)

		return self.item_details

	def __init_key_stores(self, row: Dict) -> Tuple:
		key = (row.name, row.warehouse, row.lot)
		self.item_details.setdefault(key, {"details": row, "fifo_queue": []})
		fifo_queue = self.item_details[key]["fifo_queue"]

		transferred_item_key = (row.voucher_no, row.name, row.warehouse, row.lot)
		self.transferred_item_details.setdefault(transferred_item_key, [])

		return key, fifo_queue, transferred_item_key

	def __compute_incoming_stock(self, row: Dict, fifo_queue: List, transfer_key: Tuple):
		transfer_data = self.transferred_item_details.get(transfer_key)
		incoming_rate = self.__incoming_rate(row)

		if transfer_data:
			self.__adjust_incoming_transfer_qty(transfer_data, fifo_queue, row, incoming_rate)
		else:
			if fifo_queue and flt(fifo_queue[0][0]) <= 0:
				fifo_queue[0][0] += flt(row.qty)
				fifo_queue[0][1] = row.posting_date
				fifo_queue[0][2] = incoming_rate
			else:
				fifo_queue.append([flt(row.qty), row.posting_date, incoming_rate])

	def __compute_outgoing_stock(self, row: Dict, fifo_queue: List, transfer_key: Tuple):
		qty_to_pop = abs(row.qty)
		while qty_to_pop:
			slot = fifo_queue[0] if fifo_queue else [0, None, 0]
			if 0 < flt(slot[0]) <= qty_to_pop:
				qty_to_pop -= flt(slot[0])
				self.transferred_item_details[transfer_key].append(fifo_queue.pop(0))
			elif not fifo_queue:
				fifo_queue.append([-(qty_to_pop), row.posting_date, 0])
				self.transferred_item_details[transfer_key].append([qty_to_pop, row.posting_date, 0])
				qty_to_pop = 0
			else:
				slot[0] = flt(slot[0]) - qty_to_pop
				self.transferred_item_details[transfer_key].append([qty_to_pop, slot[1], slot[2] if len(slot) > 2 else 0])
				qty_to_pop = 0

	def __adjust_incoming_transfer_qty(self, transfer_data: Dict, fifo_queue: List, row: Dict, incoming_rate: float):
		transfer_qty_to_pop = flt(row.qty)

		def add_to_fifo_queue(slot):
			# Ensure slot has 3 elements
			if len(slot) == 2:
				slot = [slot[0], slot[1], incoming_rate]
			if fifo_queue and flt(fifo_queue[0][0]) <= 0:
				fifo_queue[0][0] += flt(slot[0])
				fifo_queue[0][1] = slot[1]
				fifo_queue[0][2] = slot[2]
			else:
				fifo_queue.append(slot)

		while transfer_qty_to_pop:
			if transfer_data and 0 < transfer_data[0][0] <= transfer_qty_to_pop:
				transfer_qty_to_pop -= transfer_data[0][0]
				add_to_fifo_queue(transfer_data.pop(0))
			elif not transfer_data:
				add_to_fifo_queue([transfer_qty_to_pop, row.posting_date, incoming_rate])
				transfer_qty_to_pop = 0
			else:
				transfer_data[0][0] -= transfer_qty_to_pop
				rate = transfer_data[0][2] if len(transfer_data[0]) > 2 else incoming_rate
				add_to_fifo_queue([transfer_qty_to_pop, transfer_data[0][1], rate])
				transfer_qty_to_pop = 0

	def __incoming_rate(self, row: Dict) -> float:
		# Prefer explicit rate; fall back to valuation_rate; finally derived from stock_value_difference.
		if row.get("rate"):
			return flt(row.get("rate"))
		if row.get("valuation_rate"):
			return flt(row.get("valuation_rate"))
		if row.get("stock_value_difference") and flt(row.qty):
			return flt(row.get("stock_value_difference")) / flt(row.qty)
		return 0.0

	def __update_balances(self, row: Dict, key: Union[Tuple, str]):
		self.item_details[key]["qty_after_transaction"] = row.qty_after_transaction

		if "total_qty" not in self.item_details[key]:
			self.item_details[key]["total_qty"] = row.qty
		else:
			self.item_details[key]["total_qty"] += row.qty

	def __aggregate_details_by_item_lot(self, wh_wise_data: Dict) -> Dict:
		"Aggregate (item, warehouse, lot) into (item, lot)."
		aggregated = {}
		for key, row in wh_wise_data.items():
			item, _warehouse, lot = key
			agg_key = (item, lot)
			if not aggregated.get(agg_key):
				aggregated.setdefault(
					agg_key,
					{"details": frappe._dict(), "fifo_queue": [], "qty_after_transaction": 0.0, "total_qty": 0.0},
				)
			bucket = aggregated[agg_key]
			bucket["details"].update(row["details"])
			bucket["fifo_queue"].extend(row["fifo_queue"])
			bucket["qty_after_transaction"] += flt(row["qty_after_transaction"])
			bucket["total_qty"] += flt(row["total_qty"])

		return aggregated

	def __get_stock_ledger_entries(self) -> List[Dict]:
		sle = frappe.qb.DocType("Stock Ledger Entry")
		item = self.__get_item_query()

		sle_query = (
			frappe.qb.from_(sle)
			.from_(item)
			.select(
				item.name,
				item.item_name,
				item.item_group,
				item.brand,
				item.stock_uom,
				sle.qty,
				sle.posting_date,
				sle.voucher_type,
				sle.voucher_no,
				sle.lot,
				sle.qty_after_transaction,
				sle.warehouse,
				sle.rate,
				sle.valuation_rate,
				sle.stock_value_difference,
			)
			.where(
				(sle.item == item.name)
				& (sle.posting_date <= self.filters.get("to_date"))
				& (sle.is_cancelled != 1)
			)
		)
		if self.filters.get("warehouse"):
			sle_query = sle_query.where(sle.warehouse == self.filters.get("warehouse"))

		if self.filters.get("lot"):
			sle_query = sle_query.where(sle.lot == self.filters.get("lot"))

		sle_query = sle_query.orderby(sle.posting_date, sle.posting_time, sle.creation, sle.qty)

		return sle_query.run(as_dict=True)

	def __get_item_query(self) -> str:
		item_table = frappe.qb.DocType("Item")
		item_variant_table = frappe.qb.DocType("Item Variant")

		item = frappe.qb.from_(item_variant_table).from_(item_table).select(
			item_variant_table.name,
			item_table.name.as_('item_name'),
			item_table.default_unit_of_measure.as_('stock_uom'),
			item_table.brand,
			item_table.item_group
		)
		item = item.where(item_table.name == item_variant_table.item)

		if self.filters.get("parent_item"):
			item = item.where(item_table.name == self.filters.get("parent_item"))

		if self.filters.get("item"):
			item = item.where(item_variant_table.name == self.filters.get("item"))

		if self.filters.get("brand"):
			item = item.where(item_table.brand == self.filters.get("brand"))

		return item
