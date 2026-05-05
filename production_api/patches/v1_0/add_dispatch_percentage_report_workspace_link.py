import frappe


REPORT_NAME = "Dispatch Percentage Report"
WORKSPACE_NAME = "Manufacturing"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	report_link = _get_report_link(workspace)

	if not report_link:
		report_link = workspace.append(
			"links",
			{
				"hidden": 0,
				"is_query_report": 1,
				"label": REPORT_NAME,
				"link_count": 0,
				"link_to": REPORT_NAME,
				"link_type": "Report",
				"onboard": 0,
				"type": "Link",
			},
		)
		_move_after(workspace.links, report_link, "Finishing Plan Report")

	_update_reports_card_count(workspace)
	workspace.flags.ignore_permissions = True
	workspace.save()


def _get_report_link(workspace):
	for link in workspace.links:
		if link.label == REPORT_NAME and link.link_to == REPORT_NAME:
			return link

	return None


def _move_after(links, row, label):
	links.remove(row)
	insert_at = len(links)

	for index, link in enumerate(links):
		if link.label == label:
			insert_at = index + 1
			break

	links.insert(insert_at, row)


def _update_reports_card_count(workspace):
	reports_card = None
	report_count = 0

	for link in workspace.links:
		if link.type == "Card Break":
			if reports_card:
				break
			if link.label == "Reports":
				reports_card = link
			continue

		if reports_card and not link.hidden:
			report_count += 1

	if reports_card:
		reports_card.link_count = report_count
