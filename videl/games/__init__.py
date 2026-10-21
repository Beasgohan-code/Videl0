"""The games the arcade can host, in the order the lobby lists them."""
from .checkers import Checkers
from .connect4 import ConnectFour
from .ludo import Ludo
from .reversi import Reversi
from .tictactoe import TicTacToe

GAMES = {game.key: game for game in (Checkers(), ConnectFour(), Reversi(), TicTacToe(), Ludo())}

__all__ = ["GAMES", "Checkers", "ConnectFour", "Reversi", "TicTacToe", "Ludo"]
