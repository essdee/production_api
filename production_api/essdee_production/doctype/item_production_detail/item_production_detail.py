# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
import math
from frappe.model.document import Document
from frappe.utils import now_datetime
from six import string_types
from itertools import groupby
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details
from production_api.essdee_production.doctype.lot.lot import get_uom_conversion_factor

class ItemProductionDetail(Document):
	def autoname(self):
		item = self.item
		version = frappe.db.sql(
			f"""
				Select max(version) as max_version from `tabItem Production Detail` where item = '{item}'
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
			attribute_doc = frappe.get_doc("Item Attribute", attribute.attribute)
			if not attribute_doc.numeric_values:
				if attribute.mapping != None:
					doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
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
				doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
				bom_attribute_list.append({
					'bom_item': bom.item,
					'bom_attr_mapping_link': bom.attribute_mapping,
					'bom_attr_mapping_based_on': bom.based_on_attribute_mapping,
					'bom_attr_mapping_list': doc.values,
					'doctype': 'Item BOM Attribute Mapping'
				})
		self.set_onload('bom_attr_list', bom_attribute_list)

	def load_dependent_attribute(self):
		"""Load Dependent Attribute Detail into `__onload`"""
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
			dict_values = {
				"packing_process" : "Packing",
				"pack_in_stage" : "Piece",
				"pack_out_stage" : "Pack",
				"packing_attribute" : "Color",
				"stiching_process" : "Stiching",
				"stiching_attribute" : "Panel",
				"stiching_in_stage" : "Cut",
				"stiching_out_stage" : "Piece",
				"cutting_process" : "Cutting",
			}
			self.packing_process = dict_values['packing_process']
			self.pack_in_stage = dict_values['pack_in_stage']
			self.pack_out_stage = dict_values['pack_out_stage']
			self.packing_attribute = dict_values['packing_attribute']
			self.stiching_process = dict_values['stiching_process']
			self.stiching_attribute = dict_values['stiching_attribute']
			self.stiching_in_stage = dict_values['stiching_in_stage']
			self.stiching_out_stage = dict_values['stiching_out_stage']
			self.cutting_process = dict_values['cutting_process']	
	
	def before_validate(self):
		if self.get('set_item_detail'):
			set_details = save_item_details(self.set_item_detail)
			self.set('set_item_combination_details', set_details)

		if self.get('stiching_item_detail'):
			stiching_detail = save_item_details(self.stiching_item_detail,doc_name = self.name)
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
		cut_json = self.cutting_cloths_json
		if isinstance(cut_json, string_types):
			cut_json = json.loads(cut_json)

		if cut_json:
			cut_json['select_list'] = cloths		
		self.cutting_cloths_json = cut_json

		if self.is_set_item:
			mapping = None
			for item in self.item_attributes:
				if item.attribute == self.set_item_attribute:
					mapping = item.mapping
					break
			map_doc = frappe.get_doc("Item Item Attribute Mapping",mapping)
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
				doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
				duplicate_doc = frappe.new_doc("Item Item Attribute Mapping")
				duplicate_doc.attribute_name = doc.attribute_name
				duplicate_doc.values = doc.values
				duplicate_doc.save()
				attribute.mapping = duplicate_doc.name

		if self.dependent_attribute_mapping:
			doc = frappe.get_doc('Item Dependent Attribute Mapping',self.dependent_attribute_mapping)		
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
				duplicate_doc = frappe.new_doc("Item BOM Attribute Mapping")
				duplicate_doc.item = self.item
				duplicate_doc.bom_item = bom.item
				duplicate_doc.save()
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

		for bom in self.get('item_bom'):
			if bom.based_on_attribute_mapping and not bom.attribute_mapping:
				doc = frappe.new_doc("Item BOM Attribute Mapping")
				doc.item_production_detail = self.name
				doc.item = self.item
				doc.bom_item = bom.item

				attr_values = []
				item_doc = frappe.get_doc("Item",bom.item)
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
				frappe.delete_doc("Item BOM Attribute Mapping", name)
	
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

		map_doc = frappe.get_doc("Item Item Attribute Mapping", mapping)
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

		if self.is_set_item and self.set_item_attribute not in accessory_attributes and len(accessory_attributes) > 0:
			frappe.throw(f"{self.set_item_attribute} should be in the Accessory Combination")

		if not self.is_same_packing_attribute and self.stiching_attribute not in ipd_cutting_attributes and len(ipd_cutting_attributes) > 0:
			frappe.throw(f"{self.stiching_attribute} Should be in Cutting Combination")

		if self.stiching_attribute in ipd_cloth_attributes and self.stiching_attribute not in ipd_cutting_attributes:
			frappe.throw(f"Please mention the {self.stiching_attribute} in Cutting Combination")

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
@frappe.validate_and_sanitize_search_inputs
def get_item_attributes(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute' or filters['item_production_detail'] == None):
		return []

	item_production_detail_name = filters['item_production_detail']
	item_production_detail = frappe.get_doc("Item Production Detail", item_production_detail_name)
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
def get_attribute_values(item_production_detail, attributes = None):
	lot = frappe.get_doc("Item Production Detail", item_production_detail)
	attribute_values = {}

	if not attributes:
		attributes = [attr.attribute for attr in lot.item_attributes]

	for attribute in lot.item_attributes:
		if attribute.attribute in attributes and attribute.mapping != None:
			doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
			attribute_values[attribute.attribute] = [d.attribute_value for d in doc.values]

	return attribute_values

@frappe.whitelist()
def get_calculated_bom(item_production_detail, items, lot_name, process_name = None):
	item_detail = frappe.get_doc("Item Production Detail", item_production_detail)
	bom = {}
	bom_summary = {}
	if isinstance(items, string_types):
		items = json.loads(items)
	if len(items) == 0:
		return
	lot_doc = frappe.get_doc("Lot", lot_name)
	cloth_combination = get_cloth_combination(item_detail)
	stitching_combination = get_stitching_combination(item_detail)
	bom_combination = get_bom_combination(item_detail.item_bom)
	cloth_detail = {}
	for cloth in item_detail.cloth_detail:
		if cloth.is_bom_item:
			cloth_detail[cloth.name1] = cloth.cloth

	total_quantity = lot_doc.total_order_quantity

	for bom_item in item_detail.item_bom:
		if process_name and bom_item.process_name != process_name:
			continue
		if not bom_item.based_on_attribute_mapping:
			bom[bom_item.item] = {}
			qty_of_product = bom_item.qty_of_product
			qty_of_bom = bom_item.qty_of_bom_item
			
			bom_item_doc = None
			if bom_item.dependent_attribute_value and not bom_item.dependent_attribute_value == lot_doc.pack_in_stage:
				bom_item_doc, qty_of_product = get_doc_uom_conversion(lot_doc,bom_item)

			qty_of_product = qty_of_product/qty_of_bom
			uom = get_bom_uom(bom_item,item_detail,bom_item_doc)

			quantity = total_quantity / qty_of_product
			if not bom[bom_item.item].get(bom_item.item, False):
				bom[bom_item.item][bom_item.item] = [math.ceil(quantity),bom_item.process_name, uom]
			else:
				bom[bom_item.item][bom_item.item][0] += math.ceil(quantity)
	
	mapping_bom = {}
	cloth_details = {}
	
	for item in items:
		qty = item['quantity']
		if not qty:
			continue
		variant = item['item_variant']
		attr_values = {}
		variant_doc = frappe.get_doc("Item Variant", variant)

		for x in variant_doc.attributes:
			attr_values[x.attribute] = x.attribute_value
		
		for bom_item in item_detail.item_bom:
			if process_name and bom_item.process_name != process_name:
				continue
			if bom_item.based_on_attribute_mapping:
				if not bom_summary.get(bom_item.item,False):
					dept_attr = bom_item.dependent_attribute_value
					attr_details = get_dependent_attribute_details(item_detail.dependent_attribute_mapping)
					dept_attr_uom = attr_details['attr_list'][dept_attr]['uom']
					default_uom = frappe.get_cached_value("Item",bom_item.item,"default_unit_of_measure")
					bom_summary[bom_item.item] = [bom_item.process_name,bom_item.qty_of_product,dept_attr_uom,bom_item.qty_of_bom_item,default_uom,0]
				
				if not bom.get(bom_item.item, False):
					bom[bom_item.item] = {}

				qty_of_product = bom_item.qty_of_product
				qty_of_bom = bom_item.qty_of_bom_item
				
				bom_item_doc = None
				if bom_item.dependent_attribute_value and not bom_item.dependent_attribute_value == lot_doc.pack_in_stage:
					bom_item_doc, qty_of_product = get_doc_uom_conversion(lot_doc,bom_item)

				qty_of_product = qty_of_product/qty_of_bom
				uom = get_bom_uom(bom_item,item_detail,bom_item_doc)

				if not mapping_bom.get(bom_item.item,False):
					mapping_bom[bom_item.item] = {}
				
				xattr_values = {}
				for x in bom_combination[bom_item.item]["keys"]:
					if attr_values.get(x):
						xattr_values[x] = attr_values[x]

				quantity = qty / qty_of_product
				for key, val in bom_combination[bom_item.item].items():
					if key != "keys" and key != "same_attributes" and xattr_values == val["key"]:
						attr = val["value"].copy()
						for x in bom_combination[bom_item.item]["same_attributes"]: 
							attr[x] = attr_values[x]
						if not mapping_bom[bom_item.item].get(str(attr), False):
							mapping_bom[bom_item.item][str(attr)] = [math.ceil(quantity),bom_item.process_name, uom]
						else:
							mapping_bom[bom_item.item][str(attr)][0] += math.ceil(quantity)

		if item_detail.dependent_attribute:
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
			uom = frappe.get_cached_value("Item",k[0],"default_unit_of_measure")
			cloth_name = get_or_create_variant(k[0], {item_detail.packing_attribute: k[1], 'Dia': k[2]})
			if not bom.get(k[0],False):
				bom[k[0]] = {cloth_name:[cloth_details[k],item_detail.cutting_process,uom]}
			else:	
				bom[k[0]][cloth_name] = [cloth_details[k],item_detail.cutting_process,uom]

	for key,value in mapping_bom.items():
		for k,val in value.items():
			k = k.replace("'", '"')
			k = json.loads(k)
			variant = get_or_create_variant(key,k)
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
def get_bom_uom(bom_item,item_detail,bom_item_doc):
	uom = None
	if not bom_item.dependent_attribute_value or not item_detail.dependent_attribute:
		uom = bom_item_doc.default_unit_of_measure
	else:
		attribute_details = get_dependent_attribute_details(item_detail.dependent_attribute_mapping)
		uom = attribute_details['attr_list'][bom_item.dependent_attribute_value]['uom']
	return uom

def get_doc_uom_conversion(lot_doc,bom_item):
	dependent_attr_uom = get_uom(lot_doc.dependent_attribute_mapping,bom_item.dependent_attribute_value)
	bom_item_doc = frappe.get_cached_doc("Item", bom_item.item)
	bom_item_conv = get_uom_conversion_factor(bom_item_doc.uom_conversion_details, dependent_attr_uom ,lot_doc.packing_uom)
	qty_of_product = bom_item_conv
	return bom_item_doc,qty_of_product

def calculate_cloth(ipd_doc, variant_attrs, qty, cloth_combination, stitching_combination):
	attrs = variant_attrs.copy()
	if stitching_combination["stitching_attribute"] in cloth_combination["cloth_attributes"] and stitching_combination["stitching_attribute"] not in cloth_combination["cutting_attributes"]:
		frappe.throw(f"Cannot calculate cloth quantity without {stitching_combination['stitching_attribute']} in Cloth Weight Combination.")
	cloth_detail = []

	if stitching_combination["stitching_attribute"] in cloth_combination["cutting_attributes"]:
		for stiching_attr,attr_qty in stitching_combination["stitching_attribute_count"].items():
			attrs[ipd_doc.stiching_attribute] = stiching_attr
			if cloth_combination["cutting_combination"].get(get_key(attrs, cloth_combination["cutting_attributes"])):
				dia, weight = cloth_combination["cutting_combination"][get_key(attrs, cloth_combination["cutting_attributes"])]	
				cloth_type = cloth_combination["cloth_combination"][get_key(attrs, cloth_combination["cloth_attributes"])]
				weight = weight * qty * attr_qty
				cloth_colour = stitching_combination["stitching_combination"][attrs[ipd_doc.packing_attribute]][stiching_attr]
				cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,cloth_type,cloth_colour,dia,"cloth"))
	else:
		dia, weight = cloth_combination["cutting_combination"][get_key(attrs, cloth_combination["cutting_attributes"])]
		cloth_type = cloth_combination["cloth_combination"][get_key(attrs, cloth_combination["cloth_attributes"])]
		weight = weight * qty
		cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,cloth_type,attrs[ipd_doc.packing_attribute],dia,"cloth"))

	cloth_accessory_json = ipd_doc.accessory_clothtype_json
	if isinstance(cloth_accessory_json,string_types):
		cloth_accessory_json = json.loads(cloth_accessory_json)

	if ipd_doc.stiching_attribute in cloth_combination["accessory_attributes"] and cloth_accessory_json:
		for stiching_attr, attr_qty in stitching_combination["stitching_attribute_count"].items():
			attrs[ipd_doc.stiching_attribute] = stiching_attr
			for accessory_name, accessory_cloth in cloth_accessory_json.items():
				attrs["Accessory"] = accessory_name
				if cloth_combination["accessory_combination"].get(get_key(attrs, cloth_combination["accessory_attributes"])):
					accessory_weight = cloth_combination["accessory_combination"][get_key(attrs, cloth_combination["accessory_attributes"])]
					accessory_colour = get_accessory_colour(ipd_doc,attrs,accessory_name)
					weight = accessory_weight * qty * attr_qty
					cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,accessory_cloth,accessory_colour,dia,"accessory"))
	elif cloth_accessory_json:
		for accessory_name, accessory_cloth in cloth_accessory_json.items():
			attrs["Accessory"] = accessory_name
			accessory_weight = cloth_combination["accessory_combination"][get_key(attrs, cloth_combination["accessory_attributes"])]
			accessory_colour = get_accessory_colour(ipd_doc,attrs,accessory_name)	
			weight = accessory_weight * qty
			cloth_detail.append(add_cloth_detail(weight, ipd_doc.additional_cloth,accessory_cloth,accessory_colour,dia,"accessory"))
	return cloth_detail

def get_bom_combination(bom_items):
	if isinstance(bom_items,string_types):
		bom_items = json.loads(bom_items)
	bom_combination = {}
	for bom_item in bom_items:
		if bom_item.based_on_attribute_mapping:
			attr_doc = frappe.get_doc("Item BOM Attribute Mapping",bom_item.attribute_mapping)
			bom_combination[bom_item.item] = {"keys":[],"same_attributes":[]}
			for i in attr_doc.item_attributes:
				if not i.same_attribute:
					bom_combination[bom_item.item]["keys"].append(i.attribute)
				else:
					bom_combination[bom_item.item]["same_attributes"].append(i.attribute)	
			c = {}
			for item in attr_doc.values:
				if c.get(item.index):
					if item.type == 'item':
						c[item.index]["key"] = c[item.index]["key"]|{item.attribute:item.attribute_value}
					else:
						c[item.index]["value"] = c[item.index]["value"]|{item.attribute:item.attribute_value}	
				else:
					c[item.index] = {"key":{},"value":{}}
					c[item.index]["key"] = {item.attribute:item.attribute_value}	
			bom_combination[bom_item.item] = bom_combination[bom_item.item] | c
		else:
			bom_combination[bom_item.item] = {}
	return bom_combination

def add_cloth_detail(weight, additional_cloth,cloth_type,cloth_colour,dia,type):
	x = get_additional_cloth(weight, additional_cloth)
	weight = weight + x
	return {
		"cloth_type": cloth_type,
		"colour": cloth_colour,
		"dia": dia,
		"quantity": weight,
		"type":type
	}

def get_accessory_colour(ipd_doc,variant_attrs,accessory):
	if ipd_doc.is_set_item:
		panel = None
		part = variant_attrs[ipd_doc.set_item_attribute]
		for item in ipd_doc.stiching_item_details:
			if item.set_item_attribute_value == part and item.is_default == 1:
				panel = item.stiching_attribute_value
				break
		for acce in json.loads(ipd_doc.stiching_accessory_json)["items"]:
			if acce.get(panel):
				if acce[panel] == variant_attrs[ipd_doc.packing_attribute]:
					return acce[accessory]
	else:
		for acce in json.loads(ipd_doc.stiching_accessory_json)["items"]:
			if acce[ipd_doc.stiching_major_attribute_value] == variant_attrs[ipd_doc.packing_attribute]:
				return acce[accessory]

def get_additional_cloth(weight, additional_cloth):
	if additional_cloth:
		x = weight/100
		return  x * additional_cloth
	return 0.0

def get_uom(dependent_attribute_mapping,dependent_attribute_value):
	dept_attr_details = get_dependent_attribute_details(dependent_attribute_mapping)
	for attr in dept_attr_details['attr_list']:
		if attr == dependent_attribute_value:
			return dept_attr_details['attr_list'][attr]['uom']

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
			accessory_combination[get_key(item, accessory_attributes)] = (item["Weight"])

	return {
		"cutting_attributes": cutting_attributes,
		"cloth_attributes": cloth_attributes,
		"accessory_attributes":accessory_attributes,
		"cutting_combination": cutting_combination,
		"cloth_combination": cloth_combination,
		"accessory_combination":accessory_combination,
	}

def get_stitching_combination(ipd_doc):
	stitching_combination = {}
	for detail in ipd_doc.stiching_item_combination_details:
		stitching_combination.setdefault(detail.major_attribute_value, {})
		stitching_combination[detail.major_attribute_value][detail.set_item_attribute_value] = detail.attribute_value

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

def save_item_details(combination_item_detail, doc_name = None):
	if isinstance(combination_item_detail, string_types):
		combination_item_detail = json.loads(combination_item_detail)
	item_detail = []
	ipd_doc = None
	if doc_name:
		d = {}
		f = {}
		ipd_doc = frappe.get_doc("Item Production Detail",doc_name)
		if ipd_doc.is_set_item:
			for i in ipd_doc.stiching_item_details:
				if d.get(i.set_item_attribute_value):
					d[i.set_item_attribute_value].append(i.stiching_attribute_value)
				else:
					d[i.set_item_attribute_value] = [i.stiching_attribute_value]	
			for i in ipd_doc.set_item_combination_details:
				if f.get(i.set_item_attribute_value):
					if i.attribute_value not in f[i.set_item_attribute_value]:
						f[i.set_item_attribute_value].append(i.attribute_value)
				else:
					f[i.set_item_attribute_value] = [i.attribute_value]		

	for idx,item in enumerate(combination_item_detail['values']):
		for value in item['val']:
			row = {}
			row['index'] = idx
			row['major_attribute_value'] = item['major_attribute']
			row['set_item_attribute_value'] = value
			row['attribute_value'] = item['val'][value]
			if ipd_doc and ipd_doc.is_set_item:
				attr_val = item['major_attribute']
				part = None
				for m in d:
					if value in d[m]:
						part = m
						break
				if attr_val not in f[part]:
					row['major_attribute_value'] = f[part][0]
			item_detail.append(row)
	return item_detail	

@frappe.whitelist()
def get_new_combination(attribute_mapping_value, packing_attribute_details, major_attribute_value, is_same_packing_attribute:bool=False):
	if isinstance(packing_attribute_details, string_types):
		packing_attribute_details = json.loads(packing_attribute_details)
	doc = frappe.get_doc('Item Item Attribute Mapping', attribute_mapping_value)
	attributes = []
	for item in doc.values:
		attributes.append(item.attribute_value)
	item_detail = []
	for item in packing_attribute_details:
		item_list = {}
		item_list['major_attribute'] = item['attribute_value']
		item_list['val'] = {}
		for i in attributes:
			if i == major_attribute_value:
				item_list['val'][i] = item['attribute_value']
			elif is_same_packing_attribute:
				item_list['val'][i] = item['attribute_value']
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
	map_doc = frappe.get_doc("Item Item Attribute Mapping", attribute_mapping_value)
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
def get_combination(doc_name,attributes, combination_type):
	ipd_doc = frappe.get_doc("Item Production Detail",doc_name)

	attributes = json.loads(attributes)
	item_attributes = ipd_doc.item_attributes
	cloth_detail = ipd_doc.cloth_detail
	packing_attr = ipd_doc.packing_attribute
	packing_attr_details = ipd_doc.packing_attribute_details
	cloth_accessories = ipd_doc.accessory_clothtype_json
	
	if isinstance(item_attributes, string_types):
		item_attributes = json.loads(item_attributes)
	if isinstance(packing_attr_details, string_types):
		packing_attr_details = json.loads(packing_attr_details)

	item_attr_val_list = get_combination_attr_list(attributes,packing_attr, packing_attr_details, item_attributes)
	
	if combination_type == "Accessory":
		if isinstance(cloth_accessories, string_types):
			cloth_accessories = json.loads(cloth_accessories)	
		attributes.append("Accessory")
		accessory_list = []
		for cloth_accessory,cloth in cloth_accessories.items():
			accessory_list.append(cloth_accessory)
			
		item_attr_val_list['Accessory'] = accessory_list	
	else:		
		cloth_detail = ipd_doc.cloth_detail
		if isinstance(cloth_detail, string_types):
			cloth_detail = json.loads(cloth_detail)

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
				item_list.append({
					attributes[0]:attr_val,
					"Weight":None
				})
			else:
				item_list.append({
					attributes[0]:attr_val,
					"Cloth":None,
				})
	elif ipd_doc.is_set_item and ipd_doc.stiching_attribute in attributes and ipd_doc.set_item_attribute in attributes:
		item_attr_list = change_attr_list(item_attr_val_list,ipd_doc.stiching_item_details,ipd_doc.stiching_attribute,ipd_doc.set_item_attribute)
		set_attr_values = item_attr_list[ipd_doc.set_item_attribute]
		del item_attr_list[ipd_doc.set_item_attribute]
		
		index1 = attributes.index(ipd_doc.set_item_attribute)
		attributes.pop(index1)
		index1 = attributes.index(ipd_doc.stiching_attribute)
		attributes.pop(index1)
		item_attr_val_list = item_attr_list
		
		items = []
		for part,panels in set_attr_values.items():
			for panel in panels:
				i = {}
				i[ipd_doc.set_item_attribute] = part
				i[ipd_doc.stiching_attribute] = panel
				items.append(i)	

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

		attributes.append(ipd_doc.set_item_attribute)
		attributes.append(ipd_doc.stiching_attribute)		
	else:
		item_list = get_item_list(item_attr_val_list,attributes)
		for item in item_list:
			item = add_combination_value(combination_type,item)

	cloths = []
	for cloth in cloth_detail:
		cloths.append(cloth.name1)
	additional_attr = []

	if combination_type == 'Cutting':
		additional_attr = ['Dia', 'Weight']
	elif combination_type == "Accessory":
		additional_attr = ['Weight']
	else:
		additional_attr = ['Cloth']	

	select_list = None
	if combination_type == "Accessory":
		select_list = accessory_list
	else:
		select_list = cloths	

	final_list = {
		'combination_type': combination_type,
		'attributes' : attributes + additional_attr,
		'items': item_list,
		'select_list':select_list
	}
	return final_list

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

def add_combination_value(combination_type,item):
	if combination_type == 'Cutting':			
		item['Dia'] = None
		item['Weight'] = None
	elif combination_type == 'Cloth':
		item['Cloth'] = None
	else:
		item['Weight'] = None	
	return item

@frappe.whitelist()
def get_stiching_accessory_combination(doc_name):
	ipd_doc = frappe.get_doc("Item Production Detail",doc_name)
	combination_list = {}
	combination_list['combination_type'] = "Stiching Accessory"
	combination_list['attributes'] = []
	combination_list['attributes'].append(ipd_doc.stiching_major_attribute_value)
	x = ipd_doc.accessory_clothtype_json
	if isinstance(x,string_types):
		x = json.loads(x)

	for key,val in x.items():
		combination_list['attributes'].append(key)
	combination_list['items'] = []

	colors = []
	for stich_item in ipd_doc.stiching_item_combination_details:
		if stich_item.attribute_value not in colors:
			new_dict = {}
			new_dict[stich_item.set_item_attribute_value] = stich_item.major_attribute_value
			for key,val in x.items():
				new_dict[key] = None
			combination_list['items'].append(new_dict)
			colors.append(stich_item.attribute_value)
	
	return combination_list		

def get_combination_attr_list(attributes, packing_attr, packing_attr_details, item_attributes):
	item_attr_value_list = {}
	pack_details = []
	for pack_attr in packing_attr_details:
		pack_details.append(pack_attr.attribute_value)

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

def get_attr_mapping_details(mapping):
	doc = frappe.get_doc('Item Item Attribute Mapping', mapping)
	values = []
	for item in doc.values:
		values.append(item.attribute_value)
	return values
