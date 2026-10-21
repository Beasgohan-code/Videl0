"""The games the arcade can host, in the order the lobby lists them."""
from .checkers import Checkers
from .chess import Chess
from .connect4 import ConnectFour
from .gomoku import Gomoku
from .ludo import Ludo
from .reversi import Reversi
from .tictactoe import TicTacToe

GAMES = {game.key: game for game in (
    Chess(), Checkers(), Gomoku(), ConnectFour(), Reversi(), TicTacToe(), Ludo())}

__all__ = ["GAMES", "Checkers", "Chess", "ConnectFour", "Gomoku", "Ludo", "Reversi", "TicTacToe"]
