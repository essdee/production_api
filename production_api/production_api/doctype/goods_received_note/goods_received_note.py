# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, getdate

class GoodsReceivedNote(Document):
	pass

@frappe.whitelist(allow_guest=True)
def save_goods_received_note(against, purchase_order, delivery_location, delivery_date, items):
	grn = frappe.new_doc("Goods Received Note")
	purchase_order_doc = frappe.get_doc(against, purchase_order)
	grn.naming_series = "GRN-"
	grn.against = against
	grn.against_id = purchase_order
	grn.supplier = purchase_order_doc.supplier
	grn.delivery_date = getdate(delivery_date)
	grn.supplier_address = purchase_order_doc.supplier_address
	grn.supplier_contact = purchase_order_doc.contact_person
	grn.delivery_location = delivery_location
	item_table = save_item_details(items)
	grn.set('items', item_table)
	grn.save()
	return grn.submit()

def save_item_details(item_details):
	"""
		Save item details to Goods Received Note
		Item details format:
		Eg: see sample_po_item.jsonc
	"""
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	items = []
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					if values.get('qty'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_variant(item_name, item_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, item_attributes)
							variant1.insert()
							variant_name = variant1.name
						item1['item_variant'] = variant_name
						item1['delivery_location'] = item['delivery_location']
						item1['delivery_date'] = item['delivery_date']
						item1['lot'] = item.get('lot')
						item1['qty'] = values.get('qty')
						item1['uom'] = values.get('default_uom')
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['secondary_uom'] = values.get('secondary_uom')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					print(item_name)
					item1 = {}
					variant_name = get_variant(item_name, item_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, item_attributes)
						variant1.insert()
						variant_name = variant1.name
					item1['item_variant'] = variant_name
					item1['delivery_location'] = item['delivery_location']
					item1['delivery_date'] = item['delivery_date']
					item1['lot'] = item.get('lot')
					item1['qty'] = item['values']['default'].get('qty')
					item1['uom'] = item.get('default_uom')
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['secondary_uom'] = item.get('secondary_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					items.append(item1)
			row_index += 1
	return items