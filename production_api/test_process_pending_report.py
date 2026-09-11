from unittest import TestCase

from production_api.utils import calculate_pending_days


class TestProcessPendingReport(TestCase):
	def test_pending_days_uses_last_dc_date(self):
		self.assertEqual(calculate_pending_days("2026-09-01", "2026-09-08"), 7)

	def test_pending_days_is_empty_without_dc(self):
		self.assertIsNone(calculate_pending_days(None, "2026-09-08"))

	def test_pending_days_does_not_become_negative(self):
		self.assertEqual(calculate_pending_days("2026-09-10", "2026-09-08"), 0)
