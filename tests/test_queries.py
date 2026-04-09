from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from ledger.models import Adjustment, BillingCycle, MemberCharge, OpeningBalance, Payment
from ledger.services.queries import get_member_statement, list_member_balances


def test_negative_balance_means_member_owes(session, active_member):
    session.add(
        BillingCycle(
            cycle_date=date(2026, 4, 20),
            status="posted",
            subscription_usd=Decimal("8.00"),
            fx_locked=Decimal("100.00"),
            subscription_rub=Decimal("800.00"),
            counted_active=1,
            billed_active=1,
            total_billed_rub=Decimal("800.00"),
            owner_subsidy_rub=Decimal("0.00"),
            posted_at=date(2026, 4, 20),
        )
    )
    session.flush()
    cycle = session.query(BillingCycle).one()
    session.add(
        MemberCharge(
            cycle_id=cycle.id,
            member_id=active_member.id,
            charge_date=cycle.cycle_date,
            active_count=1,
            subscription_usd=Decimal("8.00"),
            charge_usd=Decimal("8.00"),
            fx_locked=Decimal("100.00"),
            charge_rub=Decimal("800.00"),
        )
    )
    session.commit()

    balance = list_member_balances(session)[0]
    assert balance.balance_rub == Decimal("-800.00")


def test_payments_and_adjustments_affect_statement_and_balance(session, active_member):
    session.add(
        OpeningBalance(
            member_id=active_member.id,
            snapshot_date=date(2026, 4, 20),
            opening_balance_rub=Decimal("-100.00"),
            source_note="Cutover",
        )
    )
    cycle = BillingCycle(
        cycle_date=date(2026, 4, 20),
        status="posted",
        subscription_usd=Decimal("8.00"),
        fx_locked=Decimal("100.00"),
        subscription_rub=Decimal("800.00"),
        counted_active=1,
        billed_active=1,
        total_billed_rub=Decimal("800.00"),
        owner_subsidy_rub=Decimal("0.00"),
        posted_at=date(2026, 4, 20),
    )
    session.add(cycle)
    session.flush()
    session.add(
        MemberCharge(
            cycle_id=cycle.id,
            member_id=active_member.id,
            charge_date=cycle.cycle_date,
            active_count=1,
            subscription_usd=Decimal("8.00"),
            charge_usd=Decimal("8.00"),
            fx_locked=Decimal("100.00"),
            charge_rub=Decimal("800.00"),
        )
    )
    session.add(
        Payment(
            member_id=active_member.id,
            payment_date=date(2026, 5, 1),
            rub_paid=Decimal("500.00"),
            note="Bank transfer",
        )
    )
    session.add(
        Adjustment(
            member_id=active_member.id,
            effective_date=date(2026, 5, 2),
            amount_rub=Decimal("50.00"),
            reason="Manual credit",
            related_cycle_id=cycle.id,
        )
    )
    session.commit()

    balance = list_member_balances(session)[0]
    assert balance.balance_rub == Decimal("-350.00")

    statement = get_member_statement(session, active_member.id)
    assert statement.current_balance_rub == Decimal("-350.00")
    assert [entry.entry_type for entry in statement.entries] == [
        "opening_balance",
        "charge",
        "payment",
        "adjustment",
    ]


def test_opening_balance_is_single_frozen_import(session, active_member):
    session.add(
        OpeningBalance(
            member_id=active_member.id,
            snapshot_date=date(2026, 4, 20),
            opening_balance_rub=Decimal("-100.00"),
            source_note="Cutover import",
        )
    )
    session.commit()

    balance = list_member_balances(session)[0]
    assert balance.opening_balance_rub == Decimal("-100.00")

    session.add(
        OpeningBalance(
            member_id=active_member.id,
            snapshot_date=date(2026, 4, 21),
            opening_balance_rub=Decimal("-999.00"),
            source_note="Second import should fail",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    balance = list_member_balances(session)[0]
    assert balance.opening_balance_rub == Decimal("-100.00")
    statement = get_member_statement(session, active_member.id)
    assert [entry.entry_type for entry in statement.entries] == ["opening_balance"]
