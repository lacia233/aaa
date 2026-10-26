import copy
import unittest
from unittest.mock import patch
import monitor


def quote(price):
    return {'BTC': {'usd': price, 'updated_at': 100},
            'ETH': {'usd': 2000, 'updated_at': 100},
            'ZAMA': {'usd': 0.05, 'updated_at': 100}}


class CrossingTests(unittest.TestCase):
    def setUp(self):
        self.state = {'version': 1, 'previous': None, 'sent': [], 'pending': []}

    def test_initial_sample_does_not_send_historical_alerts(self):
        monitor.observe(self.state, quote(75000))
        self.assertEqual(self.state['pending'], [])

    def test_gap_queues_each_crossed_level_with_original_snapshot(self):
        monitor.observe(self.state, quote(79500))
        monitor.observe(self.state, quote(77500))
        self.assertEqual([x['level'] for x in self.state['pending']], [79000, 78000])
        original = copy.deepcopy(self.state['pending'])
        monitor.observe(self.state, quote(80000))
        monitor.observe(self.state, quote(77500))
        self.assertEqual(self.state['pending'], original)

    def test_sent_level_does_not_repeat_after_rebound(self):
        self.state.update(previous=80000, sent=[79000])
        monitor.observe(self.state, quote(79000))
        self.assertEqual(self.state['pending'], [])

    def test_touch_then_continue_down_has_no_duplicate(self):
        monitor.observe(self.state, quote(80000))
        monitor.observe(self.state, quote(79000))
        monitor.observe(self.state, quote(78900))
        self.assertEqual(len(self.state['pending']), 1)

    def test_mail_failure_retains_queue_for_retry(self):
        self.state['previous'] = 80000
        with patch.object(monitor, 'required', return_value='configured'), \
             patch.object(monitor, 'load_state', return_value=self.state), \
             patch.object(monitor, 'save_state'), \
             patch.object(monitor, 'prices', return_value=quote(78500)), \
             patch.object(monitor, 'send', side_effect=RuntimeError('SMTP unavailable')), \
             patch('sys.argv', ['monitor.py']):
            with self.assertRaises(RuntimeError):
                monitor.main()
        self.assertEqual(self.state['sent'], [])
        self.assertEqual(self.state['pending'][0]['level'], 79000)


if __name__ == '__main__':
    unittest.main()
