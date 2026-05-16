import frappe
from frappe.utils import flt


DEFAULT_PIECE_WEIGHT_TOLERANCE = 0.003


def execute():
	if not frappe.db.table_exists("Cutting Plan"):
		return
	if not frappe.db.has_column("Cutting Plan", "piece_weight_tolerance"):
		return

	tolerance = flt(frappe.db.get_single_value("MRP Settings", "piece_weight_tolerance")) or DEFAULT_PIECE_WEIGHT_TOLERANCE
	frappe.db.sql(
		"""
		UPDATE `tabCutting Plan`
		SET piece_weight_tolerance = %s
		WHERE IFNULL(piece_weight_tolerance, 0) = 0
		""",
		(tolerance,),
	)
