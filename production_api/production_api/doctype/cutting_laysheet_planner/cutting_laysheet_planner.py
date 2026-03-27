# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document

class CuttingLaysheetPlanner(Document):
	pass

@frappe.whitelist()
def optimize(doc_name):
	from production_api.production_api.utils.lay_optimizer import optimize_all_strategies

	doc = frappe.get_doc("Cutting Laysheet Planner", doc_name)

	if not doc.order_details or len(doc.order_details) == 0:
		frappe.throw("Please add order details (size and quantity) before optimizing.")

	if not doc.max_plies or not doc.max_pieces:
		frappe.throw("Please set Maximum Plies and Maximum Pieces Per Marker.")

	order = {}
	for row in doc.order_details:
		order[row.size] = row.qty

	tolerance = doc.tolerance_pct or 3.0

	results, failed = optimize_all_strategies(
		order=order,
		max_plies=doc.max_plies,
		max_pieces=doc.max_pieces,
		tolerance_pct=tolerance,
		max_lays=doc.max_lays or 8,
		tubular=bool(doc.tubular),
	)

	if not results:
		frappe.throw("No feasible plan found for any strategy. Try adjusting tolerance or max lays.")

	# Clear existing lay details
	doc.lay_details = []

	# Populate lay details for ALL strategies
	for result in results:
		strategy = result["strategy"]
		for lay in result["lays"]:
			doc.append("lay_details", {
				"strategy": strategy,
				"lay_no": lay["lay_no"],
				"plies": lay["plies"],
				"ratio": json.dumps(lay["ratio"]),
				"pieces_per_ply": lay["pieces_per_ply"],
				"total_pieces": lay["total_pieces"],
				"cut_per_size": json.dumps(lay["cut_per_size"]),
			})

	# Use the first (best) strategy for the document summary
	best = results[0]
	summary = best["summary"]
	doc.total_lays = summary["total_lays"]
	doc.total_cut = summary["total_cut"]
	doc.total_order = summary["total_order"]
	doc.overcut = summary["overcut"]
	doc.overcut_pct = summary["overcut_pct"]
	doc.undercut = summary["undercut"]
	doc.undercut_pct = summary["undercut_pct"]

	# Build per-size HTML for the selected strategy
	doc.per_size_html = _build_per_size_html(best["per_size"])

	# Build all-strategies comparison HTML
	doc.all_strategies_html = _build_comparison_html(results, failed)

	# Store full results JSON
	doc.result_json = json.dumps({"results": results, "failed": failed})

	doc.save()
	frappe.msgprint(
		f"Optimization complete: {len(results)} strategies found. Best: {best['strategy']} ({summary['total_lays']} lays)",
		indicator="green", alert=True
	)
	return doc.name


@frappe.whitelist()
def select_strategy(doc_name, strategy):
	doc = frappe.get_doc("Cutting Laysheet Planner", doc_name)

	if not doc.result_json:
		frappe.throw("No optimization results found. Please run Optimize first.")

	stored = json.loads(doc.result_json)
	results = stored.get("results", [])
	failed = stored.get("failed", [])
	
	selected = None
	# First check in results
	for r in results:
		if r["strategy"] == strategy:
			selected = r
			break
	
	# If not found, check if it's a deduplicated strategy in 'failed'
	if not selected:
		for f in failed:
			if f["strategy"] == strategy and f.get("deduplicated"):
				# Resolve to the original plan
				same_as = f.get("same_as")
				selected = next((r for r in results if r["strategy"] == same_as), None)
				break

	if not selected:
		frappe.throw(f"Strategy '{strategy}' not found in results.")

	doc.selected_strategy = strategy
	summary = selected["summary"]
	doc.total_lays = summary["total_lays"]
	doc.total_cut = summary["total_cut"]
	doc.total_order = summary["total_order"]
	doc.overcut = summary["overcut"]
	doc.overcut_pct = summary["overcut_pct"]
	doc.undercut = summary["undercut"]
	doc.undercut_pct = summary["undercut_pct"]
	doc.per_size_html = _build_per_size_html(selected["per_size"])

	doc.save()
	return doc.name


def _build_per_size_html(per_size):
	html = '<table class="table table-bordered table-condensed" style="max-width:600px">'
	html += '<thead><tr><th>Size</th><th>Order</th><th>Cut</th><th>Diff</th><th>Deviation %</th></tr></thead>'
	html += '<tbody>'
	for size, data in per_size.items():
		diff = data["diff"]
		color = "red" if diff < 0 else ("green" if diff > 0 else "")
		style = f' style="color:{color}"' if color else ""
		html += f'<tr><td>{size}</td><td>{data["order"]}</td><td>{data["cut"]}</td>'
		html += f'<td{style}>{diff:+d}</td><td>{data["pct"]}%</td></tr>'
	html += '</tbody></table>'
	return html


def _build_comparison_html(results, failed=None):
	html = '<table class="table table-bordered table-condensed">'
	html += '<thead><tr>'
	html += '<th>Strategy</th><th>Description</th><th>Lays</th><th>Markers</th>'
	html += '<th>Avg Density</th><th>Overcut</th><th>Undercut</th><th>Action</th>'
	html += '</tr></thead><tbody>'
	for r in results:
		s = r["summary"]
		strategy = r["strategy"]
		desc = r.get("strategy_description", "")
		html += f'<tr>'
		html += f'<td><strong>{strategy}</strong></td>'
		html += f'<td>{desc}</td>'
		html += f'<td>{s["total_lays"]}</td>'
		html += f'<td>{s["unique_markers"]}</td>'
		html += f'<td>{s["avg_pieces_per_ply"]}/ply</td>'
		html += f'<td>{s["overcut"]} ({s["overcut_pct"]}%)</td>'
		html += f'<td>{s["undercut"]} ({s["undercut_pct"]}%)</td>'
		html += f'<td><button class="btn btn-xs btn-default select-strategy-btn" data-strategy="{strategy}">Select</button></td>'
		html += f'</tr>'
	if failed:
		for f in failed:
			strategy = f["strategy"]
			desc = f.get("strategy_description", "")
			if f.get("deduplicated"):
				same_as = f.get("same_as", "?")
				html += f'<tr class="text-muted">'
				html += f'<td>{strategy}</td>'
				html += f'<td>{desc}</td>'
				html += f'<td colspan="5"><em>Same plan as {same_as}</em></td>'
				html += f'<td></td>'
				html += f'</tr>'
			else:
				error = f.get("error", "No feasible plan")
				html += f'<tr class="text-muted">'
				html += f'<td>{strategy}</td>'
				html += f'<td>{desc}</td>'
				html += f'<td colspan="5"><em>{error}</em></td>'
				html += f'<td></td>'
				html += f'</tr>'
	html += '</tbody></table>'
	return html
