"""Yacht — five dice, three rolls, thirteen boxes — for two to six players.

A turn is small and complete: roll, keep what helps, roll again, then write one
category. The engine owns the scorecard so the panel never has to agree with
the server about what a full house is worth. Categories are never overwritten,
and a table ends when every card is full; the highest total, bonus included,
takes the room.

The upper bonus is the one rule people forget, so it is computed here and
returned with the totals instead of being a note in the panel.
"""
import random

from .registry import Game, GameError

CATEGORIES = ("ones", "twos", "threes", "fours", "fives", "sixes",
              "three_kind", "four_kind", "full_house", "small_straight",
              "large_straight", "yacht", "chance")
UPPER = CATEGORIES[:6]
BONUS = 35
BONUS_TARGET = 63
DICE = 5


def _score(dice, category):
    """What this roll would be worth in this box. Zero is a legal answer."""
    counts = [dice.count(value) for value in range(1, 7)]
    total = sum(dice)
    if category in UPPER:
        return dice.count(UPPER.index(category) + 1) * (UPPER.index(category) + 1)
    if category == "three_kind":
        return total if max(counts) >= 3 else 0
    if category == "four_kind":
        return total if max(counts) >= 4 else 0
    if category == "full_house":
        return 25 if sorted(counts) == [0, 0, 0, 0, 2, 3] else 0
    if category in ("small_straight", "large_straight"):
        runs, best = 0, 0
        for value in range(6):
            runs = runs + 1 if counts[value] else 0
            best = max(best, runs)
        if category == "small_straight":
            return 30 if best >= 4 else 0
        return 40 if best >= 5 else 0
    if category == "yacht":
        return 50 if max(counts) == DICE else 0
    if category == "chance":
        return total
    return 0


class Yacht(Game):
    key = "yacht"
    name = "Yacht"
    seats = (2, 3, 4, 5, 6)
    turn_seconds = 45
    summary = "Roll five dice three times, then lock one of thirteen boxes."

    def new(self, seat_count):
        count = int(seat_count)
        if count not in self.seats:
            raise GameError("Yacht seats two to six players")
        return {"dice": [0] * DICE, "kept": [False] * DICE, "rolls": 0,
                "scores": [[None] * len(CATEGORIES) for _ in range(count)],
                "turn": 0, "seats": count, "winner": None, "last": None}

    # ── rules ────────────────────────────────────────────────────────────────
    def legal(self, state, seat):
        if state.get("winner") is not None or int(state["turn"]) != int(seat):
            return []
        moves = [{"action": "hold", "index": index} for index in range(DICE)]
        if int(state["rolls"]) < 3:
            moves.append({"action": "roll"})
        if int(state["rolls"]) > 0:
            moves += [{"action": "score", "category": CATEGORIES[index]}
                      for index, value in enumerate(state["scores"][int(seat)])
                      if value is None]
        return moves

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        action = str(move.get("action") or "").lower()
        if action == "roll":
            return self._roll(state, seat)
        if action == "hold":
            return self._hold(state, move)
        if action == "score":
            return self._write(state, seat, move)
        raise GameError("Roll, keep a die or write a score")

    def _roll(self, state, seat):
        if int(state["rolls"]) >= 3:
            raise GameError("Three rolls is the whole turn; write a score")
        dice = list(state["dice"])
        kept = list(state["kept"])
        for index in range(DICE):
            if not kept[index]:
                dice[index] = random.randint(1, 6)
        return {**state, "dice": dice, "rolls": int(state["rolls"]) + 1,
                "last": {"roll": list(dice)}}

    @staticmethod
    def _hold(state, move):
        if int(state["rolls"]) < 1:
            raise GameError("Roll before keeping a die")
        try:
            index = int(move.get("index"))
        except (TypeError, ValueError):
            raise GameError("Choose a die") from None
        if not 0 <= index < DICE:
            raise GameError("Choose a die")
        kept = list(state["kept"])
        kept[index] = not kept[index]
        return {**state, "kept": kept}

    def _write(self, state, seat, move):
        if int(state["rolls"]) < 1:
            raise GameError("Roll before writing a score")
        category = str(move.get("category") or "")
        if category not in CATEGORIES:
            raise GameError("Choose one of the thirteen boxes")
        index = CATEGORIES.index(category)
        scores = [list(row) for row in state["scores"]]
        if scores[int(seat)][index] is not None:
            raise GameError("That box is already filled")
        scores[int(seat)][index] = _score(state["dice"], category)
        new_state = {**state, "scores": scores,
                     "dice": [0] * DICE, "kept": [False] * DICE, "rolls": 0,
                     "last": {"seat": int(seat), "category": category,
                              "points": scores[int(seat)][index]}}
        if all(value is not None for row in scores for value in row):
            totals = [self._total(scores[row]) for row in range(int(state["seats"]))]
            best = max(totals)
            winner = totals.index(best) if totals.count(best) == 1 else "draw"
            return {**new_state, "winner": winner}
        return {**new_state, "turn": self.next_seat(state)}

    @staticmethod
    def _total(row):
        upper = sum(value or 0 for value in row[:6])
        return sum(value or 0 for value in row) + (BONUS if upper >= BONUS_TARGET else 0)

    def totals(self, state):
        return [self._total(row) for row in state["scores"]]

    def view(self, state, seat):
        """Add the numbers the panel would otherwise have to recompute."""
        visible = dict(state)
        visible["preview"] = (
            {CATEGORIES[index]: _score(state["dice"], CATEGORIES[index])
             for index, value in enumerate(state["scores"][int(seat)])
             if value is None}
            if int(state["rolls"]) > 0 else {}
        )
        visible["totals"] = self.totals(state)
        visible["categories"] = list(CATEGORIES)
        return visible

    def auto(self, state):
        """Play a whole turn for an absent player, not a third of one.

        A timeout that rolled once and stopped would leave the room waiting on
        the same chair for another minute. Three rolls, then the best box.
        """
        seat = int(state["turn"])
        while int(state["rolls"]) < 3:
            state = self._roll(state, seat)
        open_boxes = [category for category, value in enumerate(state["scores"][seat])
                      if value is None]
        if not open_boxes:
            return self.pass_turn(state)
        best = max(open_boxes, key=lambda category: _score(state["dice"], CATEGORIES[category]))
        return self._write(state, seat, {"category": CATEGORIES[best]})
