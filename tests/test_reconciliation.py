from datetime import date, datetime, timezone
from decimal import Decimal

import ledger.services.fx as fx_service
import ledger.services.reconciliation as reconciliation_service
from ledger.models import BillingCycle, JobLock, MemberCharge, ReconciliationRun
from ledger.services.queries import list_member_balances
from ledger.services.reconciliation import reconcile_ledger


def test_reconcile_empty_db_posts_all_missing_months(session, active_member, monkeypatch):
    monkeypatch.setattr(fx_service, "fetch_historical_fx_rate", lambda _: Decimal("100.00"))

    outcome = reconcile_ledger(session, today=date(2026, 7, 25))

    cycle_dates = [cycle.cycle_date for cycle in session.query(BillingCycle).order_by(BillingCycle.cycle_date).all()]
    assert cycle_dates == [
        date(2026, 4, 20),
        date(2026, 5, 20),
        date(2026, 6, 20),
        date(2026, 7, 20),
    ]
    assert outcome.state == "healthy"
    assert outcome.exact_through_date == date(2026, 7, 20)
    assert outcome.cycles_posted_count == 4
    assert session.query(MemberCharge).count() == 4


def test_reconcile_stops_at_first_failed_month_and_alerts(session, active_member, monkeypatch):
    def fake_fetch(rate_date):
        if rate_date == date(2026, 6, 20):
            raise ValueError("CurrencyBeacon timed out.")
        return Decimal("100.00")

    sent_messages: list[str] = []
    monkeypatch.setattr(fx_service, "fetch_historical_fx_rate", fake_fetch)
    monkeypatch.setattr(
        reconciliation_service,
        "send_telegram_alert",
        lambda message: sent_messages.append(message) or True,
    )

    outcome = reconcile_ledger(session, today=date(2026, 7, 25))

    cycle_dates = [cycle.cycle_date for cycle in session.query(BillingCycle).order_by(BillingCycle.cycle_date).all()]
    assert cycle_dates == [date(2026, 4, 20), date(2026, 5, 20)]
    assert outcome.state == "stale"
    assert outcome.exact_through_date == date(2026, 5, 20)
    assert outcome.failure_cycle_date == date(2026, 6, 20)
    assert outcome.alert_sent is True
    assert len(sent_messages) == 1

    run = session.query(ReconciliationRun).order_by(ReconciliationRun.id.desc()).first()
    assert run is not None
    assert run.status == "failed"
    assert run.alert_sent is True


def test_reconcile_records_telegram_failure_without_crashing(session, active_member, monkeypatch):
    def fake_fetch(rate_date):
        if rate_date == date(2026, 5, 20):
            raise ValueError("CurrencyBeacon timed out.")
        return Decimal("100.00")

    monkeypatch.setattr(fx_service, "fetch_historical_fx_rate", fake_fetch)

    def fail_notification(_message: str) -> bool:
        raise reconciliation_service.NotificationError("Telegram network error")

    monkeypatch.setattr(reconciliation_service, "send_telegram_alert", fail_notification)

    outcome = reconcile_ledger(session, today=date(2026, 5, 25))

    assert outcome.state == "stale"
    assert outcome.alert_sent is False
    run = session.query(ReconciliationRun).order_by(ReconciliationRun.id.desc()).first()
    assert run is not None
    assert run.status == "failed"
    assert run.alert_sent is False
    assert run.alert_error == "Telegram network error"


def test_reconcile_is_idempotent_after_success(session, active_member, monkeypatch):
    monkeypatch.setattr(fx_service, "fetch_historical_fx_rate", lambda _: Decimal("100.00"))

    first = reconcile_ledger(session, today=date(2026, 5, 25))
    second = reconcile_ledger(session, today=date(2026, 5, 25))

    assert first.cycles_posted_count == 2
    assert second.cycles_posted_count == 0
    assert session.query(BillingCycle).count() == 2


def test_reconcile_respects_job_lock(session, active_member):
    session.add(
        JobLock(
            name="reconcile_ledger",
            owner_id="someone-else",
            acquired_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc).replace(year=2099),
        )
    )
    session.commit()

    outcome = reconcile_ledger(session, today=date(2026, 5, 25))

    assert outcome.state == "running"
    assert session.query(BillingCycle).count() == 0


def test_cycle_math_and_balances_are_correct(session, active_member, second_active_member, monkeypatch):
    monkeypatch.setattr(fx_service, "fetch_historical_fx_rate", lambda _: Decimal("100.00"))

    reconcile_ledger(session, today=date(2026, 4, 25))
    charges = session.query(MemberCharge).order_by(MemberCharge.member_id).all()
    assert [charge.charge_rub for charge in charges] == [Decimal("400.00"), Decimal("400.00")]

    balances = list_member_balances(session)
    assert all(balance.balance_rub == Decimal("-400.00") for balance in balances)
