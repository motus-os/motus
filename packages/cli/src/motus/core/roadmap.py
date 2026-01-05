# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Frictionless Roadmap API for Motus.

Stripe/Spotify-inspired "Pit of Success" design:
- Every call returns actionable next steps
- Errors tell you exactly what to do
- No raw SQL needed by agents

6-Call API:
- ready()     - What can I work on right now?
- claim(id)   - Claim item (blocks if prereqs unmet)
- complete(id)- Mark complete (validates deps satisfied)
- status(id)  - Check status + blockers
- release(id) - Release claim without completing
- my_work()   - What am I currently assigned to?
"""

from dataclasses import dataclass, field
from typing import Any

from motus.logging import get_logger

from ..observability.roles import Role, get_agent_role
from .database_connection import get_db_manager
from .errors import MotusError

logger = get_logger(__name__)


class RoadmapError(MotusError):
    """Roadmap operation failed.

    Error codes:
    - ROAD-001: Item not found
    - ROAD-002: Prerequisites not complete
    - ROAD-003: Already claimed by another agent
    - ROAD-004: Item not in claimable state
    - ROAD-005: Cannot complete (validation failed)
    - ROAD-006: Not assigned to you
    """

    pass


@dataclass
class RoadmapResponse:
    """Frictionless response with actionable next steps.

    Stripe pattern: Every response tells you what to do next.
    """

    success: bool
    data: Any = None
    message: str = ""
    action: str = ""  # What to do next
    command: str = ""  # Exact command to run
    blockers: list[str] = field(default_factory=list)


@dataclass
class MissingPrereq:
    """Missing prerequisite for a roadmap item."""

    item_id: str
    prereq_type: str  # approval_required, blocker_unresolved, dependency_incomplete
    prereq_id: str
    prereq_status: str
    prereq_title: str = ""


@dataclass
class RoadmapItem:
    """Roadmap item with dependency context."""

    id: str
    title: str
    status: str
    rank: float
    assignee: str | None = None
    is_blocked: bool = False
    blockers: list[str] = field(default_factory=list)
    blocking_count: int = 0
    missing_prereqs: list[MissingPrereq] = field(default_factory=list)


def get_missing_prereqs(item_id: str) -> list[MissingPrereq]:
    """Query v_missing_prereqs for an item.

    Args:
        item_id: Roadmap item ID to check

    Returns:
        List of MissingPrereq for the item
    """
    try:
        db = get_db_manager()
        with db.connection() as conn:
            rows = conn.execute(
                """
                SELECT item_id, prereq_type, prereq_id, prereq_status, prereq_title
                FROM v_missing_prereqs
                WHERE item_id = ?
                """,
                (item_id,),
            ).fetchall()
            return [
                MissingPrereq(
                    item_id=row["item_id"],
                    prereq_type=row["prereq_type"],
                    prereq_id=row["prereq_id"],
                    prereq_status=row["prereq_status"],
                    prereq_title=row["prereq_title"] or "",
                )
                for row in rows
            ]
    except Exception as e:
        logger.debug(f"get_missing_prereqs failed: {e}")
        return []


class RoadmapAPI:
    """Frictionless API for roadmap operations."""

    def __init__(self, agent_id: str = "default"):
        """Initialize API with agent identity.

        Args:
            agent_id: Identifier for the calling agent (for claims)
        """
        self.agent_id = agent_id
        self._db = get_db_manager()

    def ready(self) -> RoadmapResponse:
        """Get items ready to work on (no blocking dependencies).

        Returns items that:
        - Have status 'pending' or 'in_progress'
        - Have all blocking dependencies completed
        - Are not claimed by another agent

        Returns:
            RoadmapResponse with list of RoadmapItem
        """
        try:
            with self._db.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, rank
                    FROM v_ready_items
                    ORDER BY rank ASC
                    LIMIT 20
                    """
                ).fetchall()

                # Items in v_ready_items are always 'pending' (view filter)
                items = [
                    RoadmapItem(
                        id=row["id"],
                        title=row["title"],
                        status="pending",
                        rank=row["rank"] or 0.0,
                    )
                    for row in rows
                ]

                if not items:
                    return RoadmapResponse(
                        success=True,
                        data=[],
                        message="No items ready - all have blocking dependencies",
                        action="Check blocked items with: motus roadmap blocked",
                        command="motus roadmap blocked",
                    )

                first_item = items[0]
                return RoadmapResponse(
                    success=True,
                    data=items,
                    message=f"{len(items)} items ready to work on",
                    action=f"Claim the highest priority item: {first_item.title}",
                    command=f"motus roadmap claim {first_item.id}",
                )

        except Exception as e:
            logger.error(f"ready() failed: {e}")
            return RoadmapResponse(
                success=False,
                message=str(e),
                action="Check database connection",
                command="motus health",
            )

    def claim(self, item_id: str) -> RoadmapResponse:
        """Claim a roadmap item for work.

        Validates:
        - Item exists and is not deleted
        - Item is in claimable state (pending/in_progress)
        - All blocking dependencies are complete
        - Not already claimed by another agent

        Args:
            item_id: ID of item to claim

        Returns:
            RoadmapResponse with claim result
        """
        try:
            with self._db.transaction() as conn:
                # Check item exists
                item = conn.execute(
                    """
                    SELECT id, title, status_key
                    FROM roadmap_items
                    WHERE id = ? AND deleted_at IS NULL
                    """,
                    (item_id,),
                ).fetchone()

                if not item:
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-001] Item '{item_id}' not found",
                        action="List available items",
                        command="motus roadmap ready",
                    )

                # Check not already claimed
                existing = conn.execute(
                    """
                    SELECT agent_id FROM roadmap_assignments
                    WHERE item_id = ? AND status IN ('assigned', 'active')
                    """,
                    (item_id,),
                ).fetchone()

                if existing:
                    if existing["agent_id"] == self.agent_id:
                        return RoadmapResponse(
                            success=True,
                            data={"item_id": item_id, "status": "already_claimed"},
                            message="Already claimed by you",
                            action="Start working or complete when done",
                            command=f"motus roadmap complete {item_id}",
                        )
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-003] Already claimed by {existing['agent_id']}",
                        action="Choose a different item",
                        command="motus roadmap ready",
                    )

                # Check blocking dependencies
                blockers = conn.execute(
                    """
                    SELECT prereq_id, prereq_title
                    FROM v_prerequisite_chain
                    WHERE root_item_id = ? AND is_complete = 0
                    ORDER BY depth ASC
                    """,
                    (item_id,),
                ).fetchall()

                if blockers:
                    blocker_list = [
                        f"{b['prereq_id']}: {b['prereq_title']}" for b in blockers
                    ]
                    first_blocker = blockers[0]
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-002] {len(blockers)} prerequisites not complete",
                        blockers=blocker_list,
                        action=f"Complete blocker first: {first_blocker['prereq_title']}",
                        command=f"motus roadmap claim {first_blocker['prereq_id']}",
                    )

                # Create assignment
                conn.execute(
                    """
                    INSERT INTO roadmap_assignments (item_id, agent_id, status)
                    VALUES (?, ?, 'assigned')
                    """,
                    (item_id, self.agent_id),
                )

                # Update item status to in_progress
                conn.execute(
                    """
                    UPDATE roadmap_items
                    SET status_key = 'in_progress', updated_at = datetime('now')
                    WHERE id = ? AND status_key = 'pending'
                    """,
                    (item_id,),
                )

                return RoadmapResponse(
                    success=True,
                    data={"item_id": item_id, "title": item["title"]},
                    message=f"Claimed: {item['title']}",
                    action="Work on this item, then mark complete",
                    command=f"motus roadmap complete {item_id}",
                )

        except Exception as e:
            logger.error(f"claim({item_id}) failed: {e}")
            return RoadmapResponse(
                success=False,
                message=str(e),
                action="Check item status",
                command=f"motus roadmap status {item_id}",
            )

    def complete(self, item_id: str) -> RoadmapResponse:
        """Mark a roadmap item as complete.

        Validates:
        - Item exists
        - Item is assigned to calling agent
        - All blocking dependencies are complete

        Args:
            item_id: ID of item to complete

        Returns:
            RoadmapResponse with completion result
        """
        try:
            is_reviewer = get_agent_role(self.agent_id) == Role.REVIEWER
            if not is_reviewer:
                return RoadmapResponse(
                    success=False,
                    message=(
                        "[ROAD-010] Only reviewers can mark items complete. "
                        "Use 'motus roadmap review' instead."
                    ),
                    action="Set MC_REVIEWER=1 if you are the designated reviewer",
                    command="motus roadmap review <id>",
                )

            with self._db.transaction() as conn:
                # Check assignment
                assignment = conn.execute(
                    """
                    SELECT id, agent_id FROM roadmap_assignments
                    WHERE item_id = ? AND status IN ('assigned', 'active')
                    """,
                    (item_id,),
                ).fetchone()

                if not assignment:
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-006] Item '{item_id}' not assigned",
                        action="Claim the item first",
                        command=f"motus roadmap claim {item_id}",
                    )

                if assignment["agent_id"] != self.agent_id and not is_reviewer:
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-006] Assigned to {assignment['agent_id']}, not you",
                        action="Ask them to complete or release",
                        command="motus roadmap ready",
                    )

                # Update item status
                conn.execute(
                    """
                    UPDATE roadmap_items
                    SET status_key = 'completed', updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (item_id,),
                )

                # Update assignment
                conn.execute(
                    """
                    UPDATE roadmap_assignments
                    SET status = 'completed', completed_at = datetime('now')
                    WHERE id = ?
                    """,
                    (assignment["id"],),
                )

                # Check what's now unblocked
                unblocked = conn.execute(
                    """
                    SELECT DISTINCT ri.id, ri.title
                    FROM roadmap_dependencies rd
                    JOIN roadmap_items ri ON ri.id = rd.item_id
                    WHERE rd.depends_on_id = ?
                      AND ri.status_key != 'completed'
                      AND ri.deleted_at IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM roadmap_dependencies rd2
                          JOIN roadmap_items ri2 ON ri2.id = rd2.depends_on_id
                          WHERE rd2.item_id = ri.id
                            AND ri2.status_key != 'completed'
                            AND rd2.dependency_type = 'blocks'
                      )
                    LIMIT 5
                    """,
                    (item_id,),
                ).fetchall()

                if unblocked:
                    first = unblocked[0]
                    return RoadmapResponse(
                        success=True,
                        data={
                            "item_id": item_id,
                            "unblocked": [u["id"] for u in unblocked],
                        },
                        message=f"Completed. {len(unblocked)} items now unblocked.",
                        action=f"Work on unblocked item: {first['title']}",
                        command=f"motus roadmap claim {first['id']}",
                    )

                return RoadmapResponse(
                    success=True,
                    data={"item_id": item_id},
                    message="Completed",
                    action="Check what's ready next",
                    command="motus roadmap ready",
                )

        except Exception as e:
            logger.error(f"complete({item_id}) failed: {e}")
            return RoadmapResponse(
                success=False,
                message=str(e),
                action="Check item status",
                command=f"motus roadmap status {item_id}",
            )

    def status(self, item_id: str) -> RoadmapResponse:
        """Get detailed status of a roadmap item.

        Args:
            item_id: ID of item to check

        Returns:
            RoadmapResponse with item status and blockers
        """
        try:
            with self._db.connection() as conn:
                item = conn.execute(
                    """
                    SELECT id, title, status_key, rank
                    FROM roadmap_items
                    WHERE id = ? AND deleted_at IS NULL
                    """,
                    (item_id,),
                ).fetchone()

                if not item:
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-001] Item '{item_id}' not found",
                        action="List available items",
                        command="motus roadmap ready",
                    )

                # Get assignment
                assignment = conn.execute(
                    """
                    SELECT agent_id, status FROM roadmap_assignments
                    WHERE item_id = ? AND status IN ('assigned', 'active')
                    """,
                    (item_id,),
                ).fetchone()

                # Get blockers
                blockers = conn.execute(
                    """
                    SELECT prereq_id, prereq_title, prereq_status, depth
                    FROM v_prerequisite_chain
                    WHERE root_item_id = ?
                    ORDER BY depth ASC
                    """,
                    (item_id,),
                ).fetchall()

                incomplete_blockers = [
                    f"{b['prereq_id']}: {b['prereq_title']} ({b['prereq_status']})"
                    for b in blockers
                    if b["prereq_status"] != "completed"
                ]

                result = RoadmapItem(
                    id=item["id"],
                    title=item["title"],
                    status=item["status_key"],
                    rank=item["rank"] or 0.0,
                    assignee=assignment["agent_id"] if assignment else None,
                    is_blocked=len(incomplete_blockers) > 0,
                    blockers=incomplete_blockers,
                )

                if item["status_key"] == "completed":
                    return RoadmapResponse(
                        success=True,
                        data=result,
                        message="Item is complete",
                        action="Check what's ready next",
                        command="motus roadmap ready",
                    )

                if incomplete_blockers:
                    first_blocker_id = blockers[0]["prereq_id"]
                    return RoadmapResponse(
                        success=True,
                        data=result,
                        blockers=incomplete_blockers,
                        message=f"Blocked by {len(incomplete_blockers)} prerequisites",
                        action="Complete the first blocker",
                        command=f"motus roadmap claim {first_blocker_id}",
                    )

                if assignment:
                    if assignment["agent_id"] == self.agent_id:
                        return RoadmapResponse(
                            success=True,
                            data=result,
                            message="Assigned to you and ready",
                            action="Complete when done",
                            command=f"motus roadmap complete {item_id}",
                        )
                    return RoadmapResponse(
                        success=True,
                        data=result,
                        message=f"Assigned to {assignment['agent_id']}",
                        action="Choose a different item",
                        command="motus roadmap ready",
                    )

                return RoadmapResponse(
                    success=True,
                    data=result,
                    message="Ready to claim",
                    action="Claim this item",
                    command=f"motus roadmap claim {item_id}",
                )

        except Exception as e:
            logger.error(f"status({item_id}) failed: {e}")
            return RoadmapResponse(
                success=False,
                message=str(e),
                action="Check database connection",
                command="motus health",
            )

    def release(self, item_id: str) -> RoadmapResponse:
        """Release claim on an item without completing it.

        Args:
            item_id: ID of item to release

        Returns:
            RoadmapResponse with release result
        """
        try:
            with self._db.transaction() as conn:
                assignment = conn.execute(
                    """
                    SELECT id, agent_id FROM roadmap_assignments
                    WHERE item_id = ? AND status IN ('assigned', 'active')
                    """,
                    (item_id,),
                ).fetchone()

                if not assignment:
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-006] Item '{item_id}' not assigned",
                        action="Nothing to release",
                        command="motus roadmap ready",
                    )

                if assignment["agent_id"] != self.agent_id:
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-006] Assigned to {assignment['agent_id']}, not you",
                        action="You can't release another agent's claim",
                        command="motus roadmap ready",
                    )

                conn.execute(
                    """
                    UPDATE roadmap_assignments
                    SET status = 'released', completed_at = datetime('now')
                    WHERE id = ?
                    """,
                    (assignment["id"],),
                )

                return RoadmapResponse(
                    success=True,
                    data={"item_id": item_id},
                    message="Released claim",
                    action="Item is now available for others",
                    command="motus roadmap ready",
                )

        except Exception as e:
            logger.error(f"release({item_id}) failed: {e}")
            return RoadmapResponse(
                success=False,
                message=str(e),
                action="Check item status",
                command=f"motus roadmap status {item_id}",
            )

    def my_work(self) -> RoadmapResponse:
        """Get items currently assigned to this agent.

        Returns:
            RoadmapResponse with list of assigned items
        """
        try:
            with self._db.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT ri.id, ri.title, ri.status_key, ri.rank,
                           ra.status as assignment_status
                    FROM roadmap_assignments ra
                    JOIN roadmap_items ri ON ri.id = ra.item_id
                    WHERE ra.agent_id = ?
                      AND ra.status IN ('assigned', 'active')
                      AND ri.deleted_at IS NULL
                    ORDER BY ri.rank ASC
                    """,
                    (self.agent_id,),
                ).fetchall()

                items = [
                    RoadmapItem(
                        id=row["id"],
                        title=row["title"],
                        status=row["status_key"],
                        rank=row["rank"] or 0.0,
                        assignee=self.agent_id,
                    )
                    for row in rows
                ]

                if not items:
                    return RoadmapResponse(
                        success=True,
                        data=[],
                        message="No items assigned to you",
                        action="Claim something to work on",
                        command="motus roadmap ready",
                    )

                first_item = items[0]
                return RoadmapResponse(
                    success=True,
                    data=items,
                    message=f"{len(items)} items assigned to you",
                    action=f"Continue working on: {first_item.title}",
                    command=f"motus roadmap complete {first_item.id}",
                )

        except Exception as e:
            logger.error(f"my_work() failed: {e}")
            return RoadmapResponse(
                success=False,
                message=str(e),
                action="Check database connection",
                command="motus health",
            )

    def review(self, item_id: str, status: str = "review") -> RoadmapResponse:
        """Set roadmap item status (default: review).

        Args:
            item_id: ID of item to update
            status: New status (default: review)

        Returns:
            RoadmapResponse with update result
        """
        try:
            is_reviewer = get_agent_role(self.agent_id) == Role.REVIEWER
            valid_statuses = {
                "pending",
                "in_progress",
                "review",
                "blocked",
                "completed",
                "deferred",
            }
            if status not in valid_statuses:
                return RoadmapResponse(
                    success=False,
                    message=f"Invalid status '{status}'",
                    action="Use a valid status",
                    command="motus roadmap review <id> --status review",
                )

            if status == "completed" and not is_reviewer:
                return RoadmapResponse(
                    success=False,
                    message=(
                        "[ROAD-010] Only reviewers can mark items complete. "
                        "Use 'motus roadmap review' instead."
                    ),
                    action="Set MC_REVIEWER=1 if you are the designated reviewer",
                    command="motus roadmap review <id>",
                )

            if status != "review" and not is_reviewer:
                return RoadmapResponse(
                    success=False,
                    message="[ROAD-010] Builders can only set status to 'review'.",
                    action="Ask a reviewer to update status or mark complete",
                    command="motus roadmap review <id> --status review",
                )

            with self._db.transaction() as conn:
                item = conn.execute(
                    """
                    SELECT id, title, status_key
                    FROM roadmap_items
                    WHERE id = ? AND deleted_at IS NULL
                    """,
                    (item_id,),
                ).fetchone()

                if not item:
                    return RoadmapResponse(
                        success=False,
                        message=f"[ROAD-001] Item '{item_id}' not found",
                        action="List available items",
                        command="motus roadmap ready",
                    )

                old_status = item["status_key"]
                if old_status == status:
                    return RoadmapResponse(
                        success=True,
                        data={
                            "item_id": item_id,
                            "title": item["title"],
                            "old_status": old_status,
                            "new_status": status,
                        },
                        message=f"Already {status}",
                        action="Check item status",
                        command=f"motus roadmap status {item_id}",
                    )

                conn.execute(
                    """
                    UPDATE roadmap_items
                    SET status_key = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (status, item_id),
                )

                return RoadmapResponse(
                    success=True,
                    data={
                        "item_id": item_id,
                        "title": item["title"],
                        "old_status": old_status,
                        "new_status": status,
                    },
                    message=f"[{item_id}] {old_status} -> {status}",
                    action="Check item status",
                    command=f"motus roadmap status {item_id}",
                )

        except Exception as e:
            logger.error(f"review({item_id}) failed: {e}")
            return RoadmapResponse(
                success=False,
                message=str(e),
                action="Check item status",
                command=f"motus roadmap status {item_id}",
            )


# Module-level convenience functions (Stripe pattern: short paths)
_default_api: RoadmapAPI | None = None


def _get_api() -> RoadmapAPI:
    """Get default API instance."""
    global _default_api
    if _default_api is None:
        _default_api = RoadmapAPI()
    return _default_api


def ready() -> RoadmapResponse:
    """Get items ready to work on."""
    return _get_api().ready()


def claim(item_id: str) -> RoadmapResponse:
    """Claim a roadmap item."""
    return _get_api().claim(item_id)


def complete(item_id: str) -> RoadmapResponse:
    """Mark item complete."""
    return _get_api().complete(item_id)


def status(item_id: str) -> RoadmapResponse:
    """Get item status."""
    return _get_api().status(item_id)


def release(item_id: str) -> RoadmapResponse:
    """Release claim on item."""
    return _get_api().release(item_id)


def my_work() -> RoadmapResponse:
    """Get items assigned to you."""
    return _get_api().my_work()


def review(item_id: str, status: str = "review") -> RoadmapResponse:
    """Set item status (default: review)."""
    return _get_api().review(item_id, status=status)
