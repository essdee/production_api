# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe import utils
from frappe.utils import cint, get_link_to_form
from frappe import _

class ItemPrice(Document):
	def before_validate(self):
		validate_price_values(self.item_price_values)

	def before_submit(self):
		filters = [
			["item_name", "=", self.item_name],
			["docstatus", "=", 1],
			["workflow_state", "=", "Approved"],
		]
		if self.supplier == None:
			filters.append(["supplier", "is", "not set"])
		else:
			filters.append(["supplier", "=", self.supplier])
		price_list = frappe.db.get_list(
			'Item Price',
			filters=filters,
			pluck= "name",
			order_by='from_date asc',
		)
		for price in price_list:
			doc = frappe.get_doc("Item Price", price)
			from_date = utils.get_datetime(self.from_date).date()
			if doc.from_date == from_date:
				frappe.throw(f"An Item Price was found with the same `From Date`. Please Expire it before submitting this one.\n{get_link_to_form('Item Price', price)}")
			elif doc.from_date > from_date:
				if not self.to_date or self.to_date >= doc.from_date:
					frappe.throw(f"An Updated Price list for the same Item and Supplier exists from {frappe.utils.format_date(doc.from_date)}. Please set `To Date` less than that date or cancel the next Price.\n{get_link_to_form('Item Price', price)}")
			else:
				to_date = utils.add_days(from_date, -1)
				doc.to_date = to_date
				doc.save()
		
		self.set('approved_by', frappe.get_user().doc.name)

	def validate_attribute_values(self, qty = 0, attribute = None, attribute_value = None, get_lowest_moq_price=False) :
		if self.depends_on_attribute and (attribute == None or self.attribute != attribute or attribute_value == None):
			return None
		price_values = [[price.moq, price.price, price.attribute_value] for price in self.item_price_values]
		price = self.get_price_value(price_values, qty, attribute_value, get_lowest_moq_price)
		return price
	
	def get_price_value(self, item_price_values, qty = 0, attribute_value = None, get_lowest_moq_price=False):
		"""
		Get Item Price Value for the qty and the attribute value from item_price_values
		:param item_price_values: as List of List
			item_price_values = [
				[moq, price, attribute],
				[0, 100, None],
				[10, 98, '20 Dia']
			]
		"""
		# Filter the Attribute Value
		item_price_values = [item_price for item_price in item_price_values if item_price[2] == attribute_value]
		if not len(item_price_values):
			return None
		moq = -1
		rate = -1
		for price in item_price_values:
			if moq < price[0] and (price[0] <= qty or get_lowest_moq_price):
				moq = price[0]
				rate = price[1]
		if (moq != -1):
			return rate
		return None

def get_item_variant_price(variant: str):
	variant = frappe.get_doc("Item Variant", variant)
	price_list = get_all_active_price(item=variant.item)
	print("Price List: ", price_list)
	rate = None
	for price in price_list:
		item_price = frappe.get_doc("Item Price", price.name)
		if item_price.depends_on_attribute:
			rate1 = item_price.validate_attribute_values(qty=0, attribute=item_price.attribute, attribute_value=variant.get_attribute_value(item_price.attribute), get_lowest_moq_price=True)
			if rate1:
				rate = rate1
				break
		else:
			rate1 = item_price.validate_attribute_values(qty=0, get_lowest_moq_price=True)
			if rate1:
				rate = rate1
				break
			pass

	return rate

@frappe.whitelist()
def get_active_price(item: str, supplier: str = None, raise_error=True):
	if (item == None):
		return None
	filters = {
		"item_name": item,
		"from_date": ['<=', utils.nowdate()],
		"to_date": ['is', 'not set'],
		"docstatus": 1
	}
	if (supplier != None):
		filters['supplier'] = supplier
	lst1 = frappe.db.get_list(
		'Item Price',
		filters=filters,
	)
	filters['to_date'] = ['>=', utils.nowdate()]
	lst2 = frappe.db.get_list(
		'Item Price',
		filters=filters,
	)
	lst = lst1 + lst2
	if len(lst) == 0:
		frappe.throw("No Active Price List")
	
	if supplier != None and len(lst) > 1:
		frappe.throw("Multiple Price list Found")
	
	d = frappe.get_doc('Item Price', lst[0].name)
	return d

def validate_price_values(item_price_values):
	values = []
	for price in item_price_values:
		unique_value = ', '.join([str(price.moq), str(price.attribute_value)])
		if unique_value in values:
			frappe.throw('Duplicate Entries Found')
		else:
			values.append(unique_value)

@frappe.whitelist()
def get_item_supplier_price(item_detail, supplier: str = None):
	if (item_detail == None or supplier == None):
		return None
	if (type(item_detail) is str):
		item_detail = json.loads(item_detail)
	item_price = None
	try:
		item_price = get_active_price(item_detail["name"], supplier)
	except:
		return None

	if (item_price != None):
		if item_price.depends_on_attribute:
			if item_price.attribute in item_detail["attributes"].keys():
				qty_sum = 0
				for qty_key in item_detail["values"].keys():
					qty_sum += item_detail["values"][qty_key]["qty"]
				price = item_price.validate_attribute_values(qty=qty_sum, attribute = item_price.attribute, attribute_value = item_detail["attributes"][item_price.attribute])
				return price
			elif item_price.attribute == item_detail["primary_attribute"]:
				prices = {}
				for qty_key in item_detail["values"].keys():
					qty = item_detail["values"][qty_key]["qty"]
					price = item_price.validate_attribute_values(qty=qty, attribute = item_price.attribute, attribute_value = qty_key)
					prices[qty_key] = price
				return prices
			else:
				return None
		else:
			qty_sum = 0
			for qty_key in item_detail["values"].keys():
				qty_sum += item_detail["values"][qty_key]["qty"]
			price = item_price.validate_attribute_values(qty=qty_sum)
			return price
		
def get_all_active_price(item = None, supplier = None):
	if item == None and supplier == None:
		return []
	filters = {
		"from_date": ['<=', utils.nowdate()],
		"docstatus": 1
	}
	if (item != None):
		filters['item_name'] = item

	if (supplier != None):
		filters['supplier'] = supplier
	lst = frappe.db.get_list(
		'Item Price',
		filters=filters,
	)
	return lst

def update_all_expired_item_price():
	filters = [
		["to_date", "<", utils.nowdate()],
		["to_date", "is", "set"],
		["docstatus", "=", 1]
	]
	price_list = frappe.db.get_all(
		'Item Price',
		filters=filters,
		pluck="name"
	)
	workflow_exists = frappe.db.exists("Workflow", {"document_type": "Item Price", "is_active": 1})
	for price in price_list:
		doc = frappe.get_doc("Item Price", price)
		if workflow_exists:
			cancel_item_price(doc)
		else:
			doc.cancel()
		doc.add_comment("Info", "Cancelled Automatically due to expiry")


def cancel_item_price(doc):
	workflow_name = frappe.db.get_value("Workflow", {"document_type": "Item Price", "is_active": 1}, "name")
	if workflow_name:
		workflow = frappe.get_doc("Workflow", workflow_name)
		cancel_states = []
		for state in workflow.states:
			if cint(state.doc_status) == 2:
				cancel_states.append(state.state)
		if "Expired" in cancel_states:
			cancel_states = ["Expired"]

		transition = get_cancel_transitions(doc, workflow, cancel_states)
		if transition:
			doc.set(workflow.workflow_state_field, transition.next_state)
			next_state = [d for d in workflow.states if d.state == transition.next_state][0]
			# update any additional field
			if next_state.update_field:
				doc.set(next_state.update_field, next_state.update_value)
			doc.cancel()
			doc.add_comment("Workflow", _(next_state.state))
	else:
		doc.cancel()

def get_cancel_transitions(doc, workflow, cancel_states) -> dict:
	"""Return list of possible transitions for the given doc"""
	from frappe.model.document import Document

	if not isinstance(doc, Document):
		doc = frappe.get_doc(frappe.parse_json(doc))
		doc.load_from_db()

	if doc.is_new():
		return []

	current_state = doc.get(workflow.workflow_state_field)

	if not current_state:	
		frappe.throw("Workflow State not set")

	transitions = []

	for transition in workflow.transitions:
		if transition.state == current_state and transition.next_state in cancel_states:
			transitions.append(transition.as_dict())

	if len(transitions) > 0:
		return transitions[0]
	return None
