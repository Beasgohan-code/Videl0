"""Chinese Checkers for two, three, four or six players.

The board is a hexagram of 121 holes. Rather than storing a picture of it, the
engine builds the star from seventeen rows of holes — 1, 2, 3, 4, 13, 12, 11,
10, 9, 10, 11, 12, 13, 4, 3, 2, 1 — laid on a triangular lattice. Two holes
are neighbours when they are one row apart and half a column offset, so the
same arithmetic describes a step and a jump for every seat.

A move is a step onto an empty neighbouring hole, or one or more jumps over an
occupied hole into the empty one directly beyond it. Chain jumps may turn, and
a player may stop anywhere along the chain. The first player to fill the camp
opposite their own with all ten pegs wins.

The geometry ships with the room state (``holes`` and ``camps``) so the panel
never has to guess where a hole is; a client drawing its own star would drift
from the server the first time a board changed.
"""
from .registry import Game, GameError

ROWS = (1, 2, 3, 4, 13, 12, 11, 10, 9, 10, 11, 12, 13, 4, 3, 2, 1)
#: (row delta, doubled-column delta) for the six neighbouring holes.
STEPS = ((0, -2), (0, 2), (-1, -1), (-1, 1), (1, -1), (1, 1))
#: Which camp each seat starts in, for each supported table size. Camps are
#: ordered around the star, so the opposite camp is always three along.
CAMPS_FOR = {2: (0, 3), 3: (0, 2, 4), 4: (0, 1, 3, 4), 6: (0, 1, 2, 3, 4, 5)}


def _build():
    holes, index = [], {}
    for row, count in enumerate(ROWS):
        for position in range(count):
            # Stored doubled so half-columns stay integers.
            x2 = 2 * position - (count - 1)
            index[(row, x2)] = len(holes)
            holes.append((row, x2))
    neighbours = [
        [index[(row + dr, x2 + dx)] for dr, dx in STEPS if (row + dr, x2 + dx) in index]
        for row, x2 in holes
    ]
    camps = []
    for vertex in (
        index[(0, 0)], index[(4, -12)], index[(12, -12)],
        index[(16, 0)], index[(12, 12)], index[(4, 12)],
    ):
        camp = [vertex]
        while len(camp) < 10:
            added = False
            for hole in list(camp):
                for neighbour in neighbours[hole]:
                    if neighbour not in camp:
                        camp.append(neighbour)
                        added = True
                        if len(camp) == 10:
                            break
                if len(camp) == 10:
                    break
            if not added:
                break
        camps.append(tuple(camp[:10]))
    return tuple(holes), index, neighbours, tuple(camps)


HOLES, INDEX, NEIGHBOURS, CAMPS = _build()


class ChineseCheckers(Game):
    key = "chinese"
    name = "Chinese Checkers"
    seats = (2, 3, 4, 6)
    turn_seconds = 60
    summary = "Hop the star and fill the camp opposite yours with ten pegs."

    def new(self, seat_count):
        count = int(seat_count)
        if count not in CAMPS_FOR:
            raise GameError("Chinese Checkers seats two, three, four or six players")
        homes = list(CAMPS_FOR[count])
        return {"holes": [[row, x2] for row, x2 in HOLES],
                "camps": [list(camp) for camp in CAMPS],
                "homes": homes,
                "targets": [(home + 3) % 6 for home in homes],
                "pegs": [list(CAMPS[home]) for home in homes],
                "turn": 0, "seats": count, "winner": None, "last": None}

    # ── board helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _board(state):
        board = [-1] * len(HOLES)
        for seat, pegs in enumerate(state["pegs"]):
            for hole in pegs:
                board[int(hole)] = seat
        return board

    @staticmethod
    def _destinations(board, peg):
        """Every hole this peg can reach: one step, or a chain of jumps."""
        reached = []
        for neighbour in NEIGHBOURS[peg]:
            if board[neighbour] < 0:
                reached.append(neighbour)
        seen = {peg}
        frontier = [peg]
        while frontier:
            current = frontier.pop()
            row, x2 = HOLES[current]
            for neighbour in NEIGHBOURS[current]:
                if board[neighbour] < 0:
                    continue
                land = INDEX.get((2 * HOLES[neighbour][0] - row,
                                  2 * HOLES[neighbour][1] - x2))
                if land is None or land in seen or board[land] >= 0:
                    continue
                seen.add(land)
                reached.append(land)
                frontier.append(land)
        return sorted(set(reached))

    def _moves(self, state, seat):
        board = self._board(state)
        return [{ "from": int(peg), "to": destination}
                for peg in state["pegs"][int(seat)]
                for destination in self._destinations(board, int(peg))]

    def legal(self, state, seat):
        if state.get("winner") is not None or int(state["turn"]) != int(seat):
            return []
        return self._moves(state, seat)

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        try:
            origin, destination = int(move.get("from")), int(move.get("to"))
        except (TypeError, ValueError):
            raise GameError("Choose a peg and a hole") from None
        pegs = [list(row) for row in state["pegs"]]
        if origin not in pegs[int(seat)]:
            raise GameError("That peg is not yours")
        if destination not in self._destinations(self._board(state), origin):
            raise GameError("A peg moves to a neighbouring hole or jumps a line")
        pegs[int(seat)][pegs[int(seat)].index(origin)] = destination
        new_state = {**state, "pegs": pegs,
                     "last": {"from": origin, "to": destination}}
        target = CAMPS[int(state["targets"][int(seat)])]
        if all(hole in pegs[int(seat)] for hole in target):
            return {**new_state, "winner": int(seat)}
        return {**new_state, "turn": self.next_seat(state)}

    def auto(self, state):
        options = self.legal(state, state["turn"])
        if not options:
            return self.pass_turn(state)
        return self.apply(state, state["turn"], options[0])
