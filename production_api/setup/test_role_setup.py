import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime

from production_api import hooks
from production_api.setup.role_setup import ensure_role


class TestRoleSetup(FrappeTestCase):
    def test_roles_are_not_exported_as_destructive_fixtures(self):
        fixture_doctypes = {
            fixture.get("dt") or fixture.get("doctype")
            for fixture in hooks.fixtures
            if isinstance(fixture, dict)
        }
        self.assertNotIn("Role", fixture_doctypes)
        self.assertFalse(os.path.exists(frappe.get_app_path("production_api", "fixtures", "role.json")))

    def test_existing_role_is_updated_without_deleting_it(self):
        role_name = f"MRP In-place Role {frappe.generate_hash(length=10)}"
        previous_migrate_flag = frappe.flags.in_migrate
        frappe.flags.in_migrate = True

        try:
            role = frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1,
                }
            ).insert(ignore_permissions=True)
            creation = role.creation

            with patch("frappe.delete_doc") as delete_doc:
                ensure_role(role_name, {"desk_access": 0})

            delete_doc.assert_not_called()
            updated = frappe.get_doc("Role", role_name)
            self.assertEqual(get_datetime(updated.creation), get_datetime(creation))
            self.assertEqual(updated.desk_access, 0)
        finally:
            frappe.db.delete("Role", {"name": role_name})
            frappe.flags.in_migrate = previous_migrate_flag
