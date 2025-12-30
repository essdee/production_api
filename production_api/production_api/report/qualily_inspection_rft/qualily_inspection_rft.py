# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	data, max_inspections = get_data(filters)
	columns = get_columns(max_inspections)
	return columns, data


def get_columns(max_inspections):
	columns = [
		{
			"label": "Against ID",
			"fieldname": "against_id",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "Supplier",
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150
		},
		{
			"label": "Lot",
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"width": 120
		},
		{
			"label": "Item",
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150
		},
		{
			"label": "Colour",
			"fieldname": "colour",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Sizes",
			"fieldname": "sizes",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "Description",
			"fieldname": "description",
			"fieldtype": "Data",
			"width": 200
		}
	]
	
	for i in range(1, max_inspections + 1):
		columns.extend([
			{
				"label": f"Inspection {i} Date",
				"fieldname": f"posting_date_{i}",
				"fieldtype": "Date",
				"width": 130
			},
			{
				"label": f"Result {i}",
				"fieldname": f"result_{i}",
				"fieldtype": "Data",
				"width": 120
			}
		])
		
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	size_subquery = """
		(SELECT GROUP_CONCAT(size ORDER BY idx SEPARATOR ', ') 
		 FROM `tabEssdee Quality Inspection Size` 
		 WHERE parent = t1.name AND selected = 1) as sizes
	"""
	
	raw_data = frappe.db.sql(f"""
		SELECT 
			t1.against_id, 
			t1.supplier, 
			t1.lot, 
			t1.item, 
			t1.description,
			t1.result, 
			t1.inspector_name, 
			t1.posting_date,
			t2.colour,
			{size_subquery}
		FROM `tabEssdee Quality Inspection` as t1 
		JOIN `tabEssdee Quality Inspection Colour` as t2 
		ON t1.name = t2.parent 
		WHERE 1=1 {conditions}
		ORDER BY 
			t1.against_id, t1.supplier, t1.lot, t1.item, t2.colour, t1.posting_date
	""", filters, as_dict=1)
	
	pivoted_data = []
	grouped_records = {}
	max_inspections = 0
	
	for row in raw_data:
		key = (row.against_id, row.supplier, row.lot, row.item, row.colour, row.sizes)
		if key not in grouped_records:
			grouped_records[key] = {
				"against_id": row.against_id,
				"supplier": row.supplier,
				"lot": row.lot,
				"item": row.item,
				"colour": row.colour,
				"sizes": row.sizes,
				"description": row.description,
				"inspections": []
			}
		
		grouped_records[key]["inspections"].append({
			"date": row.posting_date,
			"result": row.result
		})
		
		max_inspections = max(max_inspections, len(grouped_records[key]["inspections"]))
		
	for key in grouped_records:
		record = grouped_records[key]
		flat_row = {
			"against_id": record["against_id"],
			"supplier": record["supplier"],
			"lot": record["lot"],
			"item": record["item"],
			"colour": record["colour"],
			"sizes": record["sizes"],
			"description": record["description"]
		}
		
		for i, inspection in enumerate(record["inspections"]):
			idx = i + 1
			flat_row[f"posting_date_{idx}"] = inspection["date"]
			flat_row[f"result_{idx}"] = inspection["result"]
			
		pivoted_data.append(flat_row)
	
	return pivoted_data, max_inspections


def get_conditions(filters):
	conditions = " AND t1.docstatus = 1 AND t2.selected = 1"
	
	if filters.get("lot"):
		conditions += " AND t1.lot = %(lot)s"
	
	if filters.get("item"):
		conditions += " AND t1.item = %(item)s"
		
	if filters.get("supplier"):
		conditions += " AND t1.supplier = %(supplier)s"
		
	if filters.get("result"):
		conditions += " AND t1.result = %(result)s"
		
	if filters.get("from_date"):
		conditions += " AND t1.posting_date >= %(from_date)s"
		
	if filters.get("to_date"):
		conditions += " AND t1.posting_date <= %(to_date)s"
		
	return conditions
