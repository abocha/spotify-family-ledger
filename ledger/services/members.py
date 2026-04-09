"""Member management service."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledger.models import Member
from ledger.schemas import SaveMemberCommand


def save_member(session: Session, cmd: SaveMemberCommand) -> Member:
    if cmd.active_to is not None and cmd.active_to <= cmd.active_from:
        raise ValueError("Active To must be later than Active From.")

    duplicate_query = session.query(Member).filter(Member.display_name == cmd.display_name)
    if cmd.member_id is not None:
        duplicate_query = duplicate_query.filter(Member.id != cmd.member_id)
    if duplicate_query.first() is not None:
        raise ValueError(f"A member named '{cmd.display_name}' already exists.")

    if cmd.member_id is None:
        member = Member(
            display_name=cmd.display_name,
            active_from=cmd.active_from,
            active_to=cmd.active_to,
            counted_in_denominator=cmd.counted_in_denominator,
            billable_after_cutover=cmd.billable_after_cutover,
            note=cmd.note,
        )
        session.add(member)
    else:
        member = session.get(Member, cmd.member_id)
        if member is None:
            raise ValueError(f"Member with id {cmd.member_id} not found.")
        member.display_name = cmd.display_name
        member.active_from = cmd.active_from
        member.active_to = cmd.active_to
        member.counted_in_denominator = cmd.counted_in_denominator
        member.billable_after_cutover = cmd.billable_after_cutover
        member.note = cmd.note

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("Could not save member because it violates a database constraint.") from exc

    return member
