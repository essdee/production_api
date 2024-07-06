# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "production_api"
app_title = "Production Api"
app_publisher = "Essdee"
app_description = "Frappe application to manage manufacturing workflows"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "essdee@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/production_api/css/production_api.css"
app_include_js = ["vue_plugin.bundle.js"]

# include js, css files in header of web template
# web_include_css = "/assets/production_api/css/production_api.css"
# web_include_js = "/assets/production_api/js/production_api.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "production_api.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "production_api.install.before_install"
# after_install = "production_api.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "production_api.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "*": {
		"after_insert": "production_api.production_api.util.send_automatic_notification",
		"on_submit": "production_api.production_api.util.send_automatic_notification",
        "on_cancel": "production_api.production_api.util.send_automatic_notification",
	},
	"Communication": {
		"validate": "production_api.production_api.util.validate_communication",
	},
    "Item": {
        "on_update": "production_api.production_api.doctype.item.item.sync_updated_item_variant",
	},
    ("Item Variant", "Item Group"): {
        "after_insert": "spine.spine_adapter.docevents.eventhandler.handle_event",
        "on_update": "spine.spine_adapter.docevents.eventhandler.handle_event",
        "on_update_after_submit": "spine.spine_adapter.docevents.eventhandler.handle_event",
        "after_rename": "spine.spine_adapter.docevents.eventhandler.handle_event",
        "on_submit": "spine.spine_adapter.docevents.eventhandler.handle_event",
        "on_cancel": "spine.spine_adapter.docevents.eventhandler.handle_event",
    },
}

fixtures =[
    { 
		"dt": 'Workflow',
		"filters": [["name", "in",["PC_Flow"]]]
    },
    {
        'dt': 'Workflow State',
        'filters':[['name','in',['Draft','Approval Pending','Expired']]],
	},
    {
        'dt':'Workflow Action Master',
        'filters':[['name','in',['Submit','Expired']]]
	}
]


# Scheduled Tasks
# ---------------

scheduler_events = {
	# "all": [
	# 	"production_api.tasks.all"
	# ],
	# "daily": [
	# 	"production_api.tasks.daily"
	# ],
	# "hourly": [
	# 	"production_api.tasks.hourly"
	# ],
	# "weekly": [
	# 	"production_api.tasks.weekly"
	# ],
	# "monthly": [
	# 	"production_api.tasks.monthly"
	# ]
	"cron": {
		"0 1 * * *": [
			"production_api.tasks.daily"
		]
	}
}

# Testing
# -------

# before_tests = "production_api.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "production_api.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "production_api.task.get_dashboard_data"
# }

jinja = {
    "methods": [
        "production_api.production_api.doctype.purchase_order.purchase_order.fetch_item_details",
        "production_api.production_api.doctype.signature.signature.get_user_signature",
        "production_api.production_api.doctype.shortened_link.shortened_link.get_short_link",
        "production_api.production_api.doctype.purchase_order.purchase_order.get_PO_print_details",
        "production_api.production_api.util.parse_string_for_SMS",
        "production_api.production_api.doctype.goods_received_note.goods_received_note.fetch_grn_item_details",
        "production_api.production_api.util.check_key_value_in_dict_or_list_of_dict",
        "production_api.production_api.util.parse_json",
        "production_api.product_development.doctype.product.product.get_latest_product_images",
        "production_api.production_api.doctype.supplier.supplier.get_supplier_address_display",
        # Stock
		"production_api.mrp_stock.doctype.stock_entry.stock_entry.fetch_stock_entry_items",
    ]
}

auto_cancel_exempted_doctypes = ["Goods Received Note"]
