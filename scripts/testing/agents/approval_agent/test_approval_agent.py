import json
import pytest
import pytest_asyncio
from shared.config.settings import settings
from agents.approval_agent.agent import ApprovalAgent
from agents.approval_agent.tools.approval_status import ApprovalDecision, ApprovalStatus
from shared.models.budget import BudgetStatus
from shared.utils.logging_config import get_logger, setup_logging

setup_logging(log_level=settings.log_level,
                log_file=settings.log_file,
                log_to_console=settings.log_to_console)

logger = get_logger(__name__)


class TestDeterministicApprovalDecision:
    """
    Tests for ApprovalAgent._deterministic_approval_decision.
    
    Decision tree under test:
    
    if vendor_active AND vendor_approved AND vendor_auto_approve:
        ├── if budget_status != ACTIVE → REJECTED
        ├── elif vendor_auto_approve_limit AND amount > limit → MANUAL_APPROVAL_REQUIRED
        ├── elif budget_approval_required_over AND amount > limit → MANUAL_APPROVAL_REQUIRED
        ├── elif budget_auto_approve_under AND amount < threshold → AUTO_APPROVED
        └── else → REJECTED (gap between thresholds)
    else:
        └── REJECTED (vendor flags not met)
        
    Key implementation detail: limits use truthiness guards (e.g., `vendor_auto_approve_limit and ...`),
    meaning a limit of 0 is treated as "no limit configured" and the branch is skipped.
    """

    @pytest_asyncio.fixture
    async def tool(self):
        agent = ApprovalAgent()
        yield agent

    @pytest_asyncio.fixture
    async def invoice(self):
        invoice_data_path = "scripts/data-source/invoices_data.json"
        logger.info(f"Loading invoice data from {invoice_data_path}")
        with open(invoice_data_path, "r") as f:
            invoices_data = json.load(f)
        return invoices_data[0]

    @pytest_asyncio.fixture
    async def budget(self):
        budget_data_path = "scripts/data-source/budgets_data.json"
        logger.info(f"Loading budget data from {budget_data_path}")
        with open(budget_data_path, "r") as f:
            budget_data = json.load(f)
        return budget_data[0]

    @pytest_asyncio.fixture
    async def vendor(self):
        vendor_data_path = "scripts/data-source/vendors_data.json"
        logger.info(f"Loading vendor data from {vendor_data_path}")
        with open(vendor_data_path, "r") as f:
            vendor_data = json.load(f)
        return vendor_data[0]

    # =========================================================================
    # Branch: vendor flags met → budget ACTIVE → amount < auto_approve_under
    # Code path: outer if → skip budget_status → skip vendor_limit → 
    #            skip budget_approval → elif budget_auto_approve_under
    # =========================================================================
    @pytest.mark.asyncio
    async def test_auto_approved_happy_path(self,
                                            tool: ApprovalAgent,
                                            invoice: dict,
                                            budget: dict,
                                            vendor: dict):
        correlation_id = "test-deterministic-001"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 10000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["auto_approve_under"] = 5000.0
        budget["approval_required_over"] = 10000.0

        invoice["amount"] = 1000.0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result is not None
        assert result.status == ApprovalStatus.AUTO_APPROVED
        assert "below budget auto-approval threshold" in result.reason
        assert "5000.0" in result.reason

    # =========================================================================
    # Branch: vendor_active = False → else (vendor flags not met)
    # Code path: outer else
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_vendor_not_active(self,
                                              tool: ApprovalAgent,
                                              invoice: dict,
                                              budget: dict,
                                              vendor: dict):
        correlation_id = "test-deterministic-002"

        vendor["active"] = False
        vendor["approved"] = True
        vendor["auto_approve"] = True

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.REJECTED
        assert "Vendor does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Branch: vendor_approved = False → else (vendor flags not met)
    # Code path: outer else
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_vendor_not_approved(self,
                                                tool: ApprovalAgent,
                                                invoice: dict,
                                                budget: dict,
                                                vendor: dict):
        correlation_id = "test-deterministic-003"

        vendor["active"] = True
        vendor["approved"] = False
        vendor["auto_approve"] = True

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.REJECTED
        assert "Vendor does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Branch: vendor_auto_approve = False → else (vendor flags not met)
    # Code path: outer else
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_vendor_auto_approve_disabled(self,
                                                         tool: ApprovalAgent,
                                                         invoice: dict,
                                                         budget: dict,
                                                         vendor: dict):
        correlation_id = "test-deterministic-004"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = False

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.REJECTED
        assert "Vendor does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Branch: vendor flags met → budget_status != ACTIVE (FROZEN)
    # Code path: outer if → if budget_status != ACTIVE
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_budget_frozen(self,
                                          tool: ApprovalAgent,
                                          invoice: dict,
                                          budget: dict,
                                          vendor: dict):
        correlation_id = "test-deterministic-005"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True

        budget["status"] = BudgetStatus.FROZEN

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.REJECTED
        assert "Budget status is" in result.reason
        assert "not active" in result.reason

    # =========================================================================
    # Branch: vendor flags met → budget ACTIVE → amount > vendor_auto_approve_limit
    # Code path: outer if → skip budget_status → elif vendor_auto_approve_limit
    # =========================================================================
    @pytest.mark.asyncio
    async def test_manual_review_exceeds_vendor_limit(self,
                                                      tool: ApprovalAgent,
                                                      invoice: dict,
                                                      budget: dict,
                                                      vendor: dict):
        correlation_id = "test-deterministic-007"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 5000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 50000.0
        budget["auto_approve_under"] = 50000.0

        invoice["amount"] = 7500.0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.MANUAL_APPROVAL_REQUIRED
        assert "vendor auto-approval limit" in result.reason
        assert "5000.0" in result.reason

    # =========================================================================
    # Branch: vendor flags met → budget ACTIVE → within vendor limit →
    #         amount > budget_approval_required_over
    # Code path: outer if → skip budget_status → skip vendor_limit →
    #            elif budget_approval_required_over
    # =========================================================================
    @pytest.mark.asyncio
    async def test_manual_review_exceeds_budget_approval_threshold(self,
                                                                    tool: ApprovalAgent,
                                                                    invoice: dict,
                                                                    budget: dict,
                                                                    vendor: dict):
        correlation_id = "test-deterministic-008"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 50000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 5000.0
        budget["auto_approve_under"] = 50000.0

        invoice["amount"] = 7500.0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.MANUAL_APPROVAL_REQUIRED
        assert "budget approval required limit" in result.reason
        assert "5000.0" in result.reason

    # =========================================================================
    # Branch: vendor flags met → budget ACTIVE → within vendor limit →
    #         within budget_approval_required_over → amount >= auto_approve_under
    #         → else (gap between thresholds)
    # Code path: outer if → skip all elifs → else
    #
    # Scenario: auto_approve_under=1000, amount=5000
    #           amount is NOT < auto_approve_under, so falls to else
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_amount_in_threshold_gap(self,
                                                     tool: ApprovalAgent,
                                                     invoice: dict,
                                                     budget: dict,
                                                     vendor: dict):
        correlation_id = "test-deterministic-009"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 50000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 50000.0
        budget["auto_approve_under"] = 1000.0

        invoice["amount"] = 5000.0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.REJECTED
        assert "does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Boundary: amount just below auto_approve_under (strictly less than)
    # Code path: elif budget_auto_approve_under and amount < budget_auto_approve_under
    # =========================================================================
    @pytest.mark.asyncio
    async def test_auto_approved_just_below_threshold(self,
                                                      tool: ApprovalAgent,
                                                      invoice: dict,
                                                      budget: dict,
                                                      vendor: dict):
        correlation_id = "test-deterministic-010"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 10000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 10000.0
        budget["auto_approve_under"] = 5000.0

        invoice["amount"] = 4999.99

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.AUTO_APPROVED

    # =========================================================================
    # Boundary: amount exactly equals auto_approve_under
    # Code: `amount < budget_auto_approve_under` → 5000 < 5000 is False
    # Falls to else → REJECTED
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_at_exact_auto_approve_boundary(self,
                                                            tool: ApprovalAgent,
                                                            invoice: dict,
                                                            budget: dict,
                                                            vendor: dict):
        correlation_id = "test-deterministic-011"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 10000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 10000.0
        budget["auto_approve_under"] = 5000.0

        invoice["amount"] = 5000.0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        # 5000 < 5000 is False, so falls to else
        assert result.status == ApprovalStatus.REJECTED
        assert "does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Evaluation order: vendor_auto_approve_limit is checked BEFORE
    # budget_approval_required_over. When both would trigger, vendor wins.
    # Code path: elif vendor_auto_approve_limit (hit first)
    # =========================================================================
    @pytest.mark.asyncio
    async def test_vendor_limit_evaluated_before_budget_limit(self,
                                                               tool: ApprovalAgent,
                                                               invoice: dict,
                                                               budget: dict,
                                                               vendor: dict):
        correlation_id = "test-deterministic-012"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 3000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 5000.0
        budget["auto_approve_under"] = 50000.0

        invoice["amount"] = 7000.0  # exceeds both limits

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.MANUAL_APPROVAL_REQUIRED
        # Vendor limit branch is evaluated first in the elif chain
        assert "vendor auto-approval limit" in result.reason

    # =========================================================================
    # Edge case: amount = 0 with valid thresholds
    # Code: 0 > vendor_limit(10000) → False, 0 > budget_limit(10000) → False,
    #        0 < auto_approve_under(5000) → True → AUTO_APPROVED
    # =========================================================================
    @pytest.mark.asyncio
    async def test_auto_approved_zero_amount(self,
                                             tool: ApprovalAgent,
                                             invoice: dict,
                                             budget: dict,
                                             vendor: dict):
        correlation_id = "test-deterministic-013"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 10000.0

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 10000.0
        budget["auto_approve_under"] = 5000.0

        invoice["amount"] = 0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.AUTO_APPROVED

    # =========================================================================
    # Edge case: all vendor flags False
    # Code path: outer else (immediately)
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_all_vendor_flags_false(self,
                                                    tool: ApprovalAgent,
                                                    invoice: dict,
                                                    budget: dict,
                                                    vendor: dict):
        correlation_id = "test-deterministic-014"

        vendor["active"] = False
        vendor["approved"] = False
        vendor["auto_approve"] = False

        budget["status"] = BudgetStatus.ACTIVE
        invoice["amount"] = 100.0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.REJECTED
        assert "Vendor does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Truthiness guard: all limits set to 0
    # Code: `vendor_auto_approve_limit and ...` → 0 is falsy, branch SKIPPED
    #        `budget_approval_required_over and ...` → 0 is falsy, SKIPPED
    #        `budget_auto_approve_under and ...` → 0 is falsy, SKIPPED
    #        Falls to else → REJECTED
    #
    # This tests a critical Python behavior: the code treats 0 as
    # "no limit configured" due to truthiness checks.
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_all_limits_zero_truthiness_guard(self,
                                                              tool: ApprovalAgent,
                                                              invoice: dict,
                                                              budget: dict,
                                                              vendor: dict):
        correlation_id = "test-deterministic-015"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 0  # falsy → branch skipped

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 0  # falsy → branch skipped
        budget["auto_approve_under"] = 0  # falsy → branch skipped

        invoice["amount"] = 500.0

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        # All elif branches skipped due to truthiness guards on 0
        assert result.status == ApprovalStatus.REJECTED
        assert "does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Truthiness guard: vendor_auto_approve_limit = 0 but budget limits set
    # Code: vendor limit branch SKIPPED (0 is falsy),
    #        budget_approval_required_over checked normally
    # =========================================================================
    @pytest.mark.asyncio
    async def test_vendor_limit_zero_skipped_budget_limit_applies(self,
                                                                   tool: ApprovalAgent,
                                                                   invoice: dict,
                                                                   budget: dict,
                                                                   vendor: dict):
        correlation_id = "test-deterministic-016"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        vendor["auto_approve_limit"] = 0  # falsy → skipped

        budget["status"] = BudgetStatus.ACTIVE
        budget["approval_required_over"] = 5000.0
        budget["auto_approve_under"] = 50000.0

        invoice["amount"] = 7000.0  # exceeds budget_approval_required_over

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        # Vendor limit skipped (0), budget limit applies
        assert result.status == ApprovalStatus.MANUAL_APPROVAL_REQUIRED
        assert "budget approval required limit" in result.reason

    # =========================================================================
    # Missing keys: invoice has no "amount", vendor/budget have no limit keys
    # Code: .get() defaults → amount=0, all limits=0
    # All truthiness guards fail → else → REJECTED
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_missing_keys_use_defaults(self,
                                                       tool: ApprovalAgent,
                                                       invoice: dict,
                                                       budget: dict,
                                                       vendor: dict):
        correlation_id = "test-deterministic-017"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True
        # Remove limit keys to test .get() defaults
        vendor.pop("auto_approve_limit", None)

        budget["status"] = BudgetStatus.ACTIVE
        budget.pop("approval_required_over", None)
        budget.pop("auto_approve_under", None)

        invoice.pop("amount", None)

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        # All .get() return defaults (0), all truthiness guards fail → else
        assert result.status == ApprovalStatus.REJECTED
        assert "does not meet auto-approval criteria" in result.reason

    # =========================================================================
    # Budget status = None (missing key)
    # Code: budget_data.get("status", None) → None != BudgetStatus.ACTIVE → REJECTED
    # =========================================================================
    @pytest.mark.asyncio
    async def test_rejected_budget_status_none(self,
                                                tool: ApprovalAgent,
                                                invoice: dict,
                                                budget: dict,
                                                vendor: dict):
        correlation_id = "test-deterministic-018"

        vendor["active"] = True
        vendor["approved"] = True
        vendor["auto_approve"] = True

        budget.pop("status", None)  # Remove status key

        result: ApprovalDecision = await tool._deterministic_approval_decision(
            invoice_data=invoice,
            vendor_data=vendor,
            budget_data=budget,
            correlation_id=correlation_id
        )

        logger.info(f"Result: {result}")
        assert result.status == ApprovalStatus.REJECTED
        assert "Budget status is" in result.reason
        assert "not active" in result.reason
