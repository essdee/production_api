# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe, json
import math
from frappe.model.document import Document
from frappe.utils import flt, now_datetime
from six import string_types
from itertools import groupby
from production_api.production_api.doctype.item.item import get_or_create_variant
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details
from production_api.essdee_production.doctype.lot.lot import get_uom_conversion_factor
class ItemProductionDetail(Document):
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
		
	def before_validate(self):
		if self.get('set_item_detail'):
			set_details = save_item_details(self.set_item_detail)
			self.set('set_item_combination_details', set_details)

		if self.get('stiching_item_detail'):
			stiching_detail = save_item_details(self.stiching_item_detail)
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
		if self.stiching_attribute_quantity == 0:
			frappe.throw("Stiching Attribute Quantity should not be zero")
		
		if len(self.stiching_item_details) == 0:
			frappe.throw("Enter stiching attribute details")

		attr= set()
		sum = 0.0
		
		for row in self.stiching_item_details:
			if not row.quantity:
				frappe.throw("Enter value in Stiching Item Details, Zero is not considered as a valid quantity")
			sum = sum + row.quantity
			attr.add(row.stiching_attribute_value)

		if sum != self.stiching_attribute_quantity:
			frappe.throw(f"In Stiching Item Details, the sum of quantity should be {self.stiching_attribute_quantity}")

		if len(attr) != len(self.stiching_item_details):
			frappe.throw("Duplicate Attribute values are occured in Stiching Item Details")	
	
	def cutting_tab_validations(self):
		ipd_cloth_attributes = []
		for item in self.cloth_attributes:
			ipd_cloth_attributes.append(item.attribute)

		if self.is_same_packing_attribute:
			for item in self.stiching_item_combination_details:
				item.attribute_value = item.major_attribute_value

		for item in self.cutting_attributes:
			ipd_cloth_attributes.append(item.attribute)

		if self.packing_attribute not in ipd_cloth_attributes:
			frappe.throw("Packing Attribute not in the cloth combination")

		if self.primary_item_attribute not in ipd_cloth_attributes:
			frappe.throw("Primary Attribute not in the cloth combination")

		if not self.is_same_packing_attribute and self.stiching_attribute not in ipd_cloth_attributes:
			frappe.throw("Stiching Attribute not in the cloth combination")

	def validate(self):
		if self.get('__islocal'):
			self.create_new_mapping_values()

		self.update_mapping_values()		

		if not self.is_new():
			self.packing_tab_validations()			
			self.stiching_tab_validations()
			# self.cutting_tab_validations()		
			
			
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
def get_calculated_bom(item_production_detail, items, lot_name, process_name = None, from_uom = None, to_uom = None):
	item_detail = frappe.get_doc("Item Production Detail", item_production_detail)
	bom = {}
	if isinstance(items, string_types):
		items = json.loads(items)
	lot_doc = frappe.get_doc("Lot", lot_name)
	pack_out_stage = lot_doc.pack_out_stage
	pack_in_stage = lot_doc.pack_in_stage
	cloth_combination = get_cloth_combination(item_detail)

	cloth_detail = {}
	for cloth in item_detail.cloth_detail:
		if cloth.is_bom_item:
			cloth_detail[cloth.name1] = cloth.cloth

	cut_attrs_list = []	
	for cut_attrs in item_detail.cutting_attributes:
		cut_attrs_list.append(cut_attrs.attribute)

	if len(items) == 0:
		return
	for item in items:
		qty = item['qty']
		if not qty:
			continue
		variant = item['item_variant']
		attr_values = {}
		variant_doc = frappe.get_doc("Item Variant", variant)
		item_name = variant_doc.item
		doc = frappe.get_doc("Item", item_name)
		og_uom_factor_to_piece = None
		uom_factor = None
		if from_uom and to_uom:
			og_uom_factor_to_piece = get_uom_conversion_factor(doc.uom_conversion_details,from_uom,to_uom)	
			uom_factor = get_uom_conversion_factor(doc.uom_conversion_details,from_uom,to_uom)
		else:	
			og_uom_factor_to_piece = get_uom_conversion_factor(doc.uom_conversion_details,lot_doc.uom,lot_doc.packing_uom)	
			uom_factor = get_uom_conversion_factor(doc.uom_conversion_details,lot_doc.uom,lot_doc.packing_uom)
		
		og_piece_quantity = qty * og_uom_factor_to_piece
		qty = (qty * uom_factor)
		for x in variant_doc.attributes:
			attr_values[x.attribute] = x.attribute_value
		
		for bom_item in item_detail.item_bom:
			if process_name:
				if bom_item.process_name != process_name:
					continue
			if not bom.get(bom_item.item, False):
				bom[bom_item.item] = {}

			qty_of_product = bom_item.qty_of_product
			qty_of_bom = bom_item.qty_of_bom_item
			bom_item_doc = None
			if pack_in_stage and pack_out_stage and bom_item.dependent_attribute_value:
				if not bom_item.dependent_attribute_value == pack_in_stage:
					dependent_attr_uom = get_uom(lot_doc.dependent_attribute_mapping,bom_item.dependent_attribute_value)
					bom_item_doc = frappe.get_doc("Item", bom_item.item)
					bom_item_conv = get_uom_conversion_factor(bom_item_doc.uom_conversion_details, dependent_attr_uom ,lot_doc.packing_uom)
					qty_of_product = bom_item_conv
			qty_of_product = qty_of_product/qty_of_bom
			uom = None
			if not bom_item.dependent_attribute_value or not item_detail.dependent_attribute:
				uom = bom_item_doc.default_unit_of_measure
			else:	
				uom = get_bom_uom(bom_item.dependent_attribute_value, item_detail.dependent_attribute_mapping)

			if not bom_item.based_on_attribute_mapping:
				quantity = qty / qty_of_product
				item_variant = get_or_create_variant(bom_item.item, {})
				
				if not bom[bom_item.item].get(item_variant, False):
					bom[bom_item.item][item_variant] = [math.ceil(quantity),bom_item.process_name, uom]
				else:
					bom[bom_item.item][item_variant][0] += math.ceil(quantity)
			else:
				pack_attr = item_detail.packing_attribute
				pack_combo = item_detail.packing_combo
				pack_attr_no =	item_detail.packing_attribute_no
				mapping_attr = bom_item.attribute_mapping
				mapping_doc = frappe.get_doc("Item BOM Attribute Mapping", mapping_attr)
				
				if item_detail.auto_calculate:
					temp_qty = qty/pack_attr_no
				else:
					temp_qty = qty/pack_combo
				temp_qty = temp_qty*qty_of_bom

				if item_detail.is_set_item:
					bom = get_set_item_bom(bom,item_detail, mapping_doc,attr_values, pack_attr,bom_item, qty, qty_of_product, temp_qty, uom)
				else:
					bom = get_not_set_item_bom(bom, item_detail, mapping_doc, attr_values, pack_attr, bom_item, qty, qty_of_product, temp_qty, uom)
		
		if item_detail.dependent_attribute:
			del attr_values[item_detail.dependent_attribute]

		if not process_name or process_name == item_detail.cutting_process:
			bom = calculate_cloth(bom, item_detail,cloth_combination, attr_values, og_piece_quantity, cloth_detail,cut_attrs_list)
	
	if process_name:
		return bom
				
	bom_items = []	
	for key, val in bom.items():
		for k,v in val.items():
			bom_items.append({'item_name': k,'uom':v[2],'process_name':v[1],'required_qty':v[0]})
	
	
	lot_doc.set('bom_summary', bom_items)
	lot_doc.last_calculated_time = now_datetime()
	lot_doc.save()	

##################       BOM CALCULATION FUNCTIONS       ##################

def get_set_item_bom(bom,item_detail,mapping_doc, attr_values, pack_attr,bom_item, qty, qty_of_product, temp_qty, uom):
	set_attr = item_detail.set_item_attribute
	set_item_map_doc = None
	for attr in item_detail.item_attributes:
		if attr.attribute == set_attr:
			set_item_map_doc = attr.mapping
			break

	same_attribute = get_same_attr(mapping_doc.item_attributes, attr_values, pack_attr)
	if pack_attr in attr_values:
		quantity = qty/qty_of_product
		set_map = frappe.get_doc("Item Item Attribute Mapping", set_item_map_doc)
		for set_val in set_map.values:
			for value in mapping_doc.values:
				if value.attribute == pack_attr and value.attribute_value == attr_values[pack_attr] and value.type == "item":
					if check_attr_value(value.index,'item',mapping_doc.values,set_attr,set_val.attribute_value):
						updated_bom = create_and_update_bom(value.index, "bom", mapping_doc.values, attr_values, mapping_doc.bom_item_attributes,bom_item.item, bom, quantity, bom_item.process_name, uom)
						bom = updated_bom
						break
	else:
		set_map = frappe.get_doc("Item Item Attribute Mapping", set_item_map_doc)
		for pack_attr_value in item_detail.packing_attribute_details:
			for attr in set_map.values:
				for value in mapping_doc.values:
					if value.attribute == set_attr and value.attribute_value == attr.attribute_value and value.type == "item":
						get_attr = pack_attr
						get_value = pack_attr_value.attribute_value

						if not same_attribute == pack_attr:
							get_attr = same_attribute
							get_value = attr_values[same_attribute]	
							
						if item_detail.major_attribute_value == attr.attribute_value:	
							if check_attr_value(value.index, "item", mapping_doc.values,get_attr,get_value):
								attributes = get_same_index_values(value.index, "bom", mapping_doc.values, attr_values, mapping_doc.bom_item_attributes)
								updated_bom = create_and_update_bom_set(attributes,bom_item.item,bom,temp_qty,item_detail.auto_calculate,item_detail.packing_attribute_details, pack_attr_value.attribute_value, bom_item.process_name, uom)
								bom = updated_bom
								break
						else:
							attributes = get_bottom_part_values(get_value,attr.attribute_value, item_detail.set_item_combination_details, item_detail.set_item_attribute, get_attr,mapping_doc.values, attr_values, mapping_doc.bom_item_attributes) 
							for attribute in attributes:
								updated_bom = create_and_update_bom_set(attribute,bom_item.item,bom,temp_qty,item_detail.auto_calculate,item_detail.packing_attribute_details, pack_attr_value.attribute_value, bom_item.process_name, uom)
								bom = updated_bom
							break
	return bom

def get_not_set_item_bom(bom, item_detail, mapping_doc, attr_values, pack_attr, bom_item, qty, qty_of_product, temp_qty, uom):
	same_attribute = get_same_attr(mapping_doc.item_attributes, attr_values, pack_attr)
	if pack_attr in attr_values:
		quantity = qty/qty_of_product
		get_attr = pack_attr
		get_value = attr_values[pack_attr]
		if not same_attribute == pack_attr:
			get_attr = same_attribute
			get_value = attr_values[same_attribute]
		for value in mapping_doc.values:
			if value.attribute == get_attr and value.attribute_value == get_value and value.type == "item":
				updated_bom = create_and_update_bom(value.index, "bom", mapping_doc.values, attr_values, mapping_doc.bom_item_attributes,bom_item.item, bom, quantity,bom_item.process_name, uom)	
				bom = updated_bom
				break	
	else:
		item_map_doc = None
		for attr in item_detail.item_attributes:
			if attr.attribute == same_attribute:
				item_map_doc = attr.mapping
				break

		item_map = frappe.get_doc("Item Item Attribute Mapping", item_map_doc)
		for attr in item_map.values:
			for value in mapping_doc.values:
				if value.attribute == same_attribute and value.attribute_value == attr.attribute_value and value.type == "item":
					attributes = get_same_index_values(value.index, "bom", mapping_doc.values, attr_values, mapping_doc.bom_item_attributes)
					updated_bom = create_and_update_bom_set(attributes,bom_item.item,bom,temp_qty,item_detail.auto_calculate,item_detail.packing_attribute_details, attr.attribute_value, bom_item.process_name, uom)
					bom = updated_bom
					break
	return bom			

##################       BOM CALCULATION FUNCTIONS       ##################
def calculate_cloth(bom, item_detail,cloth_combination, attr_values, og_piece_quantity, cloth_detail,cut_attrs_list):
	temp_qty = 0.0

	if item_detail.auto_calculate:
		temp_qty = og_piece_quantity / item_detail.packing_attribute_no		
	else:
		temp_qty = og_piece_quantity / item_detail.packing_combo

	is_stich_attribute = True
	if not cloth_combination[0].get(item_detail.stiching_attribute):
		is_stich_attribute = False
	same_attr_value = attr_values.copy()

	for packing_attr in item_detail.packing_attribute_details:
		for stiching_attr in item_detail.stiching_item_details:
			for cutting_attr in cloth_combination:
				if not attr_values.get(item_detail.stiching_attribute):
					attr_values[item_detail.stiching_attribute] = stiching_attr.stiching_attribute_value	
				if not attr_values.get(item_detail.packing_attribute):
					attr_values[item_detail.packing_attribute] = packing_attr.attribute_value
				if check_cutting_attr(attr_values, cutting_attr):
					if not cloth_detail.get(cutting_attr['Cloth'], False):
						break
					else:
						cloth_item = cloth_detail[cutting_attr['Cloth']]
						if not bom.get(cloth_item, False):
							bom[cloth_item] = {}
						multiplier = 1
						if not item_detail.auto_calculate:
							multiplier = packing_attr.quantity
						quantity = temp_qty * multiplier
						quantity = quantity * stiching_attr.quantity 
						dia = str(cutting_attr['Dia'])
						weight = cutting_attr['Weight']
						if item_detail.is_same_packing_attribute and item_detail.stiching_attribute not in cut_attrs_list:
							weight = weight / item_detail.stiching_attribute_quantity

						weight = weight * quantity
						x = 0.0
						if item_detail.additional_cloth:
							x = weight
							x = x/ 100
							x = x * item_detail.additional_cloth

						weight = weight + x
						if not is_stich_attribute and not item_detail.is_same_packing_attribute:
							frappe.msgprint("Stiching Attribute Not Defined in the Combination")
							return None
						cloth_color = get_cloth_colour(item_detail.stiching_item_combination_details,attr_values[item_detail.packing_attribute],attr_values[item_detail.stiching_attribute])
						
						if attr_values[item_detail.stiching_attribute] == item_detail.stiching_major_attribute_value:
							bom = calculate_accessories_cloth(quantity, cutting_attr, item_detail, cloth_detail, bom, cloth_item)

						variant = get_or_create_variant(cloth_item, {item_detail.packing_attribute: cloth_color, 'Dia':dia})
						if not bom[cloth_item].get(variant, False):
							uom = get_item_uom(cloth_item)
							bom[cloth_item][variant] = [weight, item_detail.cutting_process, uom]
						else:
							bom[cloth_item][variant][0] += weight

						attr_values = same_attr_value.copy()	
						break
	return bom

def get_packing_attr_quantity(packing_attr, packing_attr_details):
	for item in packing_attr_details:
		if item.attribute_value == packing_attr:
			return item.quantity

def get_stiching_attr_quantity(stiching_attr, stiching_attr_details):
	for item in stiching_attr_details:
		if item.stiching_attribute_value == stiching_attr:
			return item.quantity
		
def get_item_uom(item):
	uom = frappe.get_cached_value("Item",item,'default_unit_of_measure')
	return uom

def calculate_accessories_cloth(quantity, combination_attributes, item_detail, cloth_detail, bom, item_cloth):
	attributes = []
	for key,value in combination_attributes.items():
		if key != 'Weight':
			attributes.append(key)

	accesory_list = []
	cloth_accessory = json.loads(item_detail.cloth_accessory_json)
	if not cloth_accessory or len(cloth_accessory) == 0:
		return bom
	for cloth_item in cloth_accessory['items']:
		val = True
		for attr in attributes:
			if cloth_item.get(attr):
				if cloth_item[attr] != combination_attributes[attr]:
					val = False
		if val:
			x = cloth_item.copy() | combination_attributes
			x['Weight'] = cloth_item['Weight'] * quantity
			accesory_list.append(x)	
	item_list = {}

	for accessory in accesory_list:
		acc_cloth_json = item_detail.accessory_clothtype_json
		if isinstance(acc_cloth_json,string_types):
			acc_cloth_json = json.loads(acc_cloth_json)

		cloth_type = acc_cloth_json[accessory['Accessory']]
		cloth_item = cloth_detail[cloth_type]
		cloth_colour = get_accessory_color(item_detail.stiching_accessory_json,accessory['Accessory'],accessory[item_detail.packing_attribute], item_detail.stiching_major_attribute_value)
		variant = get_or_create_variant(cloth_item, {item_detail.packing_attribute: cloth_colour, 'Dia': accessory['Dia']})
		if item_list.get(variant):
			item_list[variant] += accessory['Weight']
		else:
			item_list[variant] = accessory['Weight']

	for key,val in item_list.items():
		y = 0.0
		if item_detail.additional_cloth:
			y = val
			y = y / 100
			y = y * item_detail.additional_cloth
		val = val + y
		if not bom[item_cloth].get(key, False):
			item_uom = get_item_uom(item_cloth)
			bom[item_cloth][key] = [val, item_detail.cutting_process, item_uom]
		else:
			bom[item_cloth][key][0] += val
	
	return bom

def get_accessory_color(accessory_json, accessory, packing_attr_value, major_attr_value):
	for item in json.loads(accessory_json)['items']:
		if item[major_attr_value] == packing_attr_value:
			return item[accessory]

def get_cloth_colour(stiching_combination_detail, major_attribute, set_attribute):
	for item in stiching_combination_detail:
		if item.major_attribute_value == major_attribute and set_attribute== item.set_item_attribute_value:
			return item.attribute_value

def get_bom_uom(dependent_attr_value, dependent_attr_mapping):
	attr_details = get_dependent_attribute_details(dependent_attr_mapping)
	return attr_details['attr_list'][dependent_attr_value]['uom']

def get_uom(dependent_attribute_mapping,dependent_attribute_value):
	dept_attr_details = get_dependent_attribute_details(dependent_attribute_mapping)
	for attr in dept_attr_details['attr_list']:
		if attr == dependent_attribute_value:
			return dept_attr_details['attr_list'][attr]['uom']

def check_attr_value(index, type, values,attr ,attr_value):
	for value in values:
		if index == value.index and type == value.type and attr == value.attribute and attr_value == value.attribute_value:
			return True
	return False

def get_quantity(packing_attribute_details, attr):
	for item in packing_attribute_details:
		if item.attribute_value == attr:
			return flt(item.quantity)

def get_same_index_values(index, type, values, attr_values, bom_item_attributes):
	bom_attr = {}
	for value in values:
		if value.index == index and value.type == type:
			bom_attr[value.attribute] = value.attribute_value
		elif value.index > index:
			break

	for attr in bom_item_attributes:
		if attr.attribute not in bom_attr and attr.same_attribute:
			bom_attr[attr.attribute] = attr_values[attr.attribute]

	return bom_attr		

def check_cutting_attr(item_attr, combination_attr):
	for key, value in item_attr.items():
		if not combination_attr.get(key, False):
			pass
		elif combination_attr[key] != value:
			return False
	return True	

def get_cloth_combination(item_detail):
	cutting_attributes = []
	cloth_attributes = []

	for i in item_detail.cutting_attributes:
		cutting_attributes.append(i.attribute)
	for i in item_detail.cloth_attributes:
		cloth_attributes.append(i.attribute)
	
	cloth_combination  = item_detail.cutting_cloths_json
	if item_detail.packing_attribute not in cutting_attributes and item_detail.packing_attribute not in cloth_attributes:
		packing_attribute_values = []
		for i in item_detail.packing_attribute_details:
			packing_attribute_values.append(i.attribute_value)
		cloth_combination = get_combination(item_detail.packing_attribute, packing_attribute_values, cloth_combination) 
	
	if item_detail.stiching_attribute not in cutting_attributes and item_detail.stiching_attribute not in cloth_attributes: #and not item_detail.is_same_packing_attribute:
		stiching_attribute_values = []
		for i in item_detail.stiching_item_details:
			stiching_attribute_values.append(i.stiching_attribute_value)
		cloth_combination = get_combination(item_detail.stiching_attribute, stiching_attribute_values, cloth_combination)
	
	if isinstance(cloth_combination,string_types):
		cloth_combination = json.loads(cloth_combination)

	cutting_items = json.loads(item_detail.cutting_items_json)
	cloth_items = cloth_combination
	combination_list = []
	for cut_item in cutting_items['items']:
		for cloth_item in cloth_items['items']:
			same_attrs = get_same_attributes(cut_item, cloth_item)
			check = True
			if len(same_attrs) > 0:
				check = check_same_values(cut_item, cloth_item, same_attrs)
			if check:
				x = cloth_item | cut_item
				combination_list.append(x)
	return combination_list

def get_combination(attribute ,attribute_values, json_data):
	if isinstance(json_data, string_types):
		json_data = json.loads(json_data)
	items = []
	for data in json_data['items']:
		for attr_value in attribute_values:
			attr = data.copy()
			attr[attribute] = attr_value
			items.append(attr)
	json_data['items'] = items
	return json_data		

def get_same_attributes(cut_item, cloth_item):
	same_attrs = []
	for key, value in cut_item.items():
		if cloth_item.get(key):
			same_attrs.append(key)
	return same_attrs		

def check_same_values(cut_item, cloth_item, same_attrs):
	for item in same_attrs:
		if cut_item[item] != cloth_item[item]:
			return False
	return True	

def create_and_update_bom(index, type, mapping_doc_values, attr_values, mapping_bom_item_attributes, bom_item, bom, quantity, process_name, uom):
	attributes = get_same_index_values(index, type, mapping_doc_values, attr_values, mapping_bom_item_attributes)
	new_variant = get_or_create_variant(bom_item, attributes)
	if not bom.get(bom_item, False):
		bom[bom_item] = {}

	if not bom[bom_item].get(new_variant, False):
		bom[bom_item][new_variant] = [math.ceil(quantity),process_name, uom]
	else:
		bom[bom_item][new_variant][0] += math.ceil(quantity)
	return bom

def create_and_update_bom_set(attributes, bom_item, bom, quantity, auto_calculate, packing_attribute_details, attr_value, process_name, uom):
	new_variant = get_or_create_variant(bom_item, attributes)
	if not bom.get(bom_item, False):
		bom[bom_item] = {}
	if not bom[bom_item].get(new_variant, False):
		if auto_calculate:
			bom[bom_item][new_variant] = [math.ceil(quantity),process_name, uom]
		else:
			bom[bom_item][new_variant] = [math.ceil(quantity * get_quantity(packing_attribute_details, attr_value)),process_name, uom]
	else:
		if auto_calculate:
			bom[bom_item][new_variant][0] += math.ceil(quantity)
		else:
			bom[bom_item][new_variant][0] += math.ceil(quantity * get_quantity(packing_attribute_details, attr_value))
	return bom

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

def save_item_details(combination_item_detail):
	if isinstance(combination_item_detail, string_types):
		combination_item_detail = json.loads(combination_item_detail)
	item_detail = []
	for idx,item in enumerate(combination_item_detail['values']):
		for value in item['val']:
			row = {}
			row['index'] = idx
			row['major_attribute_value'] = item['major_attribute']
			row['set_item_attribute_value'] = value
			row['attribute_value'] = item['val'][value]
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

##################       SET ITEM FUNCTIONS       ###################

def get_bottom_part_values(attr, major_attr, set_item_details, set_item_attr, pack_attr, mapping_doc_values, attr_values, mapping_bom_item_attributes):
	index = -1
	for item in set_item_details:
		if item.major_attribute_value == attr:
			index = item.index
			break

	bottom_parts = {}
	bottom_parts[set_item_attr] = []
	for item in set_item_details:
		if item.index == index and item.set_item_attribute_value == major_attr:
			bottom_parts[set_item_attr].append({set_item_attr : item.set_item_attribute_value, pack_attr:item.attribute_value})

	attributes = []
	for parts in bottom_parts[set_item_attr]:
		key, val = parts.items()
		index = -1
		for x in mapping_doc_values:
			if x.attribute == key[0] and x.attribute_value == key[1] and x.type == 'item':
				for y in mapping_doc_values:
					if y.index == x.index and y.attribute == val[0] and y.attribute_value == val[1] and y.type == 'item':
						index = y.index
		if index != -1:	
			attributes.append(get_same_index_values(index,"bom",mapping_doc_values, attr_values, mapping_bom_item_attributes))
	return attributes

def get_same_attr(item_attributes, attr_values, pack_attr):
	for item in item_attributes:
		if item.attribute == pack_attr:
			return item.attribute

	for item in item_attributes:
		if item.attribute in attr_values:
			return item.attribute

##################       STICHING FUNCTIONS       ###################

@frappe.whitelist()
def get_stiching_in_stage_attributes(dependent_attribute_mapping,stiching_in_stage):
	attribute_details = get_dependent_attribute_details(dependent_attribute_mapping)
	for attr in attribute_details['attr_list']:
		if attr == stiching_in_stage:
			return attribute_details['attr_list'][attr]['attributes']

##################       CUTTING FUNCTIONS        ###################

@frappe.whitelist()		
def get_cutting_combination(attributes,item_attributes, cloth_detail, combination_type, packing_attr, packing_attr_details):
	attributes = json.loads(attributes)
	if isinstance(item_attributes, string_types):
		item_attributes = json.loads(item_attributes)
	if isinstance(cloth_detail, string_types):
		cloth_detail = json.loads(cloth_detail)
	if isinstance(packing_attr_details, string_types):
		packing_attr_details = json.loads(packing_attr_details)
	item_attr_val_list = get_combination_attr_list(attributes,packing_attr, packing_attr_details, item_attributes)
	
	item_list = []
	if len(attributes) == 1:
		for attr_val in item_attr_val_list[attributes[0]]:
			if combination_type == 'Cutting':
				item_list.append({
					attributes[0]:attr_val,
					'Dia':None,
					"Weight":None,
				})
			else:		
				item_list.append({
					attributes[0]:attr_val,
					"Cloth":None,
				})
	else:
		attrs_len = {}
		initial_attrs = {}
		for key, val in item_attr_val_list.items():
			attrs_len[key] = len(val)
			initial_attrs[key] = 0
		check = False
		last_item = attributes[len(attributes)-1]
		while True:
			temp = {}
			for item,item_values in item_attr_val_list.items():
				temp[item] = item_values[initial_attrs[item]]
				if item == last_item:
					initial_attrs[item] += 1
					if initial_attrs[item] == attrs_len[item]:
						initial_attrs = update_below(initial_attrs, attributes, last_item, attrs_len)
				if initial_attrs == None:
					check = True
			if combination_type == 'Cutting':			
				temp['Dia'] = None
				temp['Weight'] = None
			elif combination_type == 'Cloth':
				temp['Cloth'] = None
			
			item_list.append(temp)
			if check:
				break
	cloths = []
	for cloth in cloth_detail:
		cloths.append(cloth['name1'])
	additional_attr = []
	if combination_type == 'Cutting':
		additional_attr = ['Dia', 'Weight']
	else:
		additional_attr = ['Cloth']	

	final_list = {
		'combination_type': combination_type,
		'attributes' : attributes + additional_attr,
		'items': item_list,
		'select_list':cloths
	}
	return final_list

@frappe.whitelist()		
def get_accessory_combination(attributes,item_attributes, cloth_accessories, combination_type, packing_attr, packing_attr_details):
	attributes = json.loads(attributes)
	if isinstance(item_attributes, string_types):
		item_attributes = json.loads(item_attributes)
	if isinstance(cloth_accessories, string_types):
		cloth_accessories = json.loads(cloth_accessories)	
	if isinstance(packing_attr_details, string_types):
		packing_attr_details = json.loads(packing_attr_details)
	item_attr_val_list = get_combination_attr_list(attributes,packing_attr, packing_attr_details, item_attributes)
	
	attributes.append("Accessory")
	accessory_list = []
	for cloth_accessory,cloth in cloth_accessories.items():
		accessory_list.append(cloth_accessory)
	item_attr_val_list['Accessory'] = accessory_list	
	item_list = []

	if len(attributes) == 1:
		for attr_val in item_attr_val_list[attributes[0]]:
			item_list.append({
				attributes[0]:attr_val,
				"Accessory":None,
				"Weight":None
			})	
	else:
		attrs_len = {}
		initial_attrs = {}
		for key, val in item_attr_val_list.items():
			attrs_len[key] = len(val)
			initial_attrs[key] = 0
		check = False
		last_item = attributes[len(attributes)-1]
		while True:
			temp = {}
			for item,item_values in item_attr_val_list.items():
				temp[item] = item_values[initial_attrs[item]]
				if item == last_item:
					initial_attrs[item] += 1
					if initial_attrs[item] == attrs_len[item]:
						initial_attrs = update_below(initial_attrs, attributes, last_item, attrs_len)
				if initial_attrs == None:
					check = True
			temp['Weight'] = None
			item_list.append(temp)
			if check:
				break
	
	additional_attr = ['Weight']	
	final_list = {
		'combination_type': combination_type,
		'attributes' : attributes + additional_attr,
		'items': item_list,
		'select_list':accessory_list,
	}
	return final_list

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

	for stich_item in ipd_doc.stiching_item_combination_details:
		if stich_item.set_item_attribute_value == ipd_doc.stiching_major_attribute_value:
			new_dict = {}
			new_dict[stich_item.set_item_attribute_value] = stich_item.major_attribute_value
			for key,val in x.items():
				new_dict[key] = None
			combination_list['items'].append(new_dict)
	
	return combination_list		

def get_combination_attr_list(attributes, packing_attr, packing_attr_details, item_attributes):
	item_attr_value_list = {}
	pack_details = []
	for pack_attr in packing_attr_details:
		pack_details.append(pack_attr['attribute_value'])

	for item in item_attributes:
		if item['attribute'] in attributes:
			attr_details = get_attr_mapping_details(item['mapping'])
			item_attr_value_list[item['attribute']] = attr_details

	item_attr_value_list[packing_attr] = pack_details
	item_attr_val_list = {}
	for attr in attributes:
		item_attr_val_list[attr] = item_attr_value_list[attr]

	return item_attr_val_list	

def update_below(initial_attrs, attributes, last_item, attrs_len):
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
