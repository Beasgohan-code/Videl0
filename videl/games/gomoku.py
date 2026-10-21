"""Five in a Row (gomoku) on a 15×15 board, two seats.

The simplest complete game after tic-tac-toe, and the one that reads best with
more than three moves in front of you: put a stone on any empty intersection,
and the first line of five — across, down or either diagonal — takes the table.

No opening restrictions, no swaps, no hidden information: the engine only has
to answer "did that stone make five", so the rules fit in a page and the board
stays readable on a phone.
"""
from .registry import Game, GameError

SIZE = 15
CELLS = SIZE * SIZE
LINE = 5
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


def _coordinates(index):
    return divmod(int(index), SIZE)


class Gomoku(Game):
    key = "gomoku"
    name = "Five in a Row"
    seats = (2,)
    turn_seconds = 60
    summary = "Fifteen by fifteen. Five stones in a line wins."

    def new(self, seat_count):
        return {"board": [0] * CELLS, "turn": 0, "winner": None, "seats": 2,
                "last": None, "line": [], "moves": 0}

    def _line_through(self, board, index, player):
        """The longest line through this stone, as the winning cells."""
        row, col = _coordinates(index)
        best = []
        for dr, dc in DIRECTIONS:
            cells = [index]
            for sign in (1, -1):
                r, c = row + dr * sign, col + dc * sign
                while 0 <= r < SIZE and 0 <= c < SIZE and board[r * SIZE + c] == player:
                    cells.append(r * SIZE + c)
                    r += dr * sign
                    c += dc * sign
            if len(cells) >= LINE and len(cells) > len(best):
                best = sorted(cells)
        return best

    def legal(self, state, seat):
        if state.get("winner") is not None or int(state["turn"]) != int(seat):
            return []
        return [{"cell": index} for index, value in enumerate(state["board"]) if value == 0]

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        try:
            index = int(move.get("cell"))
        except (TypeError, ValueError):
            raise GameError("Choose an intersection") from None
        if not 0 <= index < CELLS:
            raise GameError("Choose an intersection on the board")
        board = list(state["board"])
        if board[index]:
            raise GameError("That intersection is taken")

        board[index] = int(seat) + 1
        line = self._line_through(board, index, int(seat) + 1)
        winner = int(seat) if line else None
        moves = int(state.get("moves") or 0) + 1
        if winner is None and moves >= CELLS:
            winner = "draw"
        return {"board": board,
                "turn": int(seat) if winner is not None else 1 - int(seat),
                "winner": winner, "seats": 2,
                "last": {"cell": index, "player": int(seat) + 1},
                "line": line, "moves": moves}

    def auto(self, state):
        """A timeout plays near the middle; dull but deterministic."""
        options = self.legal(state, state["turn"])
        if not options:
            return dict(state, winner="draw")
        centre = CELLS // 2
        options.sort(key=lambda row: abs(row["cell"] // SIZE - centre // SIZE)
                     + abs(row["cell"] % SIZE - centre % SIZE))
        return self.apply(state, state["turn"], options[0])
