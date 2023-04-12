import frappe
from frappe.desk.form.utils import get_pdf_link


from frappe.website.utils import build_response
from frappe.website.page_renderers.base_renderer import BaseRenderer

def get_context(context):
    link_doc = frappe.get_doc("Shortened Link", frappe.form_dict.name)
    context["link"] = get_pdf_link(link_doc.document_type,link_doc.document_linked, "purchase_order")
    frappe.response.type = "redirect"
    frappe.response.location = get_pdf_link(link_doc.document_type,link_doc.document_linked, "purchase_order")
    return
    
