"""Connect Four: seven columns, six rows, four in a line."""
from .registry import Game, GameError, run_length

ROWS, COLS = 6, 7
WIN = 4


class ConnectFour(Game):
    key = "connect4"
    name = "Connect Four"
    seats = (2,)
    turn_seconds = 60
    summary = "Drop a disc; line up four across, down or diagonally."

    def new(self, seat_count):
        return {"board": [0] * (ROWS * COLS), "turn": 0, "winner": None,
                "line": [], "seats": 2, "last": None}

    def _landing(self, board, column):
        for row in range(ROWS - 1, -1, -1):
            index = row * COLS + column
            if board[index] == 0:
                return index
        return None

    def legal(self, state, seat):
        if state.get("winner") is not None:
            return []
        board = state["board"]
        return [{"column": column} for column in range(COLS)
                if board[column] == 0]

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        try:
            column = int(move.get("column"))
        except (TypeError, ValueError):
            raise GameError("Choose a column from 1 to 7") from None
        if not 0 <= column < COLS:
            raise GameError("Choose a column from 1 to 7")
        board = list(state["board"])
        index = self._landing(board, column)
        if index is None:
            raise GameError("That column is full")
        board[index] = int(seat) + 1
        line = []
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            if run_length(board, index, int(seat) + 1, ROWS, COLS, dr, dc) >= WIN:
                line = self._line(board, index, int(seat) + 1, dr, dc)
                break
        winner = int(seat) if line else None
        if winner is None and all(board[column] for column in range(COLS)):
            winner = "draw"
        return {"board": board,
                "turn": state["turn"] if winner is not None else 1 - int(seat),
                "winner": winner, "line": line, "seats": 2, "last": index}

    def _line(self, board, index, player, dr, dc):
        """The winning cells, so the panel can draw them instead of guessing."""
        row, col = divmod(index, COLS)
        cells = [index]
        for sign in (1, -1):
            r, c = row + dr * sign, col + dc * sign
            while 0 <= r < ROWS and 0 <= c < COLS and board[r * COLS + c] == player:
                cells.append(r * COLS + c)
                r += dr * sign
                c += dc * sign
        return sorted(cells)
