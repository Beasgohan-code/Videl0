"""Checkers (draughts) for two seats, on the standard 8×8 diagonal board.

Written so the rules are the referee, not the panel: captures are compulsory,
the longest capture chain is the only one allowed, kings fly along open
diagonals, and a man that reaches the crown row ends its move there and is
crowned. That last sentence is the rule every kitchen table argues about, so
it is written down once, here, and tested.

The board is a flat list of 64 cells: ``0`` empty, ``1``/``2`` men for seats 0
and 1, ``3``/``4`` the crowned versions. A square is ``row * 8 + col``, so the
panel renders it with no lookup table.
"""
from .registry import Game, GameError

CROWN_FROM = {1: 3, 2: 4}
DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))

#: Own-turns without a capture before a side is called stale and loses.
STALE_TURNS = 40


def colour(cell):
    return 1 if cell in (1, 3) else 2 if cell in (2, 4) else 0


def crowned(cell):
    return cell in (3, 4)


def home_row(colour_value):
    return 7 if colour_value == 1 else 0


class Checkers(Game):
    key = "checkers"
    name = "Checkers"
    seats = (2,)
    turn_seconds = 75
    summary = "Draughts with forced chains and flying kings."

    def new(self, seat_count):
        board = [0] * 64
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 0:
                    continue  # play happens on the dark squares only
                if row < 3:
                    board[row * 8 + col] = 1
                elif row > 4:
                    board[row * 8 + col] = 2
        return {"board": board, "turn": 0, "winner": None, "seats": 2,
                "chain": None, "last": None, "moves": [0, 0], "quiet": 0}

    # ── rules ───────────────────────────────────────────────────────────────

    def _hops(self, board, cell):
        """Every one-hop move from this square, quiet and capturing.

        A man sees one square ahead; a king sees the whole diagonal, and can
        land anywhere behind a captured piece. Chain building reuses this.
        """
        piece = board[cell]
        if not piece:
            return []
        mine = colour(piece)
        king = crowned(piece)
        row, col = divmod(cell, 8)
        hops = []
        for dr, dc in DIAGONALS:
            if not king and dr != (1 if mine == 1 else -1):
                continue
            r, c = row + dr, col + dc
            passed = None
            while 0 <= r < 8 and 0 <= c < 8:
                at = r * 8 + c
                occupant = board[at]
                if occupant == 0:
                    if passed is None:
                        hops.append({"from": cell, "to": at, "via": None})
                        if not king:
                            break  # a man takes one square, no more
                    elif king:
                        hops.append({"from": cell, "to": at, "via": passed})
                    r, c = r + dr, c + dc
                    continue
                if passed is not None or colour(occupant) == mine:
                    break
                passed = at
                if not king:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 8 and 0 <= nc < 8 and board[nr * 8 + nc] == 0:
                        hops.append({"from": cell, "to": nr * 8 + nc, "via": at})
                    break
                r, c = r + dr, c + dc
        return hops

    @staticmethod
    def _land(board, hop):
        board = list(board)
        piece = board[hop["from"]]
        board[hop["from"]] = 0
        if hop["via"] is not None:
            board[hop["via"]] = 0
        board[hop["to"]] = piece
        return board

    def _chains(self, board, cell, piece, depth=0):
        """Every maximal capture chain starting at this square."""
        if depth > 12:  # a board cannot produce a longer chain than this
            return []
        hops = [hop for hop in self._hops(board, cell) if hop["via"] is not None]
        if not hops:
            return []
        mine = colour(piece)
        chains = []
        for hop in hops:
            after = self._land(board, hop)
            if not crowned(piece) and divmod(hop["to"], 8)[0] == home_row(mine):
                chains.append([hop])  # crowned: the move ends, no chain
                continue
            tail = self._chains(after, hop["to"], piece, depth + 1)
            chains.extend([[hop] + rest for rest in tail] or [[hop]])
        return chains

    def _moves(self, board, seat, cell=None):
        """Legal moves for a seat, applying compulsory capture and longest chain."""
        mine = int(seat) + 1
        squares = [cell] if cell is not None else range(64)
        chains = []
        for start in squares:
            piece = board[start]
            if piece and colour(piece) == mine:
                chains.extend(self._chains(board, start, piece))
        if chains:
            longest = max(len(chain) for chain in chains)
            return [chain for chain in chains if len(chain) == longest]
        if cell is not None:
            return []  # a capture was on the board somewhere else
        steps = []
        for start in squares:
            piece = board[start]
            if piece and colour(piece) == mine:
                steps.extend([[hop] for hop in self._hops(board, start) if hop["via"] is None])
        return steps

    # ── the contract ────────────────────────────────────────────────────────

    def legal(self, state, seat):
        if state.get("winner") is not None or int(state["turn"]) != int(seat):
            return []
        rows = []
        for chain in self._moves(list(state["board"]), int(seat)):
            rows.append({
                "from": chain[0]["from"],
                "to": [hop["to"] for hop in chain],
                "via": [hop["via"] for hop in chain],
                "captures": sum(1 for hop in chain if hop["via"] is not None),
            })
        return rows

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        board = list(state["board"])
        try:
            start = int(move.get("from"))
        except (TypeError, ValueError):
            raise GameError("Pick one of your pieces") from None
        wanted = move.get("to")
        if isinstance(wanted, (int, str)):
            wanted = [wanted]
        try:
            wanted = [int(step) for step in (wanted or [])]
        except (TypeError, ValueError):
            raise GameError("Pick where the piece lands") from None
        if not wanted:
            raise GameError("Pick where the piece lands")
        if not 0 <= start < 64 or colour(board[start]) != int(seat) + 1:
            raise GameError("That piece is not yours")

        chosen = None
        for chain in self._moves(board, int(seat)):
            if chain[0]["from"] == start and [hop["to"] for hop in chain] == wanted:
                chosen = chain
                break
        if chosen is None:
            legal = self._moves(board, int(seat))
            if legal and all(hop["via"] is not None for hop in legal[0]):
                raise GameError("A capture is on the board — it must be taken")
            raise GameError("That move is not legal")

        for hop in chosen:
            board = self._land(board, hop)
        landed = chosen[-1]["to"]
        queened = False
        if not crowned(board[landed]) and divmod(landed, 8)[0] == home_row(int(seat) + 1):
            board[landed] = CROWN_FROM[board[landed]]
            queened = True

        took = any(hop["via"] is not None for hop in chosen)
        quiet = 0 if took else int(state.get("quiet") or 0) + 1
        moves = list(state.get("moves") or [0, 0])
        moves[int(seat)] = int(moves[int(seat)]) + 1
        other = 1 - int(seat)

        winner = None
        if not any(colour(value) == other + 1 for value in board):
            winner = int(seat)                       # every rival piece is gone
        elif not self._moves(board, other):
            winner = int(seat)                       # the rival cannot answer
        elif quiet >= STALE_TURNS:
            winner = other                           # nobody is playing to win

        return {"board": board,
                "turn": int(seat) if winner is not None else other,
                "winner": winner, "seats": 2, "chain": None,
                "last": {"from": start, "to": landed, "captures": sum(
                    1 for hop in chosen if hop["via"] is not None),
                    "length": len(chosen), "crowned": queened},
                "moves": moves, "quiet": quiet}
