import unittest

import src.dashboard_server as dashboard


class DashboardPolicyTests(unittest.TestCase):
    def setUp(self):
        dashboard.reset_policy()
        dashboard.STATE["events"].clear()

    def test_default_policy_allows_garry_to_monica(self):
        route = dashboard.route_status("garry", "monica")
        self.assertEqual(route["status"], "allowed")
        self.assertEqual(route["reason"], "policy allow")

    def test_default_policy_allows_garry_to_laurie(self):
        route = dashboard.route_status("garry", "laurie")
        self.assertEqual(route["status"], "allowed")

    def test_policy_can_disable_route(self):
        ok, reason = dashboard.set_access("garry", "monica", "company-info", False)
        self.assertTrue(ok)
        self.assertEqual(reason, "policy blocked")
        self.assertEqual(dashboard.route_status("garry", "monica")["status"], "blocked")

    def test_self_route_is_local(self):
        route = dashboard.route_status("garry", "garry")
        self.assertEqual(route["status"], "local")
        self.assertEqual(route["reason"], "own brain; no router needed")

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
