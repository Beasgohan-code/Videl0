"""Ludo for two to four players.

One shared 52-cell ring, four start squares, four home columns. A token's
``progress`` is the number of steps it has travelled from its own start:

    -1        in the base, waiting for a six
     0..50    on the shared ring
     51..56   in its own home column
     57       home

The ring index of a token is ``(start[seat] + progress) % 52``. Captures only
happen on the ring, and never on a start or star square — the eight squares a
Ludo board marks as safe.

Two simplifications are deliberate and stated to the players: tokens may stack
on one square (no blocking), and the first player home wins the room rather
than the game continuing for second place.
"""
import random

from .registry import Game, GameError

RING = 52
HOME_PROGRESS = 57
STARTS = (0, 13, 26, 39)
SAFE = frozenset({0, 8, 13, 21, 26, 34, 39, 47})
OFFSETS = {2: (0, 2), 3: (0, 1, 2), 4: (0, 1, 2, 3)}


class Ludo(Game):
    key = "ludo"
    name = "Ludo"
    seats = (2, 3, 4)
    turn_seconds = 45
    summary = "Roll a six to leave the base, race four tokens home, capture on the way."

    def new(self, seat_count):
        count = int(seat_count)
        if count not in OFFSETS:
            raise GameError("Ludo is for two, three or four players")
        return {"tokens": [[-1] * 4 for _ in range(count)], "roll": None,
                "turn": 0, "seats": count, "sixes": 0, "winner": None,
                "starts": [STARTS[index] for index in OFFSETS[count]],
                "last": None}

    # ── rules ────────────────────────────────────────────────────────────────
    def _start(self, state, seat):
        return STARTS[OFFSETS[int(state["seats"])][int(seat)]]

    def _on_ring(self, state, seat, progress):
        return (self._start(state, seat) + progress) % RING

    def _captures(self, state, seat, progress):
        if progress < 0 or progress > 50:
            return []
        square = self._on_ring(state, seat, progress)
        if square in SAFE:
            return []
        hits = []
        for other, tokens in enumerate(state["tokens"]):
            if other == int(seat):
                continue
            for index, value in enumerate(tokens):
                if 0 <= value <= 50 and self._on_ring(state, other, value) == square:
                    hits.append((other, index))
        return hits

    def _moves(self, state, seat):
        roll = state.get("roll")
        if roll is None:
            return []
        moves = []
        for index, progress in enumerate(state["tokens"][int(seat)]):
            if progress == -1 and roll == 6:
                moves.append(index)
            elif progress >= 0 and progress + roll <= HOME_PROGRESS:
                moves.append(index)
        return moves

    def legal(self, state, seat):
        if state.get("winner") is not None or int(state["turn"]) != int(seat):
            return []
        if state.get("roll") is None:
            return [{"action": "roll"}]
        moves = self._moves(state, seat)
        if not moves:
            return [{"action": "pass"}]
        return [{"action": "move", "token": index} for index in moves]

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        action = str(move.get("action") or "").lower()
        if action == "roll":
            return self._roll(state, seat)
        if action == "pass":
            if state.get("roll") is None:
                raise GameError("Roll before passing")
            return self._advance(state, int(seat))
        if action == "move":
            return self._move(state, seat, move)
        raise GameError("Choose roll, move or pass")

    def _roll(self, state, seat):
        if state.get("roll") is not None:
            raise GameError("You already rolled; move a token")
        roll = random.randint(1, 6)
        sixes = int(state.get("sixes") or 0)
        if roll == 6:
            sixes += 1
            if sixes >= 3:
                # Three sixes forfeit the turn, as on a physical board.
                return self._advance({**state, "roll": None, "last":
                                      {"triple_six": True}}, int(seat))
        else:
            sixes = 0
        return {**state, "roll": roll, "sixes": sixes, "last": None}

    def _move(self, state, seat, move):
        roll = state.get("roll")
        if roll is None:
            raise GameError("Roll the die first")
        try:
            token = int(move.get("token"))
        except (TypeError, ValueError):
            raise GameError("Choose one of your tokens") from None
        tokens = [list(row) for row in state["tokens"]]
        if not 0 <= token < 4:
            raise GameError("Choose one of your tokens")
        progress = tokens[int(seat)][token]
        if progress == -1:
            if roll != 6:
                raise GameError("You need a six to leave the base")
            target = 0
        else:
            target = progress + roll
            if target > HOME_PROGRESS:
                raise GameError("That token needs an exact roll to get home")
        captured = self._captures(state, seat, target)
        tokens[int(seat)][token] = target
        for other, index in captured:
            tokens[other][index] = -1
        last = {"token": token, "from": progress, "to": target,
                "captured": [list(pair) for pair in captured], "roll": roll}
        winner = int(seat) if all(value == HOME_PROGRESS for value in tokens[int(seat)]) else None
        if winner is not None:
            return {**state, "tokens": tokens, "roll": None, "sixes": 0,
                    "winner": winner, "last": last}
        if roll == 6:
            # A six keeps the turn, but the player must roll again.
            return {**state, "tokens": tokens, "roll": None, "sixes": 1,
                    "last": last}
        return {**self._advance(state, int(seat)), "tokens": tokens, "last": last}

    def _advance(self, state, seat):
        seats = int(state["seats"])
        return {**state, "turn": (seat + 1) % seats, "roll": None, "sixes": 0}

    def auto(self, state):
        """Settle a timeout: roll if needed, move if possible, otherwise pass."""
        seat = int(state["turn"])
        if state.get("roll") is None:
            state = self._roll(state, seat)
            if state.get("roll") is None:
                return state          # three sixes already ended the turn
        moves = self._moves(state, seat)
        if moves:
            return self._move(state, seat, {"token": moves[0]})
        return self._advance(state, seat)
