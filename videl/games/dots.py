"""Dots and Boxes for two, three or four players.

Six columns and five rows of boxes, drawn with strokes rather than guessed:
the state owns every edge, so a client only asks to draw one and the engine
decides who closed what. Closing a box scores it and keeps the turn, which is
the whole tension of the game — the board offers you a choice between taking
one now and leaving three for the next player.
"""
from .registry import Game, GameError

ROWS = 5
COLS = 6
HORIZONTAL = (ROWS + 1) * COLS       # 36
VERTICAL = ROWS * (COLS + 1)         # 35
BOXES = ROWS * COLS                  # 30


class DotsAndBoxes(Game):
    key = "dots"
    name = "Dots & Boxes"
    seats = (2, 3, 4)
    turn_seconds = 45
    summary = "Draw one line. Close a box to score it and keep the turn."

    def new(self, seat_count):
        count = int(seat_count)
        if count not in self.seats:
            raise GameError("Dots & Boxes seats two, three or four players")
        return {"rows": ROWS, "cols": COLS, "h": [0] * HORIZONTAL,
                "v": [0] * VERTICAL, "owner": [-1] * BOXES,
                "scores": [0] * count, "turn": 0, "seats": count,
                "winner": None, "last": None}

    # ── rules ────────────────────────────────────────────────────────────────
    @staticmethod
    def _box_done(state, row, col):
        return bool(state["h"][row * COLS + col]
                    and state["h"][(row + 1) * COLS + col]
                    and state["v"][row * (COLS + 1) + col]
                    and state["v"][row * (COLS + 1) + col + 1])

    def legal(self, state, seat):
        if state.get("winner") is not None or int(state["turn"]) != int(seat):
            return []
        moves = [{"kind": "h", "index": index}
                 for index, drawn in enumerate(state["h"]) if not drawn]
        moves += [{"kind": "v", "index": index}
                  for index, drawn in enumerate(state["v"]) if not drawn]
        return moves

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        kind = str(move.get("kind") or "").lower()
        if kind not in ("h", "v"):
            raise GameError("Choose a vertical or horizontal line")
        try:
            index = int(move.get("index"))
        except (TypeError, ValueError):
            raise GameError("Choose a line") from None
        edges = list(state[kind])
        if not 0 <= index < len(edges):
            raise GameError("That line is off the board")
        if edges[index]:
            raise GameError("That line is already drawn")
        edges[index] = 1
        h, v = list(state["h"]), list(state["v"])
        if kind == "h":
            h[index] = 1
            row, col = divmod(index, COLS)
            touched = [(row - 1, col), (row, col)]
        else:
            v[index] = 1
            row, col = divmod(index, COLS + 1)
            touched = [(row, col - 1), (row, col)]
        owner = list(state["owner"])
        scores = list(state["scores"])
        closed = []
        for box_row, box_col in touched:
            if not (0 <= box_row < ROWS and 0 <= box_col < COLS):
                continue
            box = box_row * COLS + box_col
            if owner[box] == -1 and self._box_done({"h": h, "v": v}, box_row, box_col):
                owner[box] = int(seat)
                scores[int(seat)] += 1
                closed.append(box)
        finished = all(h) and all(v)
        winner = None
        if finished:
            best = max(scores)
            winner = scores.index(best) if scores.count(best) == 1 else "draw"
        last = {"kind": kind, "index": index, "closed": closed}
        if closed and not finished:
            # Closing a box is worth another line, the rule that makes the
            # last few moves a race rather than a formality.
            return {**state, "h": h, "v": v, "owner": owner, "scores": scores,
                    "last": last}
        return {**state, "h": h, "v": v, "owner": owner, "scores": scores,
                "turn": self.next_seat(state), "winner": winner, "last": last}

    def auto(self, state):
        options = self.legal(state, state["turn"])
        if not options:
            return self.pass_turn(state)
        return self.apply(state, state["turn"], options[0])
