# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import math
import frappe, json
from itertools import groupby
from itertools import zip_longest
from frappe.utils import now_datetime
from frappe.model.document import Document
from production_api.utils import get_stich_details, update_if_string_instance
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.essdee_production.doctype.lot.lot import get_uom_conversion_factor
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class ItemProductionDetail(Document):
	def autoname(self):
		item = self.item
		version = frappe.db.sql(
			f"""
				SELECT max(version) as max_version FROM `tabItem Production Detail` WHERE item = '{item}'
			""",as_dict=True
		)[0]['max_version']
		if version:
			new_version = version + 1
		else:
			new_version = 1	

		self.name = f"{item}-{new_version}"
		self.version = new_version
		
	def load_attribute_list(self):
		attribute_list = []
		for attribute in self.item_attributes:
			attribute_doc = frappe.get_cached_doc("Item Attribute", attribute.attribute)
			if not attribute_doc.numeric_values:
				if attribute.mapping != None:
					doc = frappe.get_cached_doc("Item Item Attribute Mapping", attribute.mapping)
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.mapping,
						'attr_values': doc.values,
						'doctype': 'Item Item Attribute Mapping'
					})
				else:
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.mapping,
						'attr_values': [],
						'doctype': 'Item Item Attribute Mapping'
					})
		self.set_onload('attr_list', attribute_list)

	def load_bom_attribute_list(self):
		bom_attribute_list = []
		for bom in self.item_bom:
			if bom.attribute_mapping != None:
				doc = frappe.get_cached_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
				bom_attribute_list.append({
					'bom_item': bom.item,
					'bom_attr_mapping_link': bom.attribute_mapping,
					'bom_attr_mapping_based_on': bom.based_on_attribute_mapping,
					'bom_attr_mapping_list': doc.values,
					'doctype': 'Item BOM Attribute Mapping'
				})
		self.set_onload('bom_attr_list', bom_attribute_list)

	def load_dependent_attribute(self):
		dependent_attribute = {}
		if self.dependent_attribute and self.dependent_attribute_mapping:
			dependent_attribute = get_dependent_attribute_details(self.dependent_attribute_mapping)

		self.set_onload('dependent_attribute', dependent_attribute)	

	def onload(self):
		self.load_attribute_list()
		self.load_bom_attribute_list()
		self.load_dependent_attribute()
		set_items = fetch_combination_items(self.get('set_item_combination_details'))

		if len(set_items['values']) > 0:
			self.set_onload('set_item_detail',set_items)

		stich_items = fetch_combination_items(self.get('stiching_item_combination_details')) 	
		if len(stich_items['values']) > 0:
			self.set_onload('stiching_item_detail',stich_items)
	
	def before_save(self):
		if self.is_new():
			doc = frappe.get_single("IPD Settings")
			self.packing_process = doc.default_packing_process
			self.pack_in_stage = doc.default_pack_in_stage
			self.pack_out_stage = doc.default_pack_out_stage
			self.packing_attribute = doc.default_packing_attribute
			self.stiching_process = doc.default_stitching_process
			self.stiching_attribute = doc.default_stitching_attribute
			self.stiching_in_stage = doc.default_stitching_in_stage
			self.stiching_out_stage = doc.default_stitching_out_stage
			self.cutting_process = doc.default_cutting_process

	def on_update(self):	
		docs = frappe.flags.delete_bom_mapping
		if docs:
			for mapping in docs:
				frappe.delete_doc("Item BOM Attribute Mapping", mapping)
	
	def before_validate(self):
		items = []
		for item in self.item_bom:
			if not item.based_on_attribute_mapping:
				if item.item in items:
					frappe.throw("Duplicate Item in BOM "+item.item + " in Row "+ str(item.idx))
				items.append(item.item)	

		if self.get('set_item_detail') and self.is_set_item:
			set_details = save_item_details(self.set_item_detail)
			self.set('set_item_combination_details', set_details)

		if self.get('stiching_item_detail'):
			stiching_detail = save_item_details(self.stiching_item_detail,ipd_doc = self)
			self.set('stiching_item_combination_details', stiching_detail)

		if not self.is_set_item:
			self.set('set_item_combination_details', [])
			self.set('major_attribute_value', None)
			self.set('set_item_attribute', None)

		if len(self.cloth_detail) > 0:
			x = set()
			for cloth in self.cloth_detail:
				x.add(cloth.name1)
			if len(x) != len(self.cloth_detail):
				frappe.throw("Duplicates are occured in the cloth detail")	

		cloths = []
		for cloth in self.cloth_detail:
			cloths.append(cloth.name1)
		cut_json = update_if_string_instance(self.cutting_cloths_json)

		if cut_json:
			cut_json['select_list'] = cloths		
		self.cutting_cloths_json = cut_json

		if self.get("marker_details"):
			group_items = self.marker_details
			items2 = []
			for item in group_items:
				item['selected'].sort()
				selected = ",".join(item['selected'])
				if selected:
					items2.append({
						"group_panels":selected,
					})
			self.set("cutting_marker_groups", items2)	

		if self.is_set_item:
			doc = frappe.get_doc("Item Production Detail",self.name)
			if doc.is_set_item and self.is_set_item:
				mapping = None
				for item in self.item_attributes:
					if item.attribute == self.set_item_attribute:
						mapping = item.mapping
						break
				map_doc = frappe.get_cached_doc("Item Item Attribute Mapping",mapping)
				map_values = []
				for map_value in map_doc.values:
					map_values.append(map_value.attribute_value)

				check_dict = {}

				for attr in self.stiching_item_details:
					if attr.is_default:
						if check_dict.get(attr.set_item_attribute_value):
							frappe.throw(f"Select only one Is Default for {attr.set_item_attribute_value}")	
						else:
							check_dict[attr.set_item_attribute_value] =  1

				if len(check_dict) < len(map_values):
					frappe.throw("Select Is default for all Set Item Attributes")

	def create_new_mapping_values(self):
		for attribute in self.get('item_attributes'):
			if attribute.mapping:
				doc = frappe.get_cached_doc("Item Item Attribute Mapping", attribute.mapping)
				duplicate_doc = frappe.new_doc("Item Item Attribute Mapping")
				duplicate_doc.attribute_name = doc.attribute_name
				duplicate_doc.values = doc.values
				duplicate_doc.save()
				attribute.mapping = duplicate_doc.name

		if self.dependent_attribute_mapping:
			doc = frappe.get_cached_doc('Item Dependent Attribute Mapping',self.dependent_attribute_mapping)		
			duplicate_doc = frappe.new_doc("Item Dependent Attribute Mapping")
			duplicate_doc.item = doc.item
			duplicate_doc.dependent_attribute = doc.dependent_attribute
			duplicate_doc.mapping = doc.mapping
			duplicate_doc.details = doc.details
			duplicate_doc.save()
			self.dependent_attribute_mapping = duplicate_doc.name

		for bom in self.get('item_bom'):
			if bom.based_on_attribute_mapping and bom.attribute_mapping:
				doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
				duplicate_doc = frappe.copy_doc(doc)
				duplicate_doc.item = self.item
				duplicate_doc.bom_item = bom.item
				duplicate_doc.item_production_detail = self.name
				duplicate_doc.insert()
				bom.attribute_mapping = duplicate_doc.name
			else:
				bom.attribute_mapping = None

	def update_mapping_values(self):
		for attribute in self.get('item_attributes'):
			if attribute.mapping == None:
				doc = frappe.new_doc("Item Item Attribute Mapping")
				doc.attribute_name= attribute.attribute 
				doc.save()
				attribute.mapping = doc.name
		frappe.flags.delete_bom_mapping = []
		for bom in self.get('item_bom'):
			if bom.based_on_attribute_mapping and not bom.attribute_mapping:
				doc = frappe.new_doc("Item BOM Attribute Mapping")
				doc.item_production_detail = self.name
				doc.item = self.item
				doc.bom_item = bom.item

				attr_values = []
				item_doc = frappe.get_cached_doc("Item",bom.item)
				for item in item_doc.attributes:
					attr_values.append({'attribute':item.attribute})

				doc.set('item_attributes',[{'attribute':self.packing_attribute}])
				doc.set('bom_item_attributes',attr_values)

				doc.flags.ignore_validate = True
				doc.save()
				bom.attribute_mapping = doc.name
			elif not bom.based_on_attribute_mapping and bom.attribute_mapping:
				name = bom.attribute_mapping
				bom.attribute_mapping = None
				frappe.flags.delete_bom_mapping.append(name)
	
	def packing_tab_validations(self):
		if self.packing_combo == 0:
			frappe.throw("The packing combo should not be zero")

		if self.packing_attribute_no == 0:
			frappe.throw("The packing attribute no should not be zero")

		mapping = None
		for item in self.item_attributes:
			if item.attribute == self.packing_attribute:
				mapping = item.mapping
				break

		map_doc = frappe.get_cached_doc("Item Item Attribute Mapping", mapping)
		if len(map_doc.values) < self.packing_attribute_no:
			frappe.throw(f"The Packing attribute no is {self.packing_attribute_no} But there is only {len(map_doc.values)} attributes are available")

		if len(self.packing_attribute_details) != self.packing_attribute_no:
			frappe.throw(f"Only {self.packing_attribute_no} {self.packing_attribute}'s are required")

		attr = set()
		if self.auto_calculate:
			for row in self.packing_attribute_details:
				attr.add(row.attribute_value)
				row.quantity = 0
		else:		
			sum = 0.0
			for row in self.packing_attribute_details:
				if not row.quantity:
					frappe.throw("Enter value in Packing Attribute Details, Zero is not considered as a valid quantity")
				sum = sum + row.quantity
				attr.add(row.attribute_value)

			if sum < self.packing_combo or sum > self.packing_combo:
				frappe.throw(f"In Packing Attribute Details, the sum of quantity should be {self.packing_combo}")
		
		if len(attr) != len(self.packing_attribute_details):
			frappe.throw("Duplicate Attribute values are occured in Packing Attribute Details")	

	def stiching_tab_validations(self):
		if len(self.stiching_item_details) == 0:
			frappe.throw("Enter stiching attribute details")
		attr= set()
		sum = 0.0
		for row in self.stiching_item_details:
			if not row.quantity:
				frappe.throw("Enter value in Stiching Item Details, Zero is not considered as a valid quantity")
			sum = sum + row.quantity
			attr.add(row.stiching_attribute_value)

		if len(attr) != len(self.stiching_item_details):
			frappe.throw("Duplicate Attribute values are occured in Stiching Item Details")	
	
	def cutting_tab_validations(self):
		ipd_cloth_attributes = [i.attribute for i in self.cloth_attributes]
		ipd_cutting_attributes = [i.attribute for i in self.cutting_attributes]
		accessory_attributes = [i.attribute for i in self.accessory_attributes]

		if not self.is_same_packing_attribute and self.stiching_attribute not in ipd_cutting_attributes and len(ipd_cutting_attributes) > 0:
			frappe.throw(f"{self.stiching_attribute} Should be in Cutting Combination")

		if self.stiching_attribute in ipd_cloth_attributes and self.stiching_attribute not in ipd_cutting_attributes:
			frappe.throw(f"Please mention the {self.stiching_attribute} in Cutting Combination")
		
		pre_set_item = frappe.get_value("Item Production Detail", self.name,"is_set_item")
		if pre_set_item:
			if self.is_set_item and self.set_item_attribute not in accessory_attributes and len(accessory_attributes) > 0:
				frappe.throw(f"{self.set_item_attribute} should be in the Accessory Combination")
			
			if self.is_set_item and self.set_item_attribute not in ipd_cutting_attributes and len(ipd_cutting_attributes) > 0:
				frappe.throw(f"{self.set_item_attribute} Should be in the Cutting Combination")

		if self.is_same_packing_attribute:
			for item in self.stiching_item_combination_details:
				item.attribute_value = item.major_attribute_value

	def validate(self):
		if self.get('__islocal'):
			self.create_new_mapping_values()

		self.update_mapping_values()		

		if not self.is_new():
			self.packing_tab_validations()	

		if self.stiching_process:			
			self.stiching_tab_validations()
			
		if self.cutting_process:
			self.cutting_tab_validations()	

		if len(self.accessory_attributes) > 0 and update_if_string_instance(self.cloth_accessory_json):
			if not update_if_string_instance(self.stiching_accessory_json):
				frappe.throw("Enter the Details for Stitching Accessory Combination")

	def on_trash(self):
		documents = {
			"Item Item Attribute Mapping":[],
			'Item Dependent Attribute Mapping':[],
			"Item BOM Attribute Mapping":[],
		}
		for attribute in self.get('item_attributes'):
			if attribute.mapping:
				doc_name = attribute.mapping
				attribute.mapping = None
				documents['Item Item Attribute Mapping'].append(doc_name)

		if self.dependent_attribute_mapping:
			doc_name = self.dependent_attribute_mapping
			self.dependent_attribute_mapping = None
			documents['Item Dependent Attribute Mapping'].append(doc_name)		

		for bom in self.get('item_bom'):
			if bom.attribute_mapping:
				doc_name = bom.attribute_mapping
				bom.attribute_mapping = None
				documents["Item BOM Attribute Mapping"].append(doc_name)
		delete_docs(documents)		

def delete_docs(documents):
	for key, value in documents.items():
		doctype = frappe.qb.DocType(key)
		if value:
			frappe.qb.from_(doctype).delete().where(doctype.name.isin(value)).run()

@frappe.whitelist()
def get_ipd_primary_values(production_detail):
	doc = frappe.get_cached_doc("Item Production Detail", production_detail)
	primary_attr_values = []
	mapping = None
	for i in doc.item_attributes:
		if i.attribute == doc.primary_item_attribute:
			mapping = i.mapping
			break
	if mapping:
		map_doc = frappe.get_cached_doc("Item Item Attribute Mapping", mapping)	
		for val in map_doc.values:
			primary_attr_values.append(val.attribute_value)
	return primary_attr_values

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_attributes(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute' or filters['item_production_detail'] == None):
		return []

	item_production_detail_name = filters['item_production_detail']
	item_production_detail = frappe.get_cached_doc("Item Production Detail", item_production_detail_name)
	attributes = [attribute.attribute for attribute in item_production_detail.item_attributes]
	return [[value] for value in attributes if value.lower().startswith(txt.lower())]

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_attribute_detail_values(doctype, txt, searchfield, start, page_len, filters):
	doc = frappe.qb.DocType('Item Item Attribute Mapping Value')
	result = frappe.qb.from_(doc).select(doc.attribute_value).where(doc.parent == filters['mapping']).run(as_list=True)
	attr_list = [[res[0]] for res in result if res[0].lower().startswith(txt.lower())]
	return attr_list

@frappe.whitelist()
def get_ipd_item_group():
	return frappe.db.get_single_value("IPD Settings", "item_group")

@frappe.whitelist()
def get_attribute_values(item_production_detail, attributes = None):
	ipd_doc = frappe.get_doc("Item Production Detail", item_production_detail)
	attribute_values = {}

	if not attributes:
		attributes = [attr.attribute for attr in ipd_doc.item_attributes]
	for attribute in ipd_doc.item_attributes:
		if attribute.attribute in attributes and attribute.mapping != None:
			if attribute.attribute == ipd_doc.packing_attribute:
				attr_values = []
				for attr in ipd_doc.stiching_item_combination_details:
					if attr.major_attribute_value not in attr_values:
						attr_values.append(attr.major_attribute_value)
				attribute_values[attribute.attribute] = attr_values
			elif attribute.attribute == ipd_doc.stiching_item_details:
				attribute_values[attribute.attribute] = [d.stiching_attribute_value for d in ipd_doc.stiching_item_details]
			else:
				doc = frappe.get_cached_doc("Item Item Attribute Mapping", attribute.mapping)
				attribute_values[attribute.attribute] = [d.attribute_value for d in doc.values]
	return attribute_values

@frappe.whitelist()
def get_calculated_bom(item_production_detail, items, lot_name, process_name = None, doctype=None, deliverable=False):
	item_detail = frappe.get_cached_doc("Item Production Detail", item_production_detail)
	bom = {}
	bom_summary = {}
	items = update_if_string_instance(items)
	if len(items) == 0:
		return
	lot_doc = frappe.get_cached_doc("Lot", lot_name)
	cloth_combination = get_cloth_combination(item_detail)
	stitching_combination = get_stitching_combination(item_detail)
	bom_combination = get_bom_combination(item_detail.item_bom, process_name)
	lot_item_detail = frappe.get_cached_doc("Item", lot_doc.item)
	cloth_detail = {}
	for cloth in item_detail.cloth_detail:
		if doctype:
			cloth_detail[cloth.name1] = cloth.cloth
		elif cloth.is_bom_item: 	
			cloth_detail[cloth.name1] = cloth.cloth
	total_quantity = None
	if not process_name:
		total_quantity = lot_doc.total_order_quantity
	else:
		total_quantity = 0
		for i in items:
			total_quantity += i['quantity']
	mapping_bom = {}
	for bom_item in item_detail.item_bom:
		if process_name and bom_item.process_name != process_name:
			continue
		if not bom_item.based_on_attribute_mapping:
			get_or_create_variant(bom_item.item, {})
			bom[bom_item.item] = {}
			qty_of_product = bom_item.qty_of_product
			qty_of_bom = bom_item.qty_of_bom_item
			temp_qty = total_quantity
			if bom_item.dependent_attribute_value and bom_item.dependent_attribute_value != lot_doc.pack_in_stage:
				dependent_attr_uom = lot_item_detail.default_unit_of_measure
				qty_of_product = get_uom_conversion_factor(lot_item_detail.uom_conversion_details, dependent_attr_uom  ,lot_doc.packing_uom)
				if bom_item.dependent_attribute_value == lot_doc.pack_out_stage:
					if item_detail.is_set_item:
						temp_qty = temp_qty / 2
					qty_of_product = qty_of_product * item_detail.packing_combo

			qty_of_product = qty_of_product/qty_of_bom
			uom = frappe.get_value("Item", bom_item.item, "default_unit_of_measure")
			quantity = temp_qty / qty_of_product
			if not bom[bom_item.item].get(bom_item.item, False):
				bom[bom_item.item][bom_item.item] = [quantity,bom_item.process_name, uom]
			else:
				bom[bom_item.item][bom_item.item][0] += quantity
			if not bom_summary.get(bom_item.item,False):
				dept_attr = bom_item.dependent_attribute_value
				attr_details = get_dependent_attribute_details(item_detail.dependent_attribute_mapping)
				dept_attr_uom = attr_details['attr_list'][dept_attr]['uom']
				default_uom = frappe.get_value("Item",bom_item.item,"default_unit_of_measure")
				bom_summary[bom_item.item] = [bom_item.process_name,bom_item.qty_of_product,dept_attr_uom,bom_item.qty_of_bom_item,default_uom,0]	

	cloth_details = {}
	
	for item in items:
		qty = item['quantity']
		if not qty and not deliverable:
			continue
		variant = item['item_variant']
		attr_values = {}
		variant_doc = frappe.get_cached_doc("Item Variant", variant)

		for x in variant_doc.attributes:
			attr_values[x.attribute] = x.attribute_value
		idx_dict = {}
		for bom_item in item_detail.item_bom:
			if process_name and bom_item.process_name != process_name:
				continue
			if bom_item.based_on_attribute_mapping:
				uom = frappe.get_value("Item", bom_item.item, "default_unit_of_measure")

				if not mapping_bom.get(bom_item.item,False):
					mapping_bom[bom_item.item] = {}
				
				idx = 0
				if bom_item.item in idx_dict:
					idx = idx_dict[bom_item.item] + 1
					idx_dict[bom_item.item] = idx
				else:
					idx = 0
					idx_dict[bom_item.item] = 0
				xattr_values = {}
				for x in bom_combination[bom_item.item][idx]["keys"]:
					if attr_values.get(x):
						xattr_values[x] = attr_values[x]
				
				if not bom.get(bom_item.item, False):
					bom[bom_item.item] = {}

				qty_of_product = bom_item.qty_of_product
				if bom_item.dependent_attribute_value and not bom_item.dependent_attribute_value == lot_doc.pack_in_stage:
					dependent_attr_uom = lot_item_detail.default_unit_of_measure
					qty_of_product = get_uom_conversion_factor(lot_item_detail.uom_conversion_details, dependent_attr_uom  ,lot_doc.packing_uom)
					if bom_item.dependent_attribute_value == lot_doc.pack_out_stage:
						qty_of_product = qty_of_product * item_detail.packing_combo
				qty_of_bom_item = 0
				for key, val in bom_combination[bom_item.item][idx].items():
					if key != "keys" and key != "same_attributes" and xattr_values == val["key"]:
						attr = val["value"].copy()
						qty_of_bom_item = val['qty_of_bom']
						if qty_of_bom_item == 0:
							qty_of_bom_item = bom_item.qty_of_bom_item
						for x in bom_combination[bom_item.item][idx]["same_attributes"]: 
							attr[x] = attr_values[x]

						if not bom_summary.get(bom_item.item,False):
							dept_attr = bom_item.dependent_attribute_value
							attr_details = get_dependent_attribute_details(item_detail.dependent_attribute_mapping)
							dept_attr_uom = attr_details['attr_list'][dept_attr]['uom']
							default_uom = frappe.get_value("Item",bom_item.item,"default_unit_of_measure")
							bom_summary[bom_item.item] = [bom_item.process_name,bom_item.qty_of_product,dept_attr_uom,qty_of_bom_item,default_uom,0]

						qty_of_product = qty_of_product/qty_of_bom_item
						quantity = qty / qty_of_product
						key = tuple(sorted(attr.items()))
						if not mapping_bom[bom_item.item].get(key, False):
							mapping_bom[bom_item.item][key] = [quantity,bom_item.process_name, uom]
						else:
							mapping_bom[bom_item.item][key][0] += quantity

		if item_detail.dependent_attribute and attr_values.get(item_detail.dependent_attribute):
			del attr_values[item_detail.dependent_attribute]

		if not process_name or process_name == item_detail.cutting_process:
			c = calculate_cloth(item_detail, attr_values, item['quantity'], cloth_combination, stitching_combination)
			for c1 in c:
				if c1["cloth_type"] in cloth_detail:
					key = (cloth_detail[c1["cloth_type"]], c1["colour"], c1["dia"])
					cloth_details.setdefault(key, 0)
					cloth_details[key] += c1["quantity"]
	
	bom_items = []
	if not process_name or process_name == item_detail.cutting_process:
		for k in cloth_details:
			uom = frappe.get_value("Item",k[0],"default_unit_of_measure")
			cloth_attrs = {item_detail.packing_attribute: k[1], 'Dia': k[2]}
			cloth_name = get_or_create_variant(k[0], cloth_attrs)
			if not bom.get(k[0],False):
				bom[k[0]] = {cloth_name:[cloth_details[k],item_detail.cutting_process,uom]}
			else:	
				bom[k[0]][cloth_name] = [cloth_details[k],item_detail.cutting_process,uom]
	
	from production_api.utils import get_tuple_attributes
	for key,value in mapping_bom.items():
		for k,val in value.items():
			k = get_tuple_attributes(k)
			k = update_if_string_instance(k)
			variant = get_or_create_variant(key, k)
			if not bom.get(key,False):
				bom[key] = {variant:val}
			else:	
				bom[key][variant] = val
	if process_name:
		return bom
	
	for key, val in bom.items():
		for k,v in val.items():
			if key in bom_summary:
				bom_summary[key][5]+=v[0]

			bom_items.append({'item_name': k,'uom':v[2],'process_name':v[1],'required_qty':v[0]})
	
	lot_doc.set('bom_summary_json',bom_summary)
	lot_doc.set('bom_summary', bom_items)
	lot_doc.last_calculated_time = now_datetime()
	lot_doc.save()	

##################       BOM CALCULATION FUNCTIONS       ##################
def calculate_cloth(ipd_doc, variant_attrs, qty, cloth_combination, stitching_combination):
	attrs = variant_attrs.copy()
	if stitching_combination["stitching_attribute"] in cloth_combination["cloth_attributes"] and stitching_combination["stitching_attribute"] not in cloth_combination["cutting_attributes"]:
		frappe.throw(f"Cannot calculate cloth quantity without {stitching_combination['stitching_attribute']} in Cloth Weight Combination.")
	cloth_detail = []
	if stitching_combination["stitching_attribute"] in cloth_combination["cutting_attributes"]:
		for stiching_attr,attr_qty in stitching_combination["stitching_attribute_count"].items():
			attrs[ipd_doc.stiching_attribute] = stiching_attr
			cloth_key = get_key(attrs, cloth_combination["cloth_attributes"])
			cutting_key = get_key(attrs, cloth_combination["cutting_attributes"])
			stich_key = attrs[ipd_doc.packing_attribute]
			if ipd_doc.is_set_item:
				stich_key = (stich_key, attrs[ipd_doc.set_item_attribute])

			if cloth_combination["cutting_combination"].get(cutting_key) and stiching_attr in stitching_combination["stitching_combination"][stich_key]:
				dia, weight = cloth_combination["cutting_combination"][cutting_key]	
				cloth_type = cloth_combination["cloth_combination"][cloth_key]
				weight = weight * qty * attr_qty
				cloth_colour = stitching_combination["stitching_combination"][stich_key][stiching_attr]
				cloth_detail.append(add_cloth_detail(weight,cloth_type,cloth_colour,dia,"cloth"))
	else:
		dia, weight = cloth_combination["cutting_combination"][get_key(attrs, cloth_combination["cutting_attributes"])]
		cloth_type = cloth_combination["cloth_combination"][get_key(attrs, cloth_combination["cloth_attributes"])]
		weight = weight * qty
		cloth_detail.append(add_cloth_detail(weight,cloth_type,attrs[ipd_doc.packing_attribute],dia,"cloth"))
	accessory_detail = calculate_accessory(ipd_doc, cloth_combination, stitching_combination, attrs, qty)
	cloth_detail = cloth_detail + accessory_detail
	return cloth_detail

def calculate_accessory(ipd_doc, cloth_combination, stitching_combination, attrs, qty):
	accessory_detail = []
	cloth_accessory_json = update_if_string_instance(ipd_doc.accessory_clothtype_json)
	if ipd_doc.stiching_attribute in cloth_combination["accessory_attributes"] and cloth_accessory_json:
		for stiching_attr, attr_qty in stitching_combination["stitching_attribute_count"].items():
			attrs[ipd_doc.stiching_attribute] = stiching_attr
			for accessory_name, accessory_cloth in cloth_accessory_json.items():
				attrs["Accessory"] = accessory_name
				key = get_key(attrs, cloth_combination["accessory_attributes"])
				if cloth_combination["accessory_combination"].get(key):
					dia, accessory_weight = cloth_combination["accessory_combination"][key]
					accessory_colour, cloth = get_accessory_colour(ipd_doc,attrs,accessory_name)
					weight = accessory_weight * qty * attr_qty
					accessory_detail.append(add_cloth_detail(weight,cloth,accessory_colour,dia,"accessory", accessory_name=accessory_name))
	elif cloth_accessory_json:
		for accessory_name, accessory_cloth in cloth_accessory_json.items():
			attrs["Accessory"] = accessory_name
			key = get_key(attrs, cloth_combination["accessory_attributes"])
			if cloth_combination['accessory_combination'].get(key):
				dia, accessory_weight = cloth_combination["accessory_combination"][key]
				accessory_colour, cloth = get_accessory_colour(ipd_doc,attrs,accessory_name)	
				weight = accessory_weight * qty
				accessory_detail.append(add_cloth_detail(weight,cloth,accessory_colour,dia,"accessory", accessory_name=accessory_name))
	return accessory_detail

def get_bom_combination(bom_items, process_name):
	bom_items = update_if_string_instance(bom_items)
	bom_combination = {}
	for bom_item in bom_items:
		if bom_item.based_on_attribute_mapping:
			if process_name and bom_item.process_name != process_name:
				continue
			if not bom_combination.get(bom_item.item):
				bom_combination[bom_item.item] = []
			attr_doc = frappe.get_cached_doc("Item BOM Attribute Mapping",bom_item.attribute_mapping)
			bom_combination[bom_item.item].append({"keys":[],"same_attributes":[]})
			length = len(bom_combination[bom_item.item])
			idx = length -1
			for i in attr_doc.item_attributes:
				if not i.same_attribute:
					bom_combination[bom_item.item][idx]["keys"].append(i.attribute)
				else:
					bom_combination[bom_item.item][idx]["same_attributes"].append(i.attribute)	
			c = {}
			for item in attr_doc.values:
				if c.get(item.index):
					if item.type == 'item':
						c[item.index]["key"] = c[item.index]["key"]|{item.attribute:item.attribute_value}
					else:
						c[item.index]["value"] = c[item.index]["value"]|{item.attribute:item.attribute_value}	
					c[item.index]["qty_of_bom"] = item.quantity	
				else:
					c[item.index] = {"key":{},"value":{}, "qty_of_bom": 0}
					c[item.index]["key"] = {item.attribute:item.attribute_value}	
			bom_combination[bom_item.item][idx] = bom_combination[bom_item.item][idx] | c
	return bom_combination

def add_cloth_detail(weight,cloth_type,cloth_colour,dia,type, accessory_name=None):
	d = {
		"cloth_type": cloth_type,
		"colour": cloth_colour,
		"dia": dia,
		"quantity": weight,
		"type":type
	}
	if accessory_name:
		d["accessory_name"] = accessory_name
	return d	

def get_accessory_colour(ipd_doc,variant_attrs,accessory):
	frappe.log(variant_attrs)
	if ipd_doc.is_set_item:
		part = variant_attrs[ipd_doc.set_item_attribute]
		colour = variant_attrs[ipd_doc.packing_attribute]
		stiching_accessory_json = json.loads(ipd_doc.stiching_accessory_json)
		for row in stiching_accessory_json['items']:
			check = True
			if variant_attrs.get('set_colour') and row.get('major_attr_value'):
				check = variant_attrs.get('set_colour') == row['major_attr_value']
			if row['accessory'] == accessory and row['major_colour'] == colour and row[ipd_doc.set_item_attribute] == part and check:
				return row['accessory_colour'],row['cloth_type']
	else:
		colour = variant_attrs[ipd_doc.packing_attribute]
		stiching_accessory_json = json.loads(ipd_doc.stiching_accessory_json)
		for row in stiching_accessory_json['items']:
			if row['accessory'] == accessory and row['major_colour'] == colour:
				return row['accessory_colour'],row['cloth_type']
	frappe.throw("NO COLOUR")

def get_cloth_combination(ipd_doc):
	cutting_attributes = [i.attribute for i in ipd_doc.cutting_attributes]
	cloth_attributes = [i.attribute for i in ipd_doc.cloth_attributes]
	accessory_attributes = [i.attribute for i in ipd_doc.accessory_attributes]
	cutting_combination = {}
	cloth_combination = {}
	accessory_combination = {}
	cutting_items = json.loads(ipd_doc.cutting_items_json)
	cutting_cloths = json.loads(ipd_doc.cutting_cloths_json)
	accessory_items = json.loads(ipd_doc.cloth_accessory_json)

	for item in cutting_items["items"]:
		cutting_combination[get_key(item, cutting_attributes)] = (item["Dia"], item["Weight"])
	for item in cutting_cloths["items"]:
		cloth_combination[get_key(item, cloth_attributes)] = item["Cloth"]
	accessory_attributes.append("Accessory")
	if accessory_items:
		for item in accessory_items["items"]:
			accessory_combination[get_key(item, accessory_attributes)] = (item["Dia"],item["Weight"])

	return {
		"cutting_attributes": cutting_attributes,
		"cloth_attributes": cloth_attributes,
		"accessory_attributes":accessory_attributes,
		"cutting_combination": cutting_combination,
		"cloth_combination": cloth_combination,
		"accessory_combination":accessory_combination,
	}

def get_stitching_combination(ipd_doc):
	part_panel_comb = {}
	if ipd_doc.is_set_item:
		part_panel_comb = get_stich_details(ipd_doc)

	stitching_combination = {}
	for detail in ipd_doc.stiching_item_combination_details:
		key = detail.major_attribute_value
		if ipd_doc.is_set_item:
			key = (key, part_panel_comb[detail.set_item_attribute_value])

		stitching_combination.setdefault(key, {})
		stitching_combination[key][detail.set_item_attribute_value] = detail.attribute_value

	return {
		"stitching_attribute": ipd_doc.stiching_attribute,
		"stitching_attribute_count": {i.stiching_attribute_value:i.quantity for i in ipd_doc.stiching_item_details},
		"is_same_packing_attribute": ipd_doc.is_same_packing_attribute,
		"stitching_combination": stitching_combination,
	}

def get_key(item, attrs):
	key = []
	for attr in attrs:
		key.append(item[attr])
	return tuple(key)	

##################       COMBINATION       ##################
@frappe.whitelist()
#jinja
def fetch_combination_items(combination_items):
	combination_items = [item.as_dict() for item in combination_items]
	combination_result ={}
	combination_result['attributes'] = []
	combination_result['values'] = []
	for key, items in groupby(combination_items, lambda i: i['index']):
		items = list(items)
		item_list = {}
		item_list['major_attribute'] = items[0]['major_attribute_value']
		item_list['val'] = {}
		for item in items:
			if item['set_item_attribute_value'] not in combination_result['attributes']:
				combination_result['attributes'].append(item['set_item_attribute_value'])
			item_list['val'][item['set_item_attribute_value']] = item['attribute_value']
		combination_result['values'].append(item_list)
	return combination_result

def save_item_details(combination_item_detail, ipd_doc = None):
	combination_item_detail = update_if_string_instance(combination_item_detail)
	item_detail = []
	set_item_stitching_attrs = {}
	set_item_packing_combination = {}
	if ipd_doc and ipd_doc.is_set_item:
		set_item_stitching_attrs = get_stich_details(ipd_doc)
		for i in ipd_doc.set_item_combination_details:
			set_item_packing_combination.setdefault(i.major_attribute_value, {})
			set_item_packing_combination[i.major_attribute_value][i.set_item_attribute_value] = i.attribute_value	
	for idx,item in enumerate(combination_item_detail['values']):
		for value in item['val']:
			row = {}
			row['index'] = idx
			row['major_attribute_value'] = item['major_attribute']
			row['set_item_attribute_value'] = value
			row['attribute_value'] = item['val'][value]
			if ipd_doc and ipd_doc.is_set_item and set_item_stitching_attrs.get(value):
				part = set_item_stitching_attrs[value]
				row['major_attribute_value'] = set_item_packing_combination[item['major_attribute']][part]
				item_detail.append(row)
			else:	
				item_detail.append(row)
	return item_detail	

@frappe.whitelist()
def get_new_combination(attribute_mapping_value, packing_attribute_details, major_attribute_value, is_same_packing_attribute:bool=False, doc_name = None):
	packing_attribute_details = update_if_string_instance(packing_attribute_details)
	doc = frappe.get_cached_doc('Item Item Attribute Mapping', attribute_mapping_value)
	attributes = []
	for item in doc.values:
		attributes.append(item.attribute_value)
	
	stiching_item_details = {}
	set_item_details = {}
	is_default_list = []
	ipd_doc = None
	if doc_name:
		ipd_doc = frappe.get_doc("Item Production Detail",doc_name)
		if ipd_doc.is_set_item:
			for item in ipd_doc.stiching_item_details:
				stiching_item_details[item.stiching_attribute_value] = item.set_item_attribute_value
				if item.is_default:
					is_default_list.append(item.stiching_attribute_value)

			for item in	ipd_doc.set_item_combination_details:
				set_item_details.setdefault(item.major_attribute_value,{})
				set_item_details[item.major_attribute_value][item.set_item_attribute_value] = item.attribute_value
	
	item_detail = []
	for item in packing_attribute_details:
		item_list = {}
		item_list['major_attribute'] = item['attribute_value']
		item_list['val'] = {}
		for i in attributes:
			if i == major_attribute_value:
				item_list['val'][i] = item['attribute_value']
			elif is_same_packing_attribute:
				if doc_name and ipd_doc.is_set_item:
					part = stiching_item_details[i]
					item_list['val'][i] = set_item_details[item['attribute_value']][part]
				else:	
					item_list['val'][i] = item['attribute_value']
			elif doc_name and ipd_doc.is_set_item and i in is_default_list:
				part = stiching_item_details[i]
				item_list['val'][i] = set_item_details[item['attribute_value']][part]
			else:
				item_list['val'][i] = None	
		item_detail.append(item_list)

	item_details = {}
	item_details['attributes'] = attributes
	item_details['values'] = item_detail
	return item_details

##################       PACKING FUNCTIONS        ###################
@frappe.whitelist()
def get_mapping_attribute_values(attribute_mapping_value, attribute_no=None):
	map_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attribute_mapping_value)
	if attribute_no and len(map_doc.values) < int(attribute_no):
		frappe.throw(f"The Packing attribute number is {attribute_no} But there is only {len(map_doc.values)} attributes are available")

	attribute_value_list = []
	for index,attr in enumerate(map_doc.values):
		if not attribute_no:
			attribute_value_list.append({"stiching_attribute_value": attr.attribute_value})
		else:	
			if index > int(attribute_no) - 1:
				break
			attribute_value_list.append({'attribute_value':attr.attribute_value})
	return attribute_value_list

##################       STICHING FUNCTIONS       ###################
@frappe.whitelist()
def get_stiching_in_stage_attributes(dependent_attribute_mapping,stiching_in_stage):
	attribute_details = get_dependent_attribute_details(dependent_attribute_mapping)
	for attr in attribute_details['attr_list']:
		if attr == stiching_in_stage:
			return attribute_details['attr_list'][attr]['attributes']

##################       CUTTING FUNCTIONS        ###################
@frappe.whitelist()		
def get_combination(doc_name,attributes, combination_type, cloth_list = None):
	ipd_doc = frappe.get_doc("Item Production Detail",doc_name)

	attributes = update_if_string_instance(attributes)
	item_attributes = ipd_doc.item_attributes
	packing_attr = ipd_doc.packing_attribute
	packing_attr_details = ipd_doc.packing_attribute_details
	
	cloth_colours = []
	for pack_attr in packing_attr_details:
		cloth_colours.append(pack_attr.attribute_value)
	
	if ipd_doc.is_set_item:
		for row in ipd_doc.set_item_combination_details:
			if row.attribute_value not in cloth_colours:
				cloth_colours.append(row.attribute_value)

	item_attr_val_list = get_combination_attr_list(attributes,packing_attr, cloth_colours, item_attributes)
	part_accessory_combination = {}
	if combination_type == "Accessory":
		cloth_accessories = update_if_string_instance(ipd_doc.accessory_clothtype_json)
		accessory_list = []
		for cloth_accessory,cloth in cloth_accessories.items():
			accessory_list.append(cloth_accessory)
			if part_accessory_combination.get(cloth):
				part_accessory_combination[cloth].append(cloth_accessory)
			else:
				part_accessory_combination[cloth] = [cloth_accessory]
	else:
		cloth_list = update_if_string_instance(cloth_list)		

	stich_attr = ipd_doc.stiching_attribute
	is_set_item = ipd_doc.is_set_item
	set_attr = None
	if is_set_item:
		set_attr = ipd_doc.set_item_attribute
	pack_attr = ipd_doc.packing_attribute
	
	item_list = []
	if len(attributes) == 1:
		for attr_val in item_attr_val_list[attributes[0]]:
			if combination_type == 'Cutting':
				item_list.append({
					attributes[0]:attr_val,
					'Dia':None,
					"Weight":None,
				})
			elif combination_type == "Accessory":
				if attributes[0] == set_attr:
					x = attr_val
					if x in part_accessory_combination:
						for acc in part_accessory_combination[x]:
							item_list.append({
								attributes[0]:attr_val,
								"Accessory":acc,
								"Dia":None,
								"Weight":None
							})
				else:
					for acc in accessory_list:
						item_list.append({
							attributes[0]:attr_val,
							"Accessory": acc,
							"Dia":None,
							"Weight":None
						})
			else:
				item_list.append({
					attributes[0]:attr_val,
					"Cloth":None,
				})
	elif is_set_item and pack_attr in attributes and set_attr in attributes and stich_attr in attributes:
		x = item_attr_val_list.copy()
		del x[pack_attr]
		del x[stich_attr]

		set_data = {set_attr : {}}
		for i in item_attr_val_list[set_attr]:
			set_data[set_attr][i] = {
				pack_attr : [],
				stich_attr : []
			}

		x[set_attr] = set_data[set_attr]
		item_attr_list = x		
		item_attr_list = get_set_tri_struct(ipd_doc, item_attr_list, set_attr, pack_attr, stich_attr)
		
		set_attr_values = item_attr_list[set_attr]
		del item_attr_list[set_attr]
		
		attributes = pop_attributes(attributes, [set_attr, pack_attr, stich_attr])

		item_attr_val_list = item_attr_list
		items = get_set_tri_combination(set_attr_values, set_attr, pack_attr, stich_attr, combination_type, part_accessory_combination)
		item_list = make_comb_list(attributes, items, combination_type, item_attr_list)

		attributes.append(set_attr)
		attributes.append(pack_attr)
		attributes.append(stich_attr)

	elif is_set_item and pack_attr in attributes and set_attr in attributes and stich_attr not in attributes:
		x = item_attr_val_list.copy()
		del x[pack_attr]
		
		set_data = {set_attr : {}}
		for i in item_attr_val_list[set_attr]:
			set_data[set_attr][i] = []

		x[set_attr] = set_data[set_attr]

		item_attr_list = x	
		for i in ipd_doc.set_item_combination_details:
			if i.attribute_value not in item_attr_list[set_attr][i.set_item_attribute_value]:
				item_attr_list[set_attr][i.set_item_attribute_value].append(i.attribute_value) 

		set_attr_values = item_attr_list[set_attr]
		del item_attr_list[set_attr]

		attributes = pop_attributes(attributes, [set_attr, pack_attr])
		
		item_attr_val_list = item_attr_list
		items = get_comb_items(set_attr_values, set_attr, pack_attr, combination_type, part_accessory_combination)
		item_list = make_comb_list(attributes, items, combination_type, item_attr_list)
		attributes.append(set_attr)
		attributes.append(pack_attr)

	elif is_set_item and stich_attr in attributes and set_attr in attributes and pack_attr not in attributes:
		item_attr_list = change_attr_list(item_attr_val_list,ipd_doc.stiching_item_details,stich_attr,set_attr)
		set_attr_values = item_attr_list[set_attr]
		del item_attr_list[set_attr]
		attributes = pop_attributes(attributes, [set_attr, stich_attr])
		item_attr_val_list = item_attr_list
		items = get_comb_items(set_attr_values, set_attr, stich_attr, combination_type, part_accessory_combination)
		item_list = make_comb_list(attributes, items, combination_type, item_attr_list)
		attributes.append(set_attr)
		attributes.append(stich_attr)

	elif not is_set_item and pack_attr in attributes and stich_attr in attributes:
		item_attr_list = change_pack_stich_attr_list(item_attr_val_list, ipd_doc.stiching_item_combination_details, stich_attr, pack_attr)
		pack_attr_values = item_attr_list[pack_attr]
		del item_attr_list[pack_attr]
		attributes = pop_attributes(attributes, [pack_attr, stich_attr])
		item_attr_val_list = item_attr_list
		items = get_comb_items(pack_attr_values, stich_attr, pack_attr, combination_type, part_accessory_combination)
		item_list = make_comb_list(attributes, items, combination_type, item_attr_list)
		attributes.append(stich_attr)
		attributes.append(pack_attr)
	
	else:
		item_list = get_item_list(item_attr_val_list,attributes)
		items = []
		if is_set_item and combination_type == "Accessory":
			for item in item_list:
				if item[set_attr] in part_accessory_combination:
					for x in part_accessory_combination[item[set_attr]]:
							s = item
							s['Accessory'] = x
							m = s.copy()
							items.append(m)
		elif combination_type == "Accessory":
			for item in item_list:
				s = item
				for acc in accessory_list:
					s["Accessory"] = acc
					m = s.copy()
					items.append(m)
		else:			
			items = item_list
		for item in items:
			item = add_combination_value(combination_type,item)
		item_list = items	

	additional_attr = []

	if combination_type == 'Cutting':
		additional_attr = ['Dia', 'Weight']
	elif combination_type == "Accessory":
		additional_attr = ['Accessory','Dia','Weight']
	else:
		additional_attr = ['Cloth']	

	select_list = None
	if combination_type == "Accessory":
		select_list = accessory_list
	else:
		select_list = cloth_list	
	final_list = {
		'combination_type': combination_type,
		'attributes' : attributes + additional_attr,
		'items': item_list,
		'select_list':select_list
	}
	return final_list

def pop_attributes(attributes, attr_list):
	for attr in attr_list:
		index = attributes.index(attr)
		attributes.pop(index)
	return attributes	

def get_set_tri_struct(ipd_doc, item_attr_list, set_attr, pack_attr, stich_attr):
	for i in ipd_doc.set_item_combination_details:
		if i.attribute_value not in item_attr_list[set_attr][i.set_item_attribute_value][pack_attr]:
			item_attr_list[set_attr][i.set_item_attribute_value][pack_attr].append(i.attribute_value) 

	for i in ipd_doc.stiching_item_details:
		item_attr_list[set_attr][i.set_item_attribute_value][stich_attr].append(i.stiching_attribute_value)

	return item_attr_list	

def get_set_tri_combination(set_attr_values, set_attr, pack_attr, stich_attr, combination_type, accessory_combination):
	items = []
	for val in set_attr_values:
		s = {}
		s[set_attr] = val
		for a in set_attr_values[val][pack_attr]:
			s[pack_attr] = a
			for b in set_attr_values[val][stich_attr]:
				if combination_type == "Accessory":
					if val in accessory_combination:
						for x in accessory_combination[val]:
							s[stich_attr] = b
							s['Accessory'] = x
							m = s.copy()
							items.append(m)
				else:			
					s[stich_attr] = b
					m = s.copy()
					items.append(m)
	return items			

def get_comb_items(set_attr_values, attr1, attr2, combination_type, accessory_combination):
	items = []
	for attribute1,attribute2 in set_attr_values.items():
		for attr2_data in attribute2:
			i = {}
			if combination_type == "Accessory":
				if attribute1 in accessory_combination:
					for x in accessory_combination[attribute1]:
						i = {}
						i[attr1] = attribute1
						i[attr2] = attr2_data
						i['Accessory'] = x
						items.append(i)
			else:
				i[attr1] = attribute1
				i[attr2] = attr2_data
				items.append(i)	
	return items

def make_comb_list(attributes, items, combination_type, item_attr_list):
	item_list = []
	if len(attributes) == 0:
		for item in items:
			item = add_combination_value(combination_type,item)
		item_list = items
	else:
		item_list = get_item_list(item_attr_list,attributes)
		final_list = []
		for i in items:
			for item in item_list:
				x = item | i
				x = add_combination_value(combination_type,x)
				final_list.append(x)
		item_list = final_list
	return item_list	

def get_item_list(item_attr_list,attributes):
	attrs_len = {}
	initial_attrs = {}
	for key, val in item_attr_list.items():
		attrs_len[key] = len(val)
		initial_attrs[key] = 0
	last_item = attributes[len(attributes)-1]
	item_list = []
	check = False
	while True:
		temp = {}
		for item,item_values in item_attr_list.items():
			temp[item] = item_values[initial_attrs[item]]
			if item == last_item:
				initial_attrs[item] += 1
				if initial_attrs[item] == attrs_len[item]:
					initial_attrs = update_attr_combination(initial_attrs, attributes, last_item, attrs_len)
			if initial_attrs == None:
				check = True
		item_list.append(temp)
		if check:
			break
	return item_list	

def change_attr_list(item_attr_val_list, stiching_item_details, stiching_attr, set_attr):
	attr_list = item_attr_val_list.copy()
	stiching_details = {}
	for item in stiching_item_details:
		if stiching_details.get(item.set_item_attribute_value):
			stiching_details[item.set_item_attribute_value].append(item.stiching_attribute_value)
		else:
			stiching_details[item.set_item_attribute_value] = [item.stiching_attribute_value]	

	del attr_list[stiching_attr]
	attr_list[set_attr] = stiching_details
	return attr_list

def change_pack_stich_attr_list(item_attr_val_list, stiching_item_combination_details, stiching_attr, pack_attr):
	attr_list = item_attr_val_list.copy()
	panel_details = {}
	for item in stiching_item_combination_details:
		panel_details.setdefault(item.set_item_attribute_value, [])
		if item.attribute_value not in panel_details[item.set_item_attribute_value]:
			panel_details[item.set_item_attribute_value].append(item.attribute_value)
	del attr_list[stiching_attr]
	attr_list[pack_attr] = panel_details
	return attr_list

def add_combination_value(combination_type,item):
	if combination_type == 'Cutting':			
		item['Dia'] = None
		item['Weight'] = None
	elif combination_type == 'Cloth':
		item['Cloth'] = None
	else:
		item['Dia'] = None
		item['Weight'] = None	
	return item

@frappe.whitelist()
def get_stiching_accessory_combination(cloth_list, doc_name):
	ipd_doc = frappe.get_doc("Item Production Detail",doc_name)
	combination_list = {}
	combination_list['select_list'] = cloth_list
	combination_list['attributes'] = []
	combination_list['items'] = []
	cloth_accessories = update_if_string_instance(ipd_doc.accessory_clothtype_json)
	if ipd_doc.is_set_item:
		combination_list['is_set_item'] = 1
		combination_list['set_attr'] = ipd_doc.set_item_attribute
		combination_list['attributes'] = ["Accessory", ipd_doc.set_item_attribute, "Major Colour", "Accessory Colour","Cloth"]
		part_colours = {}
		set_colours = {}
		for row in ipd_doc.set_item_combination_details:
			set_colours.setdefault(row.index,{})
			set_colours[row.index][row.set_item_attribute_value] = row.attribute_value
			part_colours.setdefault(row.set_item_attribute_value, [])
			part_colours[row.set_item_attribute_value].append(row.attribute_value)
		for accessory, part in cloth_accessories.items():
			d = {
				"accessory" : accessory,
				ipd_doc.set_item_attribute : part,
			}
				
			for idx, colour in enumerate(part_colours[part]):
				d["major_colour"] = colour
				d['accessory_colour'] = None
				d['cloth_type'] = None 
				if part != ipd_doc.major_attribute_value:
					d['major_attr_value'] = set_colours[idx][ipd_doc.major_attribute_value]
				m = d.copy()
				combination_list['items'].append(m)
	else:
		combination_list['is_set_item'] = 0
		combination_list['attributes'] = ["Accessory", "Major Colour", "Accessory Colour","Cloth"]
		colours = []
		for row in ipd_doc.packing_attribute_details:
			colours.append(row.attribute_value)

		for accessory, part in cloth_accessories.items():
			d = {
				"accessory" : accessory,
			}
			for colour in colours:
				d["major_colour"] = colour
				d['accessory_colour'] = None
				d['cloth_type'] = None 
				m = d.copy()
				combination_list['items'].append(m)
	return combination_list		

def get_combination_attr_list(attributes, packing_attr, pack_details, item_attributes):
	item_attr_value_list = {}
	for item in item_attributes:
		if item.attribute in attributes:
			attr_details = get_attr_mapping_details(item.mapping)
			item_attr_value_list[item.attribute] = attr_details
	item_attr_value_list[packing_attr] = pack_details
	item_attr_val_list = {}
	for attr in attributes:
		item_attr_val_list[attr] = item_attr_value_list[attr]

	return item_attr_val_list	

def update_attr_combination(initial_attrs, attributes, last_item, attrs_len):
	for i in range(len(attributes)-1, -1, -1):
		if not attributes[i] == last_item:
			index = initial_attrs[attributes[i]]
			index = index + 1
			if index < attrs_len[attributes[i]]:
				initial_attrs[attributes[i]] = index
				for j in range(len(attributes)-1, -1, -1):
					if attributes[j] == attributes[i]:
						return initial_attrs
					else:
						initial_attrs[attributes[j]] = 0
	return None					

@frappe.whitelist()
def get_attr_mapping_details(mapping):
	doc = frappe.get_cached_doc('Item Item Attribute Mapping', mapping)
	values = []
	for item in doc.values:
		values.append(item.attribute_value)
	return values

@frappe.whitelist()
def get_ipd_variant(item_variants, item_name, tup):
	str_tup = str(tup)
	return item_variants[item_name][str_tup]

@frappe.whitelist()
def get_ipd_pf_details(ipd):
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	return ipd_doc

@frappe.whitelist()
def duplicate_ipd(ipd):
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	doc = frappe.new_doc("Item Production Detail")
	doc.update({
		"item": ipd_doc.item,
		"tech_pack_version": ipd_doc.tech_pack_version,
		"pattern_version": ipd_doc.pattern_version,
		"primary_item_attribute": ipd_doc.primary_item_attribute,
		"dependent_attribute": ipd_doc.dependent_attribute,
		"dependent_attribute_mapping": ipd_doc.dependent_attribute_mapping,
		"packing_process": ipd_doc.packing_process,
		"packing_attribute": ipd_doc.packing_attribute,
		"pack_in_stage": ipd_doc.pack_in_stage,
		"pack_out_stage": ipd_doc.pack_out_stage,
		"packing_combo": ipd_doc.packing_combo,
		"packing_attribute_no": ipd_doc.packing_attribute_no,
		"auto_calculate": ipd_doc.auto_calculate,
		"stiching_process": ipd_doc.stiching_process,
		"stiching_in_stage": ipd_doc.stiching_in_stage,
		"stiching_attribute": ipd_doc.stiching_attribute,
		"stiching_out_stage": ipd_doc.stiching_out_stage,
		"stiching_major_attribute_value": ipd_doc.stiching_major_attribute_value,
		"is_same_packing_attribute": ipd_doc.is_same_packing_attribute,
		"cutting_process": ipd_doc.cutting_process,
		"emblishment_details_json": ipd_doc.emblishment_details_json, 
		"cutting_cloths_json": ipd_doc.cutting_cloths_json,
		"cutting_items_json": ipd_doc.cutting_items_json,
		"cloth_accessory_json": ipd_doc.cloth_accessory_json,
		"stiching_accessory_json": ipd_doc.stiching_accessory_json,
		"accessory_clothtype_json": ipd_doc.accessory_clothtype_json,
	})

	doc.set("item_attributes", get_dict_table(ipd_doc.item_attributes))
	# doc.set("item_bom", get_dict_table(ipd_doc.item_bom))
	doc.set("ipd_processes", get_dict_table(ipd_doc.ipd_processes))
	doc.set("packing_attribute_details", get_dict_table(ipd_doc.packing_attribute_details))
	doc.set("stiching_item_details", get_dict_table(ipd_doc.stiching_item_details))
	doc.set("stiching_item_combination_details", get_dict_table(ipd_doc.stiching_item_combination_details))
	doc.set("cutting_attributes", get_dict_table(ipd_doc.cutting_attributes))
	doc.set("cloth_detail", get_dict_table(ipd_doc.cloth_detail))
	doc.set("accessory_attributes", get_dict_table(ipd_doc.accessory_attributes))
	doc.set("cloth_attributes", get_dict_table(ipd_doc.cloth_attributes))
	doc.save()
	if ipd_doc.is_set_item: 
		doc.update({
			"is_set_item": ipd_doc.is_set_item,
			"set_item_attribute": ipd_doc.set_item_attribute,
			"major_attribute_value": ipd_doc.major_attribute_value,
		})
		doc.set("set_item_combination_details", ipd_doc.set_item_combination_details)
		doc.save()

	items = []
	for row1 in ipd_doc.item_bom:
		d = {
			"item": row1.item,
			"process_name": row1.process_name,
			"dependent_attribute_value": row1.dependent_attribute_value,
			"qty_of_product": row1.qty_of_product,
			"qty_of_bom_item": row1.qty_of_bom_item,
			"based_on_attribute_mapping": 0,
			"attribute_mapping": None,
		}
		if row1.based_on_attribute_mapping:
			d['based_on_attribute_mapping'] = 1
		items.append(d)
	doc.set("item_bom", items)
	doc.save()		

	for item1, item2 in zip_longest(ipd_doc.item_bom, doc.item_bom):
		if item1.based_on_attribute_mapping and item1.attribute_mapping:
			bom_doc = frappe.get_doc("Item BOM Attribute Mapping", item1.attribute_mapping)
			new_bom_doc = frappe.copy_doc(bom_doc)
			new_bom_doc.item_production_detail = doc.name
			new_bom_doc.insert()
			item2.attribute_mapping = new_bom_doc.name
	
	doc.save()

	return doc.name

def get_dict_table(table_data):
	items = [row.as_dict() for row in table_data]
	return items