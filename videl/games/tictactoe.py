"""Tic-tac-toe: three by three, quick to finish, good first game in a room."""
from .registry import Game, GameError

LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6))


class TicTacToe(Game):
    key = "tictactoe"
    name = "Tic-tac-toe"
    seats = (2,)
    turn_seconds = 45
    summary = "Three in a row on a 3×3 grid. Fast, and easy to finish."

    def new(self, seat_count):
        return {"board": [0] * 9, "turn": 0, "winner": None, "line": [], "seats": 2}

    def _winning(self, board, player):
        for line in LINES:
            if all(board[cell] == player for cell in line):
                return list(line)
        return []

    def legal(self, state, seat):
        if state.get("winner") is not None:
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
            raise GameError("Choose a square") from None
        if not 0 <= index < 9:
            raise GameError("Choose a square")
        board = list(state["board"])
        if board[index] != 0:
            raise GameError("That square is taken")
        board[index] = int(seat) + 1
        line = self._winning(board, int(seat) + 1)
        winner = int(seat) if line else None
        if winner is None and all(board):
            winner = "draw"
        return {"board": board,
                "turn": state["turn"] if winner is not None else 1 - int(seat),
                "winner": winner, "line": line, "seats": 2}
