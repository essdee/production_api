import re

import frappe


TRANSFER_BLOCK = re.compile(
	r"(?ms)^\[\d{2}-\d{2}-\d{4}\] Quantity Transfer (?:Requested|Approved)\b.*?"
	r"(?=^\[\d{2}-\d{2}-\d{4}\] |\Z)"
)


def remove_quantity_transfer_comment_blocks(comment_log):
	cleaned = TRANSFER_BLOCK.sub("", (comment_log or "").replace("\r\n", "\n"))
	cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
	return cleaned or None


def execute():
	rows = frappe.db.sql(
		"""
		SELECT name, comment_log
		FROM `tabProduction Order`
		WHERE comment_log LIKE '%%Quantity Transfer Requested%%'
		   OR comment_log LIKE '%%Quantity Transfer Approved%%'
		""",
		as_dict=True,
	)
	for row in rows:
		cleaned = remove_quantity_transfer_comment_blocks(row.comment_log)
		if cleaned != row.comment_log:
			frappe.db.set_value(
				"Production Order",
				row.name,
				"comment_log",
				cleaned,
				update_modified=False,
			)
