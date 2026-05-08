import frappe


REPORT_NAME = "Dispatch Percentage Report"
WORKSPACE_NAME = "Manufacturing"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	report_link = _get_or_create_report_link(workspace)
	ordered_names = _get_ordered_link_names(workspace, report_link.name)
	link_by_name = {link.name: link for link in workspace.links}

	for idx, link_name in enumerate(ordered_names, start=1):
		frappe.db.set_value("Workspace Link", link_name, "idx", idx, update_modified=False)

	reports_card = _get_reports_card(link_by_name, ordered_names)
	if reports_card:
		frappe.db.set_value(
			"Workspace Link",
			reports_card.name,
			"link_count",
			_get_reports_card_count(link_by_name, ordered_names),
			update_modified=False,
		)


def _get_or_create_report_link(workspace):
	for link in workspace.links:
		if link.label == REPORT_NAME and link.link_to == REPORT_NAME:
			return link

	link = workspace.append(
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
	workspace.flags.ignore_permissions = True
	workspace.save()
	workspace.reload()

	return next(link for link in workspace.links if link.label == REPORT_NAME and link.link_to == REPORT_NAME)


def _get_ordered_link_names(workspace, report_link_name):
	ordered_names = [link.name for link in workspace.links if link.name != report_link_name]
	insert_at = len(ordered_names)

	for index, link in enumerate([link for link in workspace.links if link.name != report_link_name]):
		if link.label == "Finishing Plan Report":
			insert_at = index + 1
			break

	ordered_names.insert(insert_at, report_link_name)
	return ordered_names


def _get_reports_card(link_by_name, ordered_names):
	for link_name in ordered_names:
		link = link_by_name[link_name]
		if link.type == "Card Break" and link.label == "Reports":
			return link

	return None


def _get_reports_card_count(link_by_name, ordered_names):
	reports_started = False
	report_count = 0

	for link_name in ordered_names:
		link = link_by_name[link_name]
		if link.type == "Card Break":
			if reports_started:
				break
			if link.label == "Reports":
				reports_started = True
			continue

		if reports_started and not link.hidden:
			report_count += 1

	return report_count
