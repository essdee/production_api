"""Repair negative stock valuations and the transaction rates that propagated them.

Root causes covered by this patch:

1. FIFO rounding residue: the stored stock value is currency-rounded while the FIFO
   queue retains more precision. Applying the next unrounded queue delta to the rounded
   value can leave -0.01 (or a smaller residue), which becomes a negative valuation rate
   when divided by a small remaining quantity.
2. Corrupt/mismatched FIFO history: a historical queue can disagree with
   ``qty_after_transaction``. Reposting only from the first negative row preserves that
   bad starting state, so this patch rebuilds each affected key from its first active SLE.
3. Propagated negative transaction rate: transfer/conversion code historically copied a
   negative latest valuation into ``Stock Ledger Entry.rate``. The patch reconstructs the
   transfer rate from the source SLE's actual value movement before replaying the ledgers.

The runtime fixes must be deployed with this patch. Reposting with the old FIFO value
calculation would recreate the rounding residue.

Manual audit (no writes):

    bench --site <site> execute \
        production_api.patches.v1_0.repair_negative_stock_valuations.run

Manual live run (normally unnecessary because ``execute`` runs during migrate):

    bench --site <site> execute \
        production_api.patches.v1_0.repair_negative_stock_valuations.run \
        --kwargs "{'dry_run': False, 'commit': True}"
"""

import json
from collections import Counter

import frappe
from frappe.utils import flt

from production_api.mrp_stock.stock_ledger import update_entries_after


ZERO_TOLERANCE = 1e-9
QUEUE_QTY_TOLERANCE = 1e-6


def execute():
	run(dry_run=False, commit=True)


def run(dry_run=True, item=None, limit=None, commit=False, commit_every=10, verbose=True):
	"""Audit or repair all active SLEs containing a negative valuation/rate.

	Args:
		item: optional Item Variant restriction for a controlled verification.
		limit: optional number of affected item/warehouse/lot/type timelines.
		dry_run: audit only; never updates or reposts.
		commit: commit progress when running manually or from ``execute``.
		commit_every: live replay commit cadence. Zero disables intermediate commits.
	"""
	negative_entries = _get_negative_valuation_entries(item=item)
	negative_rate_rows = _get_negative_rate_entries(item=item)
	first_negative_by_key = _first_entry_by_key(negative_entries)
	cause_counts = Counter(_classify_negative(row) for row in first_negative_by_key.values())

	affected_keys = set(first_negative_by_key)
	affected_keys.update(_key(row) for row in negative_rate_rows)
	affected_keys = sorted(
		affected_keys,
		key=lambda key: _get_timeline_start(key).get("posting_datetime") or "9999-12-31",
	)
	if limit:
		affected_keys = affected_keys[: int(limit)]

	stats = frappe._dict(
		negative_entries=len(negative_entries),
		negative_rate_entries=len(negative_rate_rows),
		affected_keys=len(affected_keys),
		causes=dict(cause_counts),
		rates_repaired=0,
		keys_reposted=0,
		failed=0,
		failures=[],
		remaining_negative_valuations=len(negative_entries),
		remaining_negative_rates=len(negative_rate_rows),
	)
	_mode = "DRY RUN" if dry_run else "LIVE"
	if verbose:
		print(
			f"[{_mode}] negative valuation repair: entries={stats.negative_entries}, "
			f"negative_rates={stats.negative_rate_entries}, keys={stats.affected_keys}, "
			f"causes={stats.causes}"
		)

	if dry_run or not affected_keys:
		return stats

	target_keys = set(affected_keys)
	for row in negative_rate_rows:
		if _key(row) not in target_keys:
			continue
		new_rate = _get_replacement_transaction_rate(row)
		if new_rate < 0:
			raise ValueError(f"Replacement rate remained negative for {row.name}: {new_rate}")
		frappe.db.set_value(
			"Stock Ledger Entry", row.name, "rate", new_rate, update_modified=False
		)
		stats.rates_repaired += 1

	if commit:
		frappe.db.commit()

	for index, key in enumerate(affected_keys, start=1):
		savepoint = f"negative_valuation_{index}"
		frappe.db.savepoint(savepoint)
		try:
			_repost_full_timeline(key)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			stats.failed += 1
			stats.failures.append({"key": key, "error": str(exc)})
			if verbose:
				print(f"  [{index}/{len(affected_keys)}] FAILED {_format_key(key)}: {exc}")
		else:
			stats.keys_reposted += 1
			if verbose and (index == 1 or index % 10 == 0 or index == len(affected_keys)):
				print(f"  reposted {index}/{len(affected_keys)}: {_format_key(key)}")

		if commit and commit_every and index % int(commit_every) == 0:
			frappe.db.commit()

	if commit:
		frappe.db.commit()

	stats.remaining_negative_valuations = _count_negative_for_keys(
		affected_keys, "valuation_rate"
	)
	stats.remaining_negative_rates = _count_negative_for_keys(affected_keys, "rate")
	if verbose:
		print(
			f"[{_mode}] done: rates_repaired={stats.rates_repaired}, "
			f"keys_reposted={stats.keys_reposted}, failed={stats.failed}, "
			f"remaining_valuations={stats.remaining_negative_valuations}, "
			f"remaining_rates={stats.remaining_negative_rates}"
		)

	if stats.failed or stats.remaining_negative_valuations or stats.remaining_negative_rates:
		frappe.throw(
			"Negative valuation repair did not finish cleanly: "
			f"failed={stats.failed}, "
			f"remaining valuations={stats.remaining_negative_valuations}, "
			f"remaining rates={stats.remaining_negative_rates}."
		)

	return stats


def _get_negative_valuation_entries(item=None):
	conditions = ["is_cancelled = 0", "valuation_rate < 0"]
	values = {}
	if item:
		conditions.append("item = %(item)s")
		values["item"] = item
	return frappe.db.sql(
		f"""
			SELECT name, item, warehouse, lot, received_type, posting_date,
				posting_time, posting_datetime, creation, voucher_type, voucher_no,
				voucher_detail_no, qty, qty_after_transaction, rate, outgoing_rate,
				valuation_rate, stock_value, stock_value_difference, stock_queue
			FROM `tabStock Ledger Entry`
			WHERE {' AND '.join(conditions)}
			ORDER BY posting_datetime, creation
		""",
		values,
		as_dict=True,
	)


def _get_negative_rate_entries(item=None):
	conditions = ["is_cancelled = 0", "rate < 0"]
	values = {}
	if item:
		conditions.append("item = %(item)s")
		values["item"] = item
	return frappe.db.sql(
		f"""
			SELECT name, item, warehouse, lot, received_type, posting_date,
				posting_time, posting_datetime, creation, voucher_type, voucher_no,
				voucher_detail_no, qty, qty_after_transaction, rate, outgoing_rate,
				valuation_rate, stock_value, stock_value_difference, stock_queue
			FROM `tabStock Ledger Entry`
			WHERE {' AND '.join(conditions)}
			ORDER BY posting_datetime, creation
		""",
		values,
		as_dict=True,
	)


def _first_entry_by_key(entries):
	result = {}
	for row in entries:
		result.setdefault(_key(row), row)
	return result


def _classify_negative(row):
	"""Classify the first negative row of a stock timeline for audit output."""
	queue = _parse_queue(row.stock_queue)
	queue_qty = sum(flt(layer[0]) for layer in queue)
	if flt(row.qty) > 0 and flt(row.rate) < 0:
		return "negative_incoming_transaction_rate"
	if any(flt(layer[0]) < -ZERO_TOLERANCE or flt(layer[1]) < -ZERO_TOLERANCE for layer in queue):
		return "negative_fifo_layer"
	if abs(queue_qty - flt(row.qty_after_transaction)) > QUEUE_QTY_TOLERANCE:
		return "fifo_queue_quantity_mismatch"
	# With a valid, non-negative FIFO queue and matching quantity, a negative
	# valuation can only be the rounded-stock-value versus precise-queue residue.
	# The stored stock_value is often already rounded back to 0.00, while the
	# valuation_rate still contains the pre-round negative residue.
	return "fifo_currency_rounding_residual"


def _parse_queue(value):
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except (TypeError, ValueError):
			return []
	return value if isinstance(value, list) else []


def _get_replacement_transaction_rate(row):
	"""Return the non-negative value represented by a corrupt negative SLE rate.

	For an outgoing row, the actual value consumed is already recorded in
	``stock_value_difference``. For an incoming transfer/conversion row, allocate the
	value consumed by its same-voucher-detail outgoing sibling(s) over all incoming qty.
	This preserves the historical transaction's actual stock value instead of guessing
	from an unrelated current price.
	"""
	siblings = frappe.get_all(
		"Stock Ledger Entry",
		filters={
			"voucher_type": row.voucher_type,
			"voucher_no": row.voucher_no,
			"voucher_detail_no": row.voucher_detail_no,
			"is_cancelled": 0,
		},
		fields=["name", "qty", "stock_value_difference"],
	)
	if flt(row.qty) > 0:
		incoming_qty = sum(max(flt(sibling.qty), 0) for sibling in siblings)
		outgoing_value = sum(
			max(-flt(sibling.stock_value_difference), 0)
			for sibling in siblings
			if flt(sibling.qty) < 0
		)
		if incoming_qty:
			return outgoing_value / incoming_qty

	if flt(row.qty) < 0:
		return max(-flt(row.stock_value_difference) / abs(flt(row.qty)), 0)

	return 0.0


def _repost_full_timeline(key):
	start = _get_timeline_start(key)
	if not start:
		return
	update_entries_after(
		{
			"item": key[0],
			"warehouse": key[1],
			"lot": key[2],
			"received_type": key[3],
			"posting_date": start.posting_date,
			"posting_time": start.posting_time,
		},
		verbose=0,
	)


def _get_timeline_start(key):
	return frappe.db.get_value(
		"Stock Ledger Entry",
		{
			"item": key[0],
			"warehouse": key[1],
			"lot": key[2],
			"received_type": key[3],
			"is_cancelled": 0,
		},
		["posting_date", "posting_time", "posting_datetime"],
		as_dict=True,
		order_by="posting_datetime asc, creation asc",
	)


def _count_negative_for_keys(keys, fieldname):
	count = 0
	for key in keys:
		count += frappe.db.count(
			"Stock Ledger Entry",
			filters={
				"item": key[0],
				"warehouse": key[1],
				"lot": key[2],
				"received_type": key[3],
				"is_cancelled": 0,
				fieldname: ["<", 0],
			},
		)
	return count


def _key(row):
	return (row.item, row.warehouse, row.lot, row.received_type)


def _format_key(key):
	return " / ".join(str(value) for value in key)
