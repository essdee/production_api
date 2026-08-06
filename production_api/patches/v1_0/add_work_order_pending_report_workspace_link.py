import frappe


REPORT_NAME = "Work Order Pending Report"
REPORT_LABEL = "WO Pending Report"
WORKSPACE_NAME = "Manufacturing"
LEGACY_PAGE = "work-order-pending-report"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	report_link = None

	for link in list(workspace.links):
		if link.link_type == "Page" and link.link_to == LEGACY_PAGE:
			workspace.links.remove(link)
		elif link.link_type == "Report" and link.link_to == REPORT_NAME:
			if report_link:
				workspace.links.remove(link)
			else:
				report_link = link

	if not report_link:
		report_link = workspace.append("links", {})

	report_link.update(
		{
			"hidden": 0,
			"is_query_report": 1,
			"label": REPORT_LABEL,
			"link_count": 0,
			"link_to": REPORT_NAME,
			"link_type": "Report",
			"onboard": 0,
			"type": "Link",
		}
	)
	_move_after(workspace.links, report_link, "Process Pending Report")
	_update_reports_card_count(workspace)
	workspace.flags.ignore_permissions = True
	workspace.save()


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
