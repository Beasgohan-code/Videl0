"""The rules of every arcade game, without a database or a browser.

A move that the engine accepts is the only thing the store will ever write, so
these are the tests that decide whether a game can be trusted at all.
"""
import unittest
from unittest.mock import patch

from videl.games import GAMES
from videl.games.checkers import Checkers
from videl.games.connect4 import ConnectFour
from videl.games.ludo import HOME_PROGRESS, Ludo
from videl.games.registry import GameError, run_length
from videl.games.reversi import Reversi
from videl.games.tictactoe import TicTacToe


class RegistryTests(unittest.TestCase):
    def test_every_listed_game_describes_itself(self):
        self.assertEqual(set(GAMES), {"checkers", "connect4", "reversi", "tictactoe", "ludo"})
        for key, game in GAMES.items():
            described = game.describe()
            self.assertEqual(described["key"], key)
            self.assertTrue(described["name"])
            self.assertIn(described["seats"][0], game.seats)

    def test_a_run_counts_both_directions(self):
        board = [0] * 42
        for column in (2, 3, 4, 5):
            board[5 * 7 + column] = 1
        self.assertEqual(run_length(board, 5 * 7 + 3, 1, 6, 7, 0, 1), 4)
        self.assertEqual(run_length(board, 5 * 7 + 5, 1, 6, 7, 0, 1), 4)
        self.assertEqual(run_length(board, 5 * 7 + 0, 1, 6, 7, 0, 1), 0,
                         "an empty square is not the start of a run")


class ConnectFourTests(unittest.TestCase):
    def setUp(self):
        self.game = ConnectFour()
        self.state = self.game.new(2)

    def test_a_disc_falls_to_the_lowest_free_row(self):
        state = self.game.apply(self.state, 0, {"column": 0})
        self.assertEqual(state["board"][5 * 7], 1)
        self.assertEqual(state["turn"], 1)

    def test_a_replayed_move_is_refused_because_the_turn_moved(self):
        state = self.game.apply(self.state, 0, {"column": 0})
        with self.assertRaises(GameError) as caught:
            self.game.apply(state, 0, {"column": 1})
        self.assertEqual(caught.exception.status, 409)

    def test_four_in_a_column_wins_and_returns_the_line(self):
        state = self.state
        for _ in range(4):
            state = self.game.apply(state, 0, {"column": 0})
            if state["winner"] is not None:
                break
            state = self.game.apply(state, 1, {"column": 1})
        self.assertEqual(state["winner"], 0)
        self.assertEqual(len(state["line"]), 4)
        self.assertEqual(self.game.result(state), 0)

    def test_a_full_column_and_an_edge_are_refused(self):
        # A full column with no four in it: alternating discs, so the only
        # reason the move is refused is that the column has no room left.
        board = [0] * 42
        for row in range(6):
            board[row * 7 + 6] = 1 if row % 2 == 0 else 2
        state = {"board": board, "turn": 0, "winner": None, "line": [], "seats": 2}
        with self.assertRaises(GameError) as caught:
            self.game.apply(state, 0, {"column": 6})
        self.assertIn("full", str(caught.exception))
        with self.assertRaises(GameError):
            self.game.apply(self.state, 0, {"column": 7})

    def test_no_move_is_offered_after_the_game_ends(self):
        state = {"board": [0] * 42, "turn": 0, "winner": 0, "line": [0, 1, 2, 3], "seats": 2}
        self.assertEqual(self.game.legal(state, 0), [])
        with self.assertRaises(GameError):
            self.game.apply(state, 0, {"column": 0})


class ReversiTests(unittest.TestCase):
    def setUp(self):
        self.game = Reversi()
        self.state = self.game.new(2)

    def test_the_opening_position_offers_four_moves(self):
        moves = self.game.legal(self.state, 0)
        self.assertEqual(len(moves), 4)
        self.assertEqual(self.game.view(self.state, 0)["score"], [2, 2])

    def test_a_flanked_line_flips(self):
        state = self.game.apply(self.state, 0, {"cell": 19})   # row 2, column 3
        self.assertEqual(state["board"][19], 1)
        self.assertEqual(state["board"][27], 1, "the white disc between flips")
        self.assertEqual(state["board"].count(1), 4)
        self.assertEqual(state["board"].count(2), 1)

    def test_a_square_that_flips_nothing_is_refused(self):
        with self.assertRaises(GameError):
            self.game.apply(self.state, 0, {"cell": 0})
        with self.assertRaises(GameError):
            self.game.apply(self.state, 0, {"cell": 64})

    def test_a_position_with_nothing_to_flip_offers_no_move(self):
        board = [0] * 64
        board[0] = 1
        state = {"board": board, "turn": 1, "winner": None, "seats": 2,
                 "passed": False, "last": None}
        self.assertEqual(self.game.legal(state, 1), [])
        self.assertEqual(self.game.legal(state, 0), [])


class TicTacToeTests(unittest.TestCase):
    def setUp(self):
        self.game = TicTacToe()
        self.state = self.game.new(2)

    def test_three_in_a_row_wins(self):
        state = self.state
        for seat, cell in ((0, 0), (1, 1), (0, 4), (1, 2), (0, 8)):
            state = self.game.apply(state, seat, {"cell": cell})
        self.assertEqual(state["winner"], 0)
        self.assertEqual(state["line"], [0, 4, 8])
        self.assertEqual(state["turn"], 0, "a finished game does not hand over the turn")

    def test_a_taken_square_is_refused(self):
        state = self.game.apply(self.state, 0, {"cell": 4})
        with self.assertRaises(GameError):
            self.game.apply(state, 1, {"cell": 4})


class LudoTests(unittest.TestCase):
    def setUp(self):
        self.game = Ludo()
        self.state = self.game.new(2)

    def state_with(self, tokens, roll, turn=0, **extra):
        state = {"tokens": [list(row) for row in tokens], "roll": roll, "turn": turn,
                 "seats": 2, "sixes": 0, "winner": None, "starts": [0, 26],
                 "last": None}
        state.update(extra)
        return state

    def test_two_players_start_on_opposite_corners(self):
        state = self.game.new(2)
        self.assertEqual(state["starts"], [0, 26])
        self.assertEqual(state["tokens"], [[-1] * 4, [-1] * 4])

    def test_only_a_six_leaves_the_base(self):
        with self.assertRaises(GameError):
            self.game.apply(self.state_with([[-1] * 4, [-1] * 4], 3), 0,
                            {"action": "move", "token": 0})
        state = self.game.apply(self.state_with([[-1] * 4, [-1] * 4], 6), 0,
                                {"action": "move", "token": 0})
        self.assertEqual(state["tokens"][0][0], 0)
        self.assertEqual(state["turn"], 0, "a six keeps the turn")

    def test_landing_on_an_opponent_sends_it_home(self):
        tokens = [[9, -1, -1, -1], [36, -1, -1, -1]]
        state = self.game.apply(self.state_with(tokens, 1), 0,
                                {"action": "move", "token": 0})
        self.assertEqual(state["tokens"][0][0], 10)
        self.assertEqual(state["tokens"][1][0], -1, "the captured token returns to base")
        self.assertEqual(state["last"]["captured"], [[1, 0]])

    def test_a_safe_square_protects_a_token(self):
        # 8 is a star square: seat 0 reaches it from 3 with a five.
        tokens = [[3, -1, -1, -1], [34, -1, -1, -1]]  # 26 + 34 = 8 on the ring
        state = self.game.apply(self.state_with(tokens, 5), 0,
                                {"action": "move", "token": 0})
        self.assertEqual(state["tokens"][0][0], 8)
        self.assertEqual(state["tokens"][1][0], 34)

    def test_home_needs_the_exact_roll(self):
        tokens = [[55, -1, -1, -1], [-1] * 4]
        with self.assertRaises(GameError):
            self.game.apply(self.state_with(tokens, 3), 0, {"action": "move", "token": 0})
        state = self.game.apply(self.state_with(tokens, 2), 0,
                                {"action": "move", "token": 0})
        self.assertEqual(state["tokens"][0][0], HOME_PROGRESS)
        self.assertIsNone(state["winner"], "one token home is not a win")

    def test_all_four_tokens_home_wins(self):
        tokens = [[HOME_PROGRESS] * 3 + [56], [-1] * 4]
        state = self.game.apply(self.state_with(tokens, 1), 0,
                                {"action": "move", "token": 3})
        self.assertEqual(state["winner"], 0)
        self.assertEqual(self.game.result(state), 0)

    def test_a_roll_must_be_used_before_rolling_again(self):
        state = self.state_with([[-1] * 4, [-1] * 4], 4)
        with self.assertRaises(GameError):
            self.game.apply(state, 0, {"action": "roll"})
        passed = self.game.apply(state, 0, {"action": "pass"})
        self.assertEqual(passed["turn"], 1)

    def test_three_sixes_forfeit_the_turn(self):
        state = self.state_with([[-1] * 4, [-1] * 4], None, sixes=2)
        with patch("videl.games.ludo.random.randint", return_value=6):
            state = self.game.apply(state, 0, {"action": "roll"})
        self.assertEqual(state["turn"], 1)
        self.assertIsNone(state["roll"])
        self.assertTrue(state["last"]["triple_six"])

    def test_a_timeout_rolls_then_moves_or_passes(self):
        state = self.state_with([[-1] * 4, [-1] * 4], None)
        with patch("videl.games.ludo.random.randint", return_value=6):
            settled = self.game.auto(state)
        self.assertEqual(settled["tokens"][0][0], 0, "the six is used to leave the base")

    def test_a_third_and_fourth_player_can_join(self):
        state = self.game.new(4)
        self.assertEqual(state["starts"], [0, 13, 26, 39])
        self.assertEqual(len(state["tokens"]), 4)


if __name__ == "__main__":
    unittest.main()


class CheckersTests(unittest.TestCase):
    """Draughts, where the arguing is about which capture counts."""

    def setUp(self):
        self.game = Checkers()
        self.state = self.game.new(2)

    def board(self, **pieces):
        """A board from square numbers: ``board(f21=1, f26=2)``."""
        cells = [0] * 64
        for key, value in pieces.items():
            cells[int(key[1:])] = value
        state = self.state
        return dict(state, board=cells)

    def test_a_new_board_has_twelve_men_each_and_no_kings(self):
        board = self.state["board"]
        self.assertEqual(sum(1 for cell in board if cell == 1), 12)
        self.assertEqual(sum(1 for cell in board if cell == 2), 12)
        self.assertFalse(any(cell in (3, 4) for cell in board))
        self.assertEqual(len(self.game.legal(self.state, 0)), 7,
                         "seven opening moves, because the edge men cannot go left")

    def test_a_man_moves_one_square_forward_only(self):
        state = self.game.apply(self.state, 0, {"from": 17, "to": [26]})
        self.assertEqual(state["board"][17], 0)
        self.assertEqual(state["board"][26], 1)
        with self.assertRaises(GameError):
            self.game.apply(self.state, 0, {"from": 17, "to": [35]})

    def test_a_capture_is_compulsory_and_the_longest_chain_wins(self):
        # Two rival men in a row: a double capture must be taken in one move.
        state = self.board(f21=1, f28=2, f42=2, f62=2, f63=2)
        rows = self.game.legal(state, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["to"], [35, 49])
        self.assertEqual(rows[0]["captures"], 2)
        with self.assertRaises(GameError) as caught:
            self.game.apply(state, 0, {"from": 21, "to": [35]})
        self.assertIn("capture", str(caught.exception).lower(), "a short chain is refused")

    def test_a_man_crowned_by_a_capture_stops_there(self):
        # 49 -> 56 captures? no: a quiet step crowns; a capturing step onto the
        # last row also crowns and must end the chain even with a jump available.
        state = self.board(f42=1, f49=2, f63=2, f0=2)
        row = self.game.legal(state, 0)
        this = [r for r in row if r["from"] == 42]
        self.assertTrue(this)
        moved = self.game.apply(state, 0, {"from": 42, "to": [56]})
        self.assertEqual(moved["board"][56], 3, "a man on the last row is a king")
        self.assertTrue(moved["last"]["crowned"])

    def test_a_king_flies_and_lands_past_the_captured_piece(self):
        state = self.board(f56=3, f42=2, f7=2)
        rows = self.game.legal(state, 0)
        lands = {row["to"][0] for row in rows}
        self.assertEqual(lands, {35, 28, 21, 14},
                         "a king may land anywhere beyond the captured piece")
        moved = self.game.apply(state, 0, {"from": 56, "to": [21]})
        self.assertEqual(moved["board"][42], 0)
        self.assertEqual(moved["board"][21], 3)

    def test_a_side_with_no_move_loses(self):
        # One rival man in the corner, boxed in by our piece on its only square.
        state = self.board(f46=1, f37=1, f55=2, f17=1)
        self.assertEqual(self.game.legal(dict(state, turn=1), 1), [],
                         "the corner man has nowhere to go")
        moved = self.game.apply(state, 0, {"from": 17, "to": [26]})
        self.assertEqual(moved["board"][55], 2, "the rival still has a man")
        self.assertEqual(moved["winner"], 0, "but no move, so the game is over")

    def test_the_server_can_play_a_timeout_for_an_absent_player(self):
        state = self.board(f21=1, f28=2, f42=2, f62=2, f63=2)
        played = self.game.auto(state)
        self.assertEqual(played["board"][28], 0, "the forced chain was taken")
        self.assertNotEqual(played["turn"], state["turn"])
