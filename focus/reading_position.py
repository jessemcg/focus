"""Case-local, in-memory reading positions for displayed Agent answers.

Positions are transient UI state only: they are never written to the saved
answer files.  Each entry is keyed by immutable answer ID and stores a
viewport text anchor (buffer offset of the top visible line) plus a scroll
fraction fallback for the case where the anchor can no longer be resolved.
The cache is bounded; eviction only loses a reading position, never an answer.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

DEFAULT_ANSWER_POSITION_CAPACITY = 100


@dataclass(frozen=True, slots=True)
class AnswerPosition:
    anchor_offset: int
    scroll_fraction: float


class AnswerPositionCache:
    """Bounded least-recently-used map of answer ID to reading position."""

    def __init__(self, capacity: int = DEFAULT_ANSWER_POSITION_CAPACITY) -> None:
        self._capacity = max(1, capacity)
        self._positions: OrderedDict[str, AnswerPosition] = OrderedDict()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._positions)

    def __contains__(self, answer_id: object) -> bool:
        return answer_id in self._positions

    def capture(
        self,
        answer_id: str,
        *,
        anchor_offset: int,
        scroll_fraction: float,
    ) -> None:
        if not answer_id:
            return
        position = AnswerPosition(
            anchor_offset=max(0, int(anchor_offset)),
            scroll_fraction=min(1.0, max(0.0, float(scroll_fraction))),
        )
        self._positions[answer_id] = position
        self._positions.move_to_end(answer_id)
        while len(self._positions) > self._capacity:
            self._positions.popitem(last=False)

    def get(self, answer_id: str) -> AnswerPosition | None:
        if not answer_id:
            return None
        position = self._positions.get(answer_id)
        if position is not None:
            self._positions.move_to_end(answer_id)
        return position

    def discard(self, answer_id: str) -> None:
        self._positions.pop(answer_id, None)

    def clear(self) -> None:
        self._positions.clear()
