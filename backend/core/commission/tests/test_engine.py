from decimal import Decimal

from django.test import SimpleTestCase

from commission.services.commission_engine import (
    CommissionSplitError,
    apply_split,
    calculate_commission,
)


class CommissionEngineUnitTests(SimpleTestCase):
    def test_calculate_commission_fixed_rate(self):
        amount = calculate_commission(
            base_amount=Decimal("1000.00"),
            rules_json={"rate_pct": Decimal("10.0")},
        )
        self.assertEqual(amount, Decimal("100.00"))

    def test_calculate_commission_tiered(self):
        rules = {
            "tiers": [
                {"up_to": "1000", "rate_pct": "5"},
                {"up_to": "5000", "rate_pct": "7.5"},
                {"rate_pct": "9.0"},
            ]
        }
        amount = calculate_commission(base_amount="3000", rules_json=rules)
        self.assertEqual(amount, Decimal("270.00"))

    def test_calculate_commission_with_product_exception(self):
        rules = {
            "rate_pct": "10",
            "exceptions": {
                "product": {
                    "42": {"rate_pct": "15"},
                }
            },
            "context": {"product_id": "42"},
        }
        amount = calculate_commission(base_amount="1000", rules_json=rules)
        self.assertEqual(amount, Decimal("150.00"))

    def test_apply_split_even_100_percent(self):
        allocations = apply_split(
            total_commission=Decimal("100.00"),
            split_participants=[
                {"id": "p1", "percentage": Decimal("60.00")},
                {"id": "p2", "percentage": Decimal("40.00")},
            ],
        )
        self.assertEqual(len(allocations), 2)
        self.assertEqual(allocations[0].amount, Decimal("60.00"))
        self.assertEqual(allocations[1].amount, Decimal("40.00"))

    def test_apply_split_validates_sum_100_percent(self):
        with self.assertRaises(CommissionSplitError):
            apply_split(
                total_commission=Decimal("100.00"),
                split_participants=[
                    {"id": "p1", "percentage": Decimal("80.00")},
                    {"id": "p2", "percentage": Decimal("10.00")},
                ],
            )
