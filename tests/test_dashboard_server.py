import unittest

import src.dashboard_server as dashboard


class DashboardPolicyTests(unittest.TestCase):
    def setUp(self):
        dashboard.STATE["scenario"] = "disabled"
        dashboard.STATE["events"].clear()

    def test_disabled_scenario_blocks_garry_to_monica(self):
        route = dashboard.route_status("garry", "monica")
        self.assertEqual(route["status"], "blocked")
        self.assertEqual(route["reason"], "policy blocked")

    def test_disabled_scenario_allows_garry_to_laurie(self):
        route = dashboard.route_status("garry", "laurie")
        self.assertEqual(route["status"], "allowed")

    def test_enabled_scenario_allows_garry_to_monica_and_laurie(self):
        dashboard.STATE["scenario"] = "enabled"
        self.assertEqual(dashboard.route_status("garry", "monica")["status"], "allowed")
        self.assertEqual(dashboard.route_status("garry", "laurie")["status"], "allowed")

    def test_self_route_is_blocked(self):
        route = dashboard.route_status("garry", "garry")
        self.assertEqual(route["status"], "blocked")
        self.assertEqual(route["reason"], "self blocked")

    def test_add_event_keeps_model_readable_fields(self):
        event = dashboard.add_event(
            {
                "event": "router_decision",
                "caller": "garry",
                "target": "monica",
                "status": "rejected",
                "reason": "policy blocked",
            }
        )
        self.assertEqual(event["skill"], "company-info")
        self.assertEqual(event["status"], "rejected")
        self.assertEqual(list(dashboard.STATE["events"])[0], event)


if __name__ == "__main__":
    unittest.main()
