import unittest
from unittest import mock

from src.collab_router import Router, batch_status


def config_for(caller="garry"):
    return {
        "caller": caller,
        "default_skill": "company-info",
        "timeout_seconds": 1,
        "partners": {
            "garry": {"a2a_url": "http://hermes-garry:8080"},
            "monica": {"a2a_url": "http://hermes-monica:8080"},
            "laurie": {"a2a_url": "http://hermes-laurie:8080"},
        },
        "policy": {
            "require_purpose": True,
            "deny_self_calls": True,
            "callers": {
                "garry": {
                    "can_ask": ["monica", "laurie"],
                    "skills": ["company-info"],
                },
                "monica": {
                    "can_ask": ["garry", "laurie"],
                    "skills": ["company-info"],
                },
            },
        },
    }


class RouterPolicyTests(unittest.TestCase):
    def test_unknown_target_rejects(self):
        router = Router(config_for())
        result = router.ask_partner_brain(
            {
                "partner": "brad",
                "company_query": "Acme",
                "purpose": "meeting prep",
            }
        )
        self.assertEqual(result["status"], "rejected")
        self.assertIn("unknown target partner", result["reason"])

    def test_missing_purpose_rejects(self):
        router = Router(config_for())
        result = router.ask_partner_brain(
            {
                "partner": "monica",
                "company_query": "Acme",
                "purpose": "",
            }
        )
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "purpose is required")

    def test_self_call_rejects(self):
        router = Router(config_for())
        result = router.ask_partner_brain(
            {
                "partner": "garry",
                "company_query": "Acme",
                "purpose": "meeting prep",
            }
        )
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "self calls are not allowed")

    def test_batch_preserves_partner_order_and_dedupes(self):
        router = Router(config_for())

        def fake_forward(partner, _query, _purpose):
            return {
                "status": "ok",
                "partner": partner,
                "skill": "company-info",
                "text": f"{partner} notes",
            }

        with mock.patch.object(router, "forward_to_a2a", side_effect=fake_forward):
            result = router.ask_partner_brains(
                {
                    "partners": ["laurie", "monica", "laurie"],
                    "company_query": "Acme",
                    "purpose": "meeting prep",
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            [item["partner"] for item in result["results"]],
            ["laurie", "monica"],
        )

    def test_batch_partial_when_one_allowed_call_fails(self):
        router = Router(config_for())

        def fake_forward(partner, _query, _purpose):
            if partner == "monica":
                return {
                    "status": "upstream_error",
                    "partner": partner,
                    "skill": "company-info",
                    "reason": "boom",
                }
            return {
                "status": "ok",
                "partner": partner,
                "skill": "company-info",
                "text": "notes",
            }

        with mock.patch.object(router, "forward_to_a2a", side_effect=fake_forward):
            result = router.ask_partner_brains(
                {
                    "partners": ["monica", "laurie"],
                    "company_query": "Acme",
                    "purpose": "meeting prep",
                }
            )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(
            [item["status"] for item in result["results"]],
            ["upstream_error", "ok"],
        )

    def test_batch_status_all_rejected(self):
        self.assertEqual(
            batch_status(
                [
                    {"status": "rejected"},
                    {"status": "rejected"},
                ]
            ),
            "rejected",
        )


if __name__ == "__main__":
    unittest.main()
