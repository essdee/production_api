import json

import frappe

from production_api.production_api.doctype.cutting_laysheet_planner.cutting_laysheet_planner import (
    _get_optimizer_inputs,
)


def execute():
    if not frappe.db.table_exists("Cutting Laysheet Planner"):
        return

    planners = frappe.get_all(
        "Cutting Laysheet Planner",
        fields=["name", "result_json", "selected_strategy", "modified"],
    )
    for planner in planners:
        values = {
            "optimization_status": (
                "Completed" if planner.result_json else "Not Started"
            ),
        }

        if planner.result_json:
            values["optimization_completed_on"] = planner.modified
            if not planner.selected_strategy:
                values["selected_strategy"] = _first_strategy(
                    planner.result_json
                )

        try:
            doc = frappe.get_doc("Cutting Laysheet Planner", planner.name)
            values["optimization_input_json"] = json.dumps(
                _get_optimizer_inputs(doc),
                separators=(",", ":"),
                ensure_ascii=False,
            )
        except Exception:
            # Legacy malformed inputs remain viewable and can be corrected by a user.
            values["optimization_input_json"] = None

        frappe.db.set_value(
            "Cutting Laysheet Planner",
            planner.name,
            values,
            update_modified=False,
        )


def _first_strategy(result_json):
    try:
        results = json.loads(result_json).get("results", [])
        return results[0].get("strategy") if results else None
    except (AttributeError, TypeError, ValueError):
        return None
