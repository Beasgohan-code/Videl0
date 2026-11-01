"""The games the arcade can host, in the order the lobby lists them."""
from .checkers import Checkers
from .chinese import ChineseCheckers
from .chess import Chess
from .connect4 import ConnectFour
from .dots import DotsAndBoxes
from .gomoku import Gomoku
from .ludo import Ludo
from .reversi import Reversi
from .tictactoe import TicTacToe
from .yacht import Yacht

GAMES = {game.key: game for game in (
    Chess(), Checkers(), Gomoku(), ConnectFour(), Reversi(), TicTacToe(), Ludo(),
    ChineseCheckers(), DotsAndBoxes(), Yacht())}

__all__ = ["GAMES", "Checkers", "Chess", "ChineseCheckers", "ConnectFour",
           "DotsAndBoxes", "Gomoku", "Ludo", "Reversi", "TicTacToe", "Yacht"]
