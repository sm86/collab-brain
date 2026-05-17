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

    def test_default_policy_allows_monica_to_laurie(self):
        route = dashboard.route_status("monica", "laurie")
        self.assertEqual(route["status"], "allowed")

    def test_default_policy_blocks_monica_to_garry(self):
        route = dashboard.route_status("monica", "garry")
        self.assertEqual(route["status"], "blocked")

    def test_default_policy_blocks_laurie_to_garry_and_monica(self):
        self.assertEqual(dashboard.route_status("laurie", "garry")["status"], "blocked")
        self.assertEqual(dashboard.route_status("laurie", "monica")["status"], "blocked")

    def test_policy_can_disable_and_enable_route(self):
        ok, reason = dashboard.set_access("garry", "monica", "company-info", False)
        self.assertTrue(ok)
        self.assertEqual(reason, "policy blocked")
        self.assertEqual(dashboard.route_status("garry", "monica")["status"], "blocked")

        ok, reason = dashboard.set_access("garry", "monica", "company-info", True)
        self.assertTrue(ok)
        self.assertEqual(reason, "policy allow")
        self.assertEqual(dashboard.route_status("garry", "monica")["status"], "allowed")

    def test_policy_rejects_local_route_edits(self):
        ok, reason = dashboard.set_access("garry", "garry", "company-info", False)
        self.assertFalse(ok)
        self.assertIn("local routes", reason)

    def test_reset_policy_restores_default_hierarchy(self):
        dashboard.set_access("garry", "monica", "company-info", False)
        self.assertEqual(dashboard.route_status("garry", "monica")["status"], "blocked")
        dashboard.reset_policy()
        self.assertEqual(dashboard.route_status("garry", "monica")["status"], "allowed")

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

    def test_mock_data_index_lists_partner_markdown(self):
        index = dashboard.mock_data_index()
        self.assertIn("garry", index["partners"])
        companies = index["partners"]["garry"]["groups"]["companies"]
        self.assertIn("companies/acme.md", [item["path"] for item in companies])

    def test_read_mock_file_returns_markdown_content(self):
        data, error = dashboard.read_mock_file("garry", "companies/acme.md")
        self.assertEqual(error, "")
        self.assertEqual(data["partner"], "garry")
        self.assertEqual(data["path"], "companies/acme.md")
        self.assertIn("Acme", data["content"])

    def test_read_mock_file_rejects_path_traversal(self):
        data, error = dashboard.read_mock_file("garry", "../monica/companies/acme.md")
        self.assertIsNone(data)
        self.assertEqual(error, "invalid path")


if __name__ == "__main__":
    unittest.main()
