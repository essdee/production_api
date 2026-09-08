from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from . import fg_inward_temp as report


class TestFGInwardTemp(TestCase):
    def setUp(self):
        self.enterContext(patch.object(report, '_', lambda text: text))
        self.enterContext(patch.object(frappe, 'throw', side_effect=ValueError))
        self.filters = report.validate_filters(dict(start_date='2026-01-31', end_date='2026-01-31', warehouse='WH'))
        self.row = dict(inward_reference=1, lot='LOT', inward_date='2026-01-31 23:59:59',
            created_by='operator', item='ITEM', legacy_item_id=10, size1=12,
            enabled_size1=1, label_size1='M', size2=0, size3=None)

    def test_dates_and_required_filters(self):
        self.assertEqual(str(self.filters.end_exclusive), '2026-02-01')
        for values in ({}, dict(start_date='2026-02-02', end_date='2026-02-01', warehouse='WH')):
            with self.assertRaises(ValueError):
                report.validate_filters(values)

    def test_query_parameterizes_filters_and_uses_creator_and_creation_date(self):
        self.filters.item = "ITEM' OR 1=1 --"
        self.filters.lot = "LOT'"
        query, values = report.build_query(self.filters, 2)
        self.assertNotIn(self.filters.item, query)
        self.assertNotIn(self.filters.lot, query)
        self.assertEqual(values['item'], self.filters.item)
        self.assertEqual(values['location_id'], 2)
        self.assertIn('entry.blame_user AS created_by', query)
        self.assertIn('entry.creationdate < %(end_exclusive)s', query)
        self.assertNotIn('docstatus', query)

    def test_original_quantities_and_separate_receipts_are_preserved(self):
        rows = report.expand_rows([self.row, {**self.row, 'inward_reference': 2}], self.filters, 'Warehouse')
        self.assertEqual([r['qty'] for r in rows], [12, 12])
        self.assertEqual([r['inward_reference'] for r in rows], [1, 2])
        self.assertEqual(rows[0]['created_by'], 'operator')
        self.assertEqual(rows[0]['item_variant'], 'ITEM-M')

    def test_sizes_are_constructed_without_variant_filtering(self):
        filters = report.validate_filters(dict(start_date='2026-01-31',
            end_date='2026-01-31', warehouse='WH', item_variant='STALE-FILTER'))
        self.assertNotIn('item_variant', filters)
        row = {**self.row, 'size2': 4, 'enabled_size2': 1, 'label_size2': 'L'}
        result = report.expand_rows([row], filters, 'WH')
        self.assertEqual([(r['item_variant'], r['qty']) for r in result],
            [('ITEM-M', 12), ('ITEM-L', 4)])

    def test_unmapped_and_negative_quantities_are_not_silently_dropped(self):
        row = {**self.row, 'enabled_size1': 0, 'size1': -3}
        result = report.expand_rows([row], self.filters, 'WH')
        self.assertEqual(result[0]['qty'], -3)
        self.assertEqual(result[0]['item_variant'], 'ITEM [unmapped size1]')

    def test_connection_closes_on_success_and_failure(self):
        for fail in (False, True):
            connection = MagicMock()
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value = [self.row]
            if fail:
                cursor.execute.side_effect = RuntimeError('query failed')
            with patch.object(report, 'get_connection', return_value=connection), patch.object(report, 'old_warehouse_mapping', return_value=[2, 'WH', 'Warehouse']):
                if fail:
                    with self.assertRaises(RuntimeError):
                        report.get_data(self.filters)
                else:
                    self.assertEqual(report.get_data(self.filters)[0]['warehouse'], 'Warehouse')
            connection.close.assert_called_once()
            connection.cursor.return_value.__exit__.assert_called_once()

    def test_empty_results_and_report_notice(self):
        self.assertEqual(report.expand_rows([], self.filters, 'WH'), [])
        with patch.object(report, 'get_data', return_value=[]):
            columns, rows, message = report.execute(dict(start_date='2026-01-01', end_date='2026-01-31', warehouse='WH'))
        self.assertEqual(len(columns), 10)
        self.assertEqual(rows, [])
        self.assertIn('No cancellation field', message)
