"""The rules of every arcade game, without a database or a browser.

A move that the engine accepts is the only thing the store will ever write, so
these are the tests that decide whether a game can be trusted at all.
"""
import unittest
from unittest.mock import patch

from videl.games import GAMES
from videl.games.checkers import Checkers
from videl.games.chess import Chess
from videl.games.chinese import CAMPS, HOLES, INDEX, NEIGHBOURS, ChineseCheckers
from videl.games.connect4 import ConnectFour
from videl.games.dots import COLS as DOTS_COLS
from videl.games.dots import DotsAndBoxes
from videl.games.gomoku import Gomoku
from videl.games.ludo import HOME_PROGRESS, Ludo
from videl.games.registry import GameError, run_length
from videl.games.reversi import Reversi
from videl.games.tictactoe import TicTacToe
from videl.games.yacht import CATEGORIES, Yacht


class RegistryTests(unittest.TestCase):
    def test_every_listed_game_describes_itself(self):
        self.assertEqual(set(GAMES), {"checkers", "chess", "chinese", "connect4",
                                      "dots", "gomoku", "reversi", "tictactoe",
                                      "ludo", "yacht"})
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


class ChineseCheckersTests(unittest.TestCase):
    def setUp(self):
        self.game = ChineseCheckers()
        self.state = self.game.new(4)

    def landing(self, origin, neighbour):
        row, x2 = HOLES[origin]
        nrow, nx2 = HOLES[neighbour]
        return INDEX[(2 * nrow - row, 2 * nx2 - x2)]

    def test_the_star_has_121_holes_and_six_ten_peg_camps(self):
        self.assertEqual(len(HOLES), 121)
        self.assertEqual(len(CAMPS), 6)
        self.assertEqual({len(camp) for camp in CAMPS}, {10})
        cells = [hole for camp in CAMPS for hole in camp]
        self.assertEqual(len(cells), len(set(cells)), "no two camps share a hole")
        self.assertEqual(self.state["homes"], [0, 1, 3, 4])
        self.assertEqual(self.state["targets"], [3, 4, 0, 1],
                         "each camp is opposite its own")

    def test_two_players_start_in_opposite_camps(self):
        state = self.game.new(2)
        self.assertEqual(state["homes"], [0, 3])
        self.assertEqual(len(state["pegs"][0]), 10)
        self.assertEqual(set(state["pegs"][0]), set(CAMPS[0]))

    def test_a_peg_steps_and_the_turn_passes(self):
        move = self.game.legal(self.state, 0)[0]
        moved = self.game.apply(self.state, 0, move)
        self.assertEqual(moved["turn"], 1)
        self.assertIn(move["to"], moved["pegs"][0])
        self.assertNotIn(move["from"], moved["pegs"][0])

    def test_a_peg_jumps_over_one_peg_into_the_empty_hole_beyond(self):
        origin = INDEX[(8, 0)]
        neighbour = NEIGHBOURS[origin][0]
        landing = self.landing(origin, neighbour)
        state = {**self.state, "pegs": [[origin], [neighbour], [], []],
                 "targets": [3, 4, 5, 0]}
        moves = self.game.legal(state, 0)
        self.assertIn({"from": origin, "to": landing}, moves)
        moved = self.game.apply(state, 0, {"from": origin, "to": landing})
        self.assertIn(landing, moved["pegs"][0])

    def test_a_peg_cannot_teleport_or_move_for_another_seat(self):
        origin = self.state["pegs"][0][0]
        far = next(hole for hole in range(len(HOLES))
                   if hole not in self.state["pegs"][0]
                   and hole not in NEIGHBOURS[origin])
        with self.assertRaises(GameError):
            self.game.apply(self.state, 0, {"from": origin, "to": far})
        with self.assertRaises(GameError):
            self.game.apply(self.state, 1, {"from": origin, "to": NEIGHBOURS[origin][0]})

    def test_filling_the_opposite_camp_wins(self):
        state = self.game.new(2)
        target = CAMPS[state["targets"][0]]
        missing = next(hole for hole in target
                       if any(neighbour not in target for neighbour in NEIGHBOURS[hole]))
        park = next(neighbour for neighbour in NEIGHBOURS[missing] if neighbour not in target)
        state = {**state, "pegs": [list(hole for hole in target if hole != missing) + [park], []],
                 "turn": 0}
        won = self.game.apply(state, 0, {"from": park, "to": missing})
        self.assertEqual(won["winner"], 0)


class DotsAndBoxesTests(unittest.TestCase):
    def setUp(self):
        self.game = DotsAndBoxes()
        self.state = self.game.new(2)

    def test_the_grid_owns_every_edge_and_box(self):
        self.assertEqual(len(self.state["h"]), 36)
        self.assertEqual(len(self.state["v"]), 35)
        self.assertEqual(len(self.state["owner"]), 30)
        self.assertEqual(len(self.game.legal(self.state, 0)), 71)

    def test_a_line_is_drawn_once_and_passes_the_turn(self):
        state = self.game.apply(self.state, 0, {"kind": "h", "index": 0})
        self.assertEqual(state["turn"], 1)
        with self.assertRaises(GameError):
            self.game.apply(state, 1, {"kind": "h", "index": 0})
        with self.assertRaises(GameError):
            self.game.apply(state, 1, {"kind": "h", "index": 999})

    def test_closing_one_box_scores_it_and_keeps_the_turn(self):
        state = self.state
        state["h"][0] = state["h"][DOTS_COLS] = 1
        state["v"][0] = 1
        state = self.game.apply(state, 0, {"kind": "v", "index": 1})
        self.assertEqual(state["owner"][0], 0)
        self.assertEqual(state["scores"][0], 1)
        self.assertEqual(state["turn"], 0, "closing a box earns another line")

    def test_one_line_can_close_two_boxes(self):
        state = self.state
        # Box (0, 1) and box (1, 1) share the horizontal line at row 1, col 1.
        for index in (1, 2, 1 * DOTS_COLS + 2, 2 * DOTS_COLS + 1, 2 * DOTS_COLS + 2):
            state["h"][index] = 1
        state["v"][1] = state["v"][2] = 1          # top pair's sides
        state["v"][1 * (DOTS_COLS + 1) + 1] = 1
        state["v"][1 * (DOTS_COLS + 1) + 2] = 1    # bottom pair's sides
        state = self.game.apply(state, 0, {"kind": "h", "index": 1 * DOTS_COLS + 1})
        self.assertEqual(state["scores"][0], 2)
        self.assertEqual(state["owner"][1], 0)
        self.assertEqual(state["owner"][DOTS_COLS + 1], 0)

    def test_a_full_board_decides_by_score_and_can_draw(self):
        state = self.game.new(2)
        state["h"] = [1] * len(state["h"])
        state["v"] = [1] * len(state["v"])
        state["owner"] = [-1] * 30
        state["scores"] = [10, 10]
        state["turn"] = 1
        # Re-open one line so the winning move can close the last box.
        state["h"][-1] = 0
        state = self.game.apply(state, 1, {"kind": "h", "index": len(state["h"]) - 1})
        self.assertEqual(state["winner"], 1)


class YachtTests(unittest.TestCase):
    def setUp(self):
        self.game = Yacht()
        self.state = self.game.new(3)

    def test_a_turn_has_three_rolls_and_five_dice(self):
        state = self.game.apply(self.state, 0, {"action": "roll"})
        self.assertEqual(len(state["dice"]), 5)
        self.assertTrue(all(1 <= die <= 6 for die in state["dice"]))
        state = self.game.apply(state, 0, {"action": "roll"})
        state = self.game.apply(state, 0, {"action": "roll"})
        with self.assertRaises(GameError):
            self.game.apply(state, 0, {"action": "roll"})

    def test_each_category_scores_the_way_a_scorecard_does(self):
        from videl.games.yacht import _score
        self.assertEqual(_score([1, 1, 1, 2, 2], "full_house"), 25)
        self.assertEqual(_score([1, 2, 3, 4, 6], "small_straight"), 30)
        self.assertEqual(_score([2, 3, 4, 5, 6], "large_straight"), 40)
        self.assertEqual(_score([4, 4, 4, 4, 4], "yacht"), 50)
        self.assertEqual(_score([4, 4, 4, 4, 4], "four_kind"), 20)
        self.assertEqual(_score([6, 6, 6, 2, 3], "three_kind"), 23)
        self.assertEqual(_score([1, 1, 3, 4, 6], "ones"), 2)
        self.assertEqual(_score([5, 5, 4, 4, 3], "full_house"), 0)

    def test_a_box_is_written_once_and_the_turn_moves_on(self):
        state = self.game.apply(self.state, 0, {"action": "roll"})
        state = self.game.apply(state, 0, {"action": "score", "category": "chance"})
        self.assertEqual(state["turn"], 1)
        self.assertIsNotNone(state["scores"][0][CATEGORIES.index("chance")])
        state = self.game.apply(state, 1, {"action": "roll"})
        with self.assertRaises(GameError):
            self.game.apply(state, 1, {"action": "score", "category": "not_a_box"})

    def test_a_timeout_plays_a_whole_turn_rather_than_one_roll(self):
        state = self.game.auto(self.state)
        self.assertEqual(state["turn"], 1)
        self.assertEqual(state["rolls"], 0)
        self.assertEqual(sum(value is not None for value in state["scores"][0]), 1)

    def test_all_thirteen_boxes_end_the_table_and_pay_the_upper_bonus(self):
        state = self.game.new(2)
        state["scores"] = [[11] * 6 + [10] * 7, [11] * 6 + [10] * 7]
        state["scores"][0][12] = None
        state["scores"][1][12] = None
        state["dice"] = [6, 6, 6, 6, 6]
        state["rolls"] = 3
        state["turn"] = 0
        state = self.game.apply(state, 0, {"action": "score", "category": "chance"})
        state["dice"] = [1, 1, 1, 1, 1]
        state["rolls"] = 1
        state = self.game.apply(state, 1, {"action": "score", "category": "chance"})
        self.assertIsNotNone(state["winner"])
        self.assertEqual(state["winner"], 0)
        self.assertEqual(self.game.totals(state), [191, 166],
                         "sixty-six in the upper six pays the thirty-five bonus")

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


class ChessTests(unittest.TestCase):
    """The rules people check first, because they are the ones that get argued."""

    def setUp(self):
        self.game = Chess()
        self.state = self.game.new(2)

    def play(self, *moves):
        state = self.state
        for move in moves:
            start, end = move[0], move[1]
            payload = {"from": start, "to": end}
            if len(move) > 2 and move[2]:
                payload["promote"] = move[2]
            state = self.game.apply(state, state["turn"], payload)
        return state

    def test_a_new_board_offers_the_twenty_opening_moves(self):
        self.assertEqual(len(self.game.legal(self.state, 0)), 20,
                         "sixteen pawn moves and four knight moves")
        self.assertEqual(self.game.legal(self.state, 1), [],
                         "the player who is not on move has no options")
        self.assertEqual(self.state["board"][60], "K")
        self.assertEqual(self.state["board"][4], "k")

    def test_a_knight_jumps_over_pieces_but_not_onto_its_own(self):
        with self.assertRaises(GameError):
            self.game.apply(self.state, 0, {"from": 62, "to": 53})
        moved = self.game.apply(self.state, 0, {"from": 62, "to": 45})
        self.assertEqual(moved["board"][45], "N")
        self.assertEqual(moved["board"][62], ".")

    def test_fools_mate_is_a_mate_in_four(self):
        state = self.play((53, 45), (12, 28), (54, 38), (3, 39))
        self.assertEqual(state["winner"], 1)
        self.assertEqual(state["last"]["san"], "Qh4#")
        self.assertTrue(state["last"]["mate"])

    def test_a_pinned_piece_may_not_expose_its_king(self):
        # King e1 (60), white rook e2 (52), black rook e8 (4): the white rook
        # is pinned to the file and may not step sideways.
        board = ["."] * 64
        board[60] = "K"
        board[52] = "R"
        board[4] = "r"
        board[0] = "k"
        state = dict(self.state, board=board, castle="", history=[], turn=0)
        rows = self.game.legal(state, 0)
        sideways = [row["to"] for row in rows if row["from"] == 52]
        self.assertNotIn(51, sideways, "a pinned rook cannot leave the file")
        self.assertIn(44, sideways, "it may still move along the pin")

    def test_castling_moves_the_rook_and_cannot_pass_through_check(self):
        board = ["."] * 64
        board[60] = "K"
        board[63] = "R"
        board[56] = "R"
        board[4] = "k"
        state = dict(self.state, board=board, castle="KQ", history=[], turn=0)
        castled = self.game.apply(state, 0, {"from": 60, "to": 62})
        self.assertEqual(castled["board"][62], "K")
        self.assertEqual(castled["board"][61], "R", "the rook hopped over the king")
        self.assertEqual(castled["board"][63], ".")
        self.assertEqual(castled["last"]["san"], "O-O")

        blocked = dict(state, board=list(board))
        blocked["board"][4] = "r"  # rook on e8 attacks the e-file
        with self.assertRaises(GameError):
            self.game.apply(blocked, 0, {"from": 60, "to": 62})

    def test_en_passant_captures_the_pawn_that_just_ran(self):
        # 1. e4 a6 2. e5 d5 — the white pawn on e5 may take on d6 as if the
        # black pawn had only advanced one square.
        state = self.play((52, 36), (8, 16), (36, 28), (11, 27))
        self.assertEqual(state["ep"], 19, "d6 is the en passant target")
        taken = self.game.apply(state, 0, {"from": 28, "to": 19})
        self.assertEqual(taken["board"][19], "P")
        self.assertEqual(taken["board"][27], ".", "the passed pawn is gone")
        self.assertEqual(taken["last"]["san"], "exd6")

    def test_a_pawn_on_the_last_rank_must_choose_a_piece(self):
        board = ["."] * 64
        board[8] = "P"    # a7, one step from promotion
        board[60] = "K"
        board[4] = "k"
        state = dict(self.state, board=board, castle="", history=[], turn=0)
        with self.assertRaises(GameError) as caught:
            self.game.apply(state, 0, {"from": 8, "to": 0})
        self.assertEqual(caught.exception.status, 422, "the panel is asked to choose")
        promoted = self.game.apply(state, 0, {"from": 8, "to": 0, "promote": "n"})
        self.assertEqual(promoted["board"][0], "N")

    def test_stalemate_is_a_draw_not_a_loss(self):
        # Black king a8, white queen b6 and king e1. Qb6-c7 leaves the king with
        # nowhere to go and no check: a draw, not a win for White.
        board = ["."] * 64
        board[0] = "k"     # a8
        board[17] = "Q"    # b6
        board[60] = "K"    # e1
        state = dict(self.state, board=board, castle="", history=[], turn=0)
        state["history"] = [self.game._key(board, 0, "", None)]
        drawn = self.game.apply(state, 0, {"from": 17, "to": 10})
        self.assertEqual(drawn["winner"], "draw")
        self.assertFalse(drawn["check"], "stalemate, not checkmate")
        self.assertEqual(drawn["last"]["san"], "Qc7")

    def test_the_fifty_move_rule_ends_a_quiet_game(self):
        board = ["."] * 64
        board[60] = "K"
        board[0] = "k"
        board[7] = "R"
        state = dict(self.state, board=board, castle="", history=[], turn=0, half=99)
        state["history"] = [self.game._key(board, 0, "", None)]
        drawn = self.game.apply(state, 0, {"from": 7, "to": 15})
        self.assertEqual(drawn["winner"], "draw")

    def test_a_timeout_still_produces_a_legal_position(self):
        played = self.game.auto(self.state)
        self.assertNotEqual(played["turn"], self.state["turn"])
        self.assertEqual(sum(1 for piece in played["board"] if piece != "."), 32,
                         "a timeout moves a piece, it does not remove one")
        self.assertIsNotNone(played["last"]["san"])


class GomokuTests(unittest.TestCase):
    def setUp(self):
        self.game = Gomoku()
        self.state = self.game.new(2)

    def place(self, *cells):
        state = self.state
        for cell in cells:
            state = self.game.apply(state, state["turn"], {"cell": cell})
        return state

    def test_five_in_a_row_takes_the_table(self):
        # White 0,0 1,0 2,0 3,0 4,0 — black answers on the last row.
        state = self.place(0, 210, 1, 211, 2, 212, 3, 213, 4)
        self.assertEqual(state["winner"], 0)
        self.assertEqual(sorted(state["line"]), [0, 1, 2, 3, 4])

    def test_a_diagonal_counts_as_a_line(self):
        state = self.state
        for step in range(4):
            state = self.game.apply(state, 0, {"cell": step * 16})
            state = self.game.apply(state, 1, {"cell": 200 + step})
        state = self.game.apply(state, 0, {"cell": 4 * 16})
        self.assertEqual(state["winner"], 0)

    def test_four_in_a_row_is_not_a_win(self):
        state = self.place(0, 100, 1, 101, 2, 102, 3)
        self.assertIsNone(state["winner"])
        self.assertEqual(state["line"], [])

    def test_a_taken_intersection_is_refused(self):
        state = self.place(112)
        with self.assertRaises(GameError):
            self.game.apply(state, 1, {"cell": 112})

    def test_only_the_seat_on_move_may_play(self):
        with self.assertRaises(GameError) as caught:
            self.game.apply(self.state, 1, {"cell": 0})
        self.assertEqual(caught.exception.status, 409)


class ChessScoresheetTests(unittest.TestCase):
    """The move list the panel prints must be readable notation, not coordinates."""

    def setUp(self):
        self.game = Chess()

    def play(self, state, seat, move):
        return self.game.apply(state, seat, move)

    def test_the_scoresheet_is_written_in_san(self):
        state = self.game.new(2)
        state = self.play(state, 0, {"from": 52, "to": 36})   # e4
        state = self.play(state, 1, {"from": 12, "to": 28})   # e5
        state = self.play(state, 0, {"from": 62, "to": 45})   # Nf3
        self.assertEqual(state["log"], ["e4", "e5", "Nf3"])

    def test_a_capture_and_a_check_are_marked(self):
        state = self.game.new(2)
        state = self.play(state, 0, {"from": 52, "to": 36})   # e4
        state = self.play(state, 1, {"from": 11, "to": 27})   # d5
        state = self.play(state, 0, {"from": 36, "to": 27})   # exd5
        self.assertEqual(state["log"][-1], "exd5")

    def test_the_scoresheet_survives_a_reload(self):
        state = self.game.new(2)
        state = self.play(state, 0, {"from": 52, "to": 36})
        view = self.game.view(state, 0)
        self.assertEqual(view["log"], ["e4"], "the view is what the browser reloads into")
