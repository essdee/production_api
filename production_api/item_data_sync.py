import json

import frappe


def orginize_data(rows):
	item_in = {}

	default_uom = ""
	for r in rows:
		item_name = r.get("item_name")

		if not item_name:
			continue
		data_map = item_in.get(item_name)
		if not data_map:
			data_map = {
				"item_name": item_name,
				"primary_attribute": r.get("primary_attribute"),
				"primary_attribute_values": [],
				"attributes": [],
				"attributes_value": {},
				"rate": {},
				"retail_rate": {},
				"mrp_rate": {},
				"variant_map": {},
				"size_order": {},
			}
		item_in[item_name] = data_map

		size = r.get("attribute_value")
		item_variant = r.get("item_variant")
		sort_order = r.get("sort_order")

		if size and size not in data_map["primary_attribute_values"]:
			data_map["primary_attribute_values"].append(size)
		if size and sort_order is not None and size not in data_map["size_order"]:
			data_map["size_order"][size] = sort_order

		if size:
			data_map["rate"][size] = r.get("rate") or 0
			data_map["retail_rate"][size] = r.get("retail_rate") or 0
			data_map["mrp_rate"][size] = r.get("mrp_rate") or 0
			if item_variant:
				data_map["variant_map"][size] = item_variant

		if not default_uom:
			default_uom = r.get("default_uom")

	for item in item_in.values():
		ordered_sizes = sorted(
			item["primary_attribute_values"],
			key=lambda x: (item["size_order"].get(x, 9999), x),
		)

		item["primary_attribute_values"] = ordered_sizes

	return item_in.values(), default_uom


@frappe.whitelist()
def get_item_data(item_name=None):

	item_filter = ""
	if item_name:
		item_filter = " AND I3.name1 = %(item_name)s "
	primary_attribute = frappe.db.get_single_value(
		"IPD Settings", "default_primary_attribute")

	arg = {"item_name": item_name,
		   "primary_attribute": primary_attribute}
	query = f""" 
					SELECT 
					DISTINCT
					I1.attribute,
					I1.attribute_value,
					I2.name AS item_variant,
					I4.rate,
					I4.retail_rate,
					I4.mrp_rate,
					I3.primary_attribute,
					FGM.name1 AS item_name,
					I3.default_unit_of_measure as default_uom,
					FIS.idx AS sort_order

				FROM `tabItem Variant Attribute` I1

				LEFT JOIN `tabItem Variant` I2 ON I2.name=I1.parent 

				LEFT JOIN `tabItem` I3 ON I3.name=I2.item

				LEFT JOIN `tabFG Item Master` FGM ON FGM.item=I3.name 

				LEFT JOIN `tabFG Item Size` FIS ON FIS.parent=FGM.name

				AND FIS.attribute_value=I1.attribute_value

				INNER JOIN `tabSales Item Price` I4 ON  I4.item_variant=I1.parent

				WHERE FGM.disabled=0 {item_filter} AND FGM.is_scheme=0 AND I1.attribute=%(primary_attribute)s

				AND NOT EXISTS (

				SELECT 1 FROM `tabItem Variant Attribute` IV1  WHERE IV1.parent=I2.name AND IV1.attribute NOT IN (%(primary_attribute)s,I3.dependent_attribute )

				)

				ORDER BY FGM.name1,FIS.idx ,I1.idx
			   

			"""
	rows = frappe.db.sql(query, arg, as_dict=True)
	

	data, default_uom = orginize_data(rows)
	return {
		"status": 200,
		"data": data,
		"default_unit_of_measure": default_uom,
	}

def float_x(value, default=0):
	try:
		return float(value)
	except Exception:
		return default


@frappe.whitelist()
def upsert_sales_item_price(fieldname, value):
	if fieldname not in ("rate", "retail_rate", "mrp_rate"):
		frappe.throw("Field name not in the list")
	if isinstance(value, str):
		value = json.loads(value)
	if not isinstance(value, dict):
		frappe.throw("Value must be a dict")
	
	if not value:
		return{
			"status":200,
			"message":"No data to update"
		}
	variant=list(value.keys())

	ex_item=frappe.get_all("Sales Item Price",
						filters={"item_variant":["in",variant]},
						fields=["name","item_variant",fieldname]
	)
	
		
	ex_data={r.get("item_variant"): r for r in ex_item}
	for iv,v in value.items():
		row=ex_data.get(iv)
		if not row:
			continue
		value_n=float_x(v)
		
		frappe.db.set_value("Sales Item Price", 
					   row.get("name"),
						fieldname, value_n)

	return{
		"status":200,
		"message":"Price updated successfully	"
	}

@frappe.whitelist()
def bulk_upload_data_from_file(value=None):
	if isinstance(value,str):
		value=json.loads(value)
	if not isinstance(value, dict):
		frappe.throw("Value must be a dict")
	if not value:
		return {
			"status": 200,
			"message": "No data to update"
		}
	vari_file=list(value.keys())
	ex_item=frappe.get_all("Sales Item Price",
						filters={"item_variant":["in",vari_file]},
						fields=["name","item_variant"]
	)
	print("ex_item", value)
	ex_data={r.get("item_variant"): r for r in ex_item}
	for iv,v in value.items():
		r=ex_data.get(iv)
		if not r:
			continue
		frappe.db.set_value("Sales Item Price",r.get("name"),{
			"rate": float_x(v.get("rate"),0),
			"retail_rate": float_x(v.get("retail_rate"),0),
			"mrp_rate": float_x(v.get("mrp_rate"),0),
		})

	return {
		"status": 200,
		"message": "Price updated successfully"
	}