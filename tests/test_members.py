from datetime import date

import pytest

from ledger.services.members import save_member


def test_save_member_rejects_duplicate_name(session, active_member):
    with pytest.raises(ValueError, match="already exists"):
        save_member(
            session,
            display_name=active_member.display_name,
            active_from=date(2026, 1, 1),
            active_to=None,
            counted_in_denominator=True,
            billable_after_cutover=True,
        )


def test_save_member_rejects_invalid_date_range(session):
    with pytest.raises(ValueError, match="later than Active From"):
        save_member(
            session,
            display_name="Test Member",
            active_from=date(2026, 5, 20),
            active_to=date(2026, 5, 20),
            counted_in_denominator=True,
            billable_after_cutover=True,
        )
