import frappe
from six import string_types

@frappe.whitelist()
def execute():
    ipd_list = frappe.get_all("Item Production Detail", pluck="name")   
    for ipd in ipd_list:
        ipd_doc = frappe.get_doc("Item Production Detail", ipd)
        stiching_accessory_json = ipd_doc.stiching_accessory_json
        if isinstance(stiching_accessory_json, string_types):
            stiching_accessory_json = frappe.json.loads(stiching_accessory_json)
        if stiching_accessory_json:
            cloth_list = []
            for cloth in ipd_doc.cloth_detail:
                cloth_list.append(cloth.name1)
            combination_list = {}
            combination_list['select_list'] = cloth_list
            combination_list['items'] = []
            if ipd_doc.is_set_item:
                combination_list['is_set_item'] = 1
                combination_list['set_attr'] = ipd_doc.set_item_attribute
                combination_list['attributes'] = ["Accessory", ipd_doc.set_item_attribute, "Major Colour", "Accessory Colour","Cloth"]
                part_colours = {}
                for row in ipd_doc.set_item_combination_details:
                    part_colours.setdefault(row.set_item_attribute_value, [])
                    part_colours[row.set_item_attribute_value].append(row.attribute_value)
                accessory_json =  ipd_doc.accessory_clothtype_json
                if isinstance(accessory_json, string_types):
                    accessory_json = frappe.json.loads(accessory_json)

                for accessory, part in accessory_json.items():
                    for row in stiching_accessory_json['items']:
                        major_colour = row['major_attr_value']
                        if major_colour not in part_colours[part]:
                            continue
                        for acc, details in row['accessories'].items():
                            if acc == accessory:
                                combination = {}
                                combination['accessory'] = acc
                                combination[ipd_doc.set_item_attribute] = part
                                combination['major_colour'] = major_colour
                                combination['accessory_colour'] = details['colour']
                                combination['cloth_type'] = details['cloth_type']
                                combination_list['items'].append(combination)
                                break
            else:
                combination_list['is_set_item'] = 0
                combination_list['attributes'] = ["Accessory", "Major Colour", "Accessory Colour","Cloth"]
                part_colours = []
                for row in ipd_doc.packing_attribute_details:
                    part_colours.append(row.attribute_value)
                accessory_json =  ipd_doc.accessory_clothtype_json
                if isinstance(accessory_json, string_types):
                    accessory_json = frappe.json.loads(accessory_json)

                for accessory, part in accessory_json.items():
                    for row in stiching_accessory_json['items']:
                        major_colour = row['major_attr_value']
                        for acc, details in row['accessories'].items():
                            if acc == accessory:
                                combination = {}
                                combination['accessory'] = acc
                                combination['major_colour'] = major_colour
                                combination['accessory_colour'] = details['colour']
                                combination['cloth_type'] = details['cloth_type']
                                combination_list['items'].append(combination)
                                break

            ipd_doc.stiching_accessory_json = combination_list
            ipd_doc.save()
