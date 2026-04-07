"""Member service — validation and create/update helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledger.models import Member


def save_member(
    session: Session,
    *,
    display_name: str,
    active_from: date,
    active_to: date | None,
    counted_in_denominator: bool,
    billable_after_cutover: bool,
    note: str | None = None,
    member_id: int | None = None,
) -> Member:
    normalized_name = " ".join(display_name.split())
    normalized_note = "\n".join(line.rstrip() for line in (note or "").strip().splitlines()) or None

    if not normalized_name:
        raise ValueError("Display Name is required.")
    if active_to is not None and active_to <= active_from:
        raise ValueError("Active To must be later than Active From.")

    duplicate_query = session.query(Member).filter(Member.display_name == normalized_name)
    if member_id is not None:
        duplicate_query = duplicate_query.filter(Member.id != member_id)
    duplicate = duplicate_query.first()
    if duplicate is not None:
        raise ValueError(f"A member named '{normalized_name}' already exists.")

    if member_id is None:
        member = Member(
            display_name=normalized_name,
            active_from=active_from,
            active_to=active_to,
            counted_in_denominator=counted_in_denominator,
            billable_after_cutover=billable_after_cutover,
            note=normalized_note,
        )
        session.add(member)
    else:
        member = session.get(Member, member_id)
        if member is None:
            raise ValueError(f"Member with id {member_id} not found")
        member.display_name = normalized_name
        member.active_from = active_from
        member.active_to = active_to
        member.counted_in_denominator = counted_in_denominator
        member.billable_after_cutover = billable_after_cutover
        member.note = normalized_note

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("Could not save member because it violates a database constraint.") from exc

    return member
