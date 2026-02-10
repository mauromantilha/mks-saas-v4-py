from decimal import Decimal
from insurance_core.models import InsuranceBranch

class CommissionEngine:
    def calculate(self, policy, installment_number: int, paid_amount: Decimal) -> Decimal:
        """
        Calculates commission amount based on policy rules and installment details.
        """
        if not hasattr(policy, "billing_config"):
            return Decimal("0.00")

        branch_type = policy.branch.branch_type
        billing = policy.billing_config

        # 1. Normal Branch
        if branch_type == InsuranceBranch.TYPE_NORMAL:
            rate = billing.commission_rate_percent
            return paid_amount * (rate / Decimal("100.0"))

        # 2. Health Plan Branch
        if branch_type == InsuranceBranch.TYPE_HEALTH:
            # Renewal: Flat 2% on everything
            if policy.is_renewal:
                return paid_amount * Decimal("0.02")
            
            # New Business
            # We need to distinguish between "original" premium part and "endorsement delta" part.
            # The rule: 
            # - Original part: 100% for installments 1-3, 2% for 4-12.
            # - Delta part (endorsements): Always 2% (implied by "atualizar base... para 2%").
            
            original_total = billing.original_premium_total or billing.premium_total
            count = billing.installments_count
            
            # Avoid division by zero
            if count == 0:
                return Decimal("0.00")
                
            original_installment_value = original_total / count
            
            # Calculate split
            base_part = min(paid_amount, original_installment_value)
            delta_part = max(Decimal("0.00"), paid_amount - base_part)
            
            commission = Decimal("0.00")
            
            # Base part logic
            if installment_number <= 3:
                commission += base_part # 100%
            else:
                commission += base_part * Decimal("0.02") # 2%
            
            # Delta part logic
            commission += delta_part * Decimal("0.02")
            
            return commission.quantize(Decimal("0.01"))

        return Decimal("0.00")