"""Public multiplayer games for the Videl arcade.

The client is never authoritative. It sends a move, the engine validates it
against the stored state, and the store writes the result only if the room's
version still matches. A replayed or forged move is refused rather than merged.

Every engine keeps its state as plain JSON types so the room document is a
straight read and the panel needs no custom serialisation.
"""
from __future__ import annotations


class GameError(ValueError):
    """A move the rules reject. ``status`` maps onto the HTTP answer."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Game:
    key = ""
    name = ""
    seats = (2,)
    #: How long a live turn may take before the server plays for the absent
    #: player. Short enough to keep a room moving, long enough to answer a call.
    turn_seconds = 60
    #: A room nobody touches is abandoned after this, not left forever.
    idle_seconds = 24 * 3600
    summary = ""

    def new(self, seat_count):
        raise NotImplementedError

    def legal(self, state, seat):
        raise NotImplementedError

    def apply(self, state, seat, move):
        raise NotImplementedError

    def auto(self, state):
        """The move the server makes for a player who ran out of time.

        One deterministic legal move, or a pass when the rules allow none. It
        is deliberately not random: the same room always settles the same way,
        which keeps the timeout behaviour testable.
        """
        options = [option for option in self.legal(state, state["turn"])
                   if "column" in option or "cell" in option or "token" in option]
        if not options:
            return self.pass_turn(state)
        return self.apply(state, state["turn"], options[0])

    def pass_turn(self, state):
        state = dict(state)
        state["turn"] = self.next_seat(state)
        return state

    def next_seat(self, state):
        return (int(state["turn"]) + 1) % int(state["seats"])

    def view(self, state, seat):
        """What this seat may see. No engine hides information yet."""
        return state

    def result(self, state):
        return state.get("winner")

    def describe(self):
        return {"key": self.key, "name": self.name, "seats": list(self.seats),
                "turn_seconds": self.turn_seconds, "summary": self.summary}


def run_length(board, index, player, rows, cols, dr, dc):
    """Length of the run of ``player`` through ``index`` along (dr, dc)."""
    if board[index] != player:
        return 0
    row, col = divmod(index, cols)
    total = 1
    for sign in (1, -1):
        r, c = row + dr * sign, col + dc * sign
        while 0 <= r < rows and 0 <= c < cols and board[r * cols + c] == player:
            total += 1
            r += dr * sign
            c += dc * sign
    return total


def occupied(board, index):
    return bool(board[index])


def seat_of(state):
    return int(state.get("turn", 0))
