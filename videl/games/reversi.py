"""Reversi (Othello): eight by eight, flank and flip.

The rules have one consequence the UI must respect: a player can have no legal
move, in which case the turn passes immediately — possibly twice, which ends
the game. Both cases are handled here, not in the panel.
"""
from .registry import Game, GameError

SIZE = 8
DIRECTIONS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


class Reversi(Game):
    key = "reversi"
    name = "Reversi"
    seats = (2,)
    turn_seconds = 90
    summary = "Place a disc that flanks a line; the line flips to your colour."

    def new(self, seat_count):
        board = [0] * (SIZE * SIZE)
        board[3 * SIZE + 3] = 2
        board[4 * SIZE + 4] = 2
        board[3 * SIZE + 4] = 1
        board[4 * SIZE + 3] = 1
        return {"board": board, "turn": 0, "winner": None, "seats": 2,
                "passed": False, "last": None}

    def _flips(self, board, index, player):
        row, col = divmod(index, SIZE)
        if board[index] != 0:
            return []
        captured = []
        for dr, dc in DIRECTIONS:
            line, r, c = [], row + dr, col + dc
            while 0 <= r < SIZE and 0 <= c < SIZE and board[r * SIZE + c] == 3 - player:
                line.append(r * SIZE + c)
                r += dr
                c += dc
            if line and 0 <= r < SIZE and 0 <= c < SIZE and board[r * SIZE + c] == player:
                captured.extend(line)
        return captured

    def _options(self, board, player):
        return {index: self._flips(board, index, player) for index in range(SIZE * SIZE)
                if self._flips(board, index, player)}

    def legal(self, state, seat):
        if state.get("winner") is not None:
            return []
        options = self._options(state["board"], int(seat) + 1)
        return [{"cell": index, "flips": len(cells)} for index, cells in sorted(options.items())]

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        try:
            index = int(move.get("cell"))
        except (TypeError, ValueError):
            raise GameError("Choose a square") from None
        if not 0 <= index < SIZE * SIZE:
            raise GameError("Choose a square")
        player = int(seat) + 1
        board = list(state["board"])
        flips = self._flips(board, index, player)
        if not flips:
            raise GameError("That square does not flip a line")
        board[index] = player
        for cell in flips:
            board[cell] = player
        other = 3 - player
        if self._options(board, other):
            turn, passed = 1 - int(seat), False
        elif self._options(board, player):
            # The opponent has to pass; the turn comes straight back.
            turn, passed = int(seat), True
        else:
            turn, passed = int(seat), True
        winner = None
        if not self._options(board, 1) and not self._options(board, 2):
            mine = board.count(1)
            theirs = board.count(2)
            winner = int(seat) if mine > theirs else (1 - int(seat) if theirs > mine else "draw")
        return {"board": board, "turn": turn, "winner": winner, "seats": 2,
                "passed": passed, "last": index}

    def view(self, state, seat):
        board = state["board"]
        return {**state,
                "score": [board.count(1), board.count(2)],
                "legal": [entry["cell"] for entry in self.legal(state, seat)]}
