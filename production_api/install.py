import frappe
from production_api.production_api.doctype.supplier.supplier import make_gstin_custom_field

def after_install():
    make_gstin_custom_field()
    