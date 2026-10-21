"""Chess, refereed by the server.

Nothing here trusts the panel: every move is generated from the stored board,
castling is checked against rights and attacked squares, en passant against the
stored target, and a king may never be left in check. A move the browser invents
is answered with an error, not applied.

The board is a flat list of 64 squares, ``row * 8 + col`` with row 0 as rank 8,
so the panel can draw it without a lookup table. Pieces are two characters:
uppercase is seat 0 (ivory), lowercase seat 1 (onyx) — ``P N B R Q K``.

State is plain JSON: ``board``, ``turn``, ``castle`` (rights still alive),
``ep`` (en passant target or null), ``half`` (fifty-move clock), ``history``
(position keys for the threefold rule) and ``last`` (the move just played, with
its algebraic name so the room can print something readable).
"""
from .registry import Game, GameError

FILES = "abcdefgh"
KNIGHT = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
KING = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ORTHOGONAL = ((1, 0), (-1, 0), (0, 1), (0, -1))

START = (
    "rnbqkbnr"
    "pppppppp"
    "........"
    "........"
    "........"
    "........"
    "PPPPPPPP"
    "RNBQKBNR"
)

#: Home squares, so castling can be verified against the board it claims.
ROOK_HOME = {"K": (63, "K"), "Q": (56, "Q"), "k": (7, "k"), "q": (0, "q")}
KING_HOME = {True: 60, False: 4}


def square_name(index):
    return f"{FILES[int(index) % 8]}{8 - int(index) // 8}"


def _owner(piece):
    """0 for ivory, 1 for onyx, None for an empty square."""
    if not piece or piece == ".":
        return None
    return 0 if piece.isupper() else 1


def _mine(piece, seat):
    return _owner(piece) == int(seat)


class Chess(Game):
    key = "chess"
    name = "Chess"
    seats = (2,)
    turn_seconds = 180
    summary = "The real thing: castling, en passant, promotion and mate."

    # ── setup ───────────────────────────────────────────────────────────────

    def new(self, seat_count):
        board = list(START)
        return {"board": board, "turn": 0, "winner": None, "seats": 2,
                "castle": "KQkq", "ep": None, "half": 0, "full": 1,
                "history": [self._key(board, 0, "KQkq", None)],
                "last": None, "check": False, "moves": []}

    # ── geometry helpers ────────────────────────────────────────────────────

    @staticmethod
    def _inside(row, col):
        return 0 <= row < 8 and 0 <= col < 8

    def _find_king(self, board, seat):
        wanted = "K" if int(seat) == 0 else "k"
        for index, piece in enumerate(board):
            if piece == wanted:
                return index
        return None

    def _attacked(self, board, square, by):
        """Is ``square`` attacked by a piece of seat ``by``?"""
        row, col = divmod(int(square), 8)
        enemy_pawn = "P" if by == 0 else "p"
        # A pawn attacks diagonally; so the square is attacked if a pawn sits
        # one rank behind it in the right file.
        pawn_row = row + (1 if by == 0 else -1)
        for dc in (-1, 1):
            if self._inside(pawn_row, col + dc) and board[pawn_row * 8 + col + dc] == enemy_pawn:
                return True
        for dr, dc in KNIGHT:
            r, c = row + dr, col + dc
            if self._inside(r, c):
                piece = board[r * 8 + c]
                if piece != "." and _owner(piece) == by and piece.lower() == "n":
                    return True
        for dr, dc in KING:
            r, c = row + dr, col + dc
            if self._inside(r, c):
                piece = board[r * 8 + c]
                if piece != "." and _owner(piece) == by and piece.lower() == "k":
                    return True
        for table, kinds in ((DIAGONAL, "bq"), (ORTHOGONAL, "rq")):
            for dr, dc in table:
                r, c = row + dr, col + dc
                while self._inside(r, c):
                    piece = board[r * 8 + c]
                    if piece != ".":
                        if _owner(piece) == by and piece.lower() in kinds:
                            return True
                        break
                    r, c = r + dr, c + dc
        return False

    def _pseudo(self, state, seat):
        """Every move that follows the piece rules, check ignored."""
        board = state["board"]
        seat = int(seat)
        out = []
        for index, piece in enumerate(board):
            if not _mine(piece, seat):
                continue
            row, col = divmod(index, 8)
            kind = piece.lower()
            if kind == "p":
                step = -1 if seat == 0 else 1
                start_row = 6 if seat == 0 else 1
                last_row = 0 if seat == 0 else 7
                r = row + step
                if self._inside(r, col) and board[r * 8 + col] == ".":
                    self._pawn(out, index, r * 8 + col, last_row, None)
                    rr = row + 2 * step
                    if row == start_row and board[rr * 8 + col] == ".":
                        out.append({"from": index, "to": rr * 8 + col, "flags": "double"})
                for dc in (-1, 1):
                    r, c = row + step, col + dc
                    if not self._inside(r, c):
                        continue
                    at = r * 8 + c
                    target = board[at]
                    if target != "." and _owner(target) != seat:
                        self._pawn(out, index, at, last_row, target)
                    elif state.get("ep") == at and target == ".":
                        out.append({"from": index, "to": at, "flags": "ep"})
            elif kind == "n":
                for dr, dc in KNIGHT:
                    r, c = row + dr, col + dc
                    if not self._inside(r, c):
                        continue
                    target = board[r * 8 + c]
                    if target == "." or _owner(target) != seat:
                        out.append({"from": index, "to": r * 8 + c, "flags": ""})
            elif kind == "k":
                for dr, dc in KING:
                    r, c = row + dr, col + dc
                    if not self._inside(r, c):
                        continue
                    target = board[r * 8 + c]
                    if target == "." or _owner(target) != seat:
                        out.append({"from": index, "to": r * 8 + c, "flags": ""})
                out.extend(self._castles(state, seat))
            else:
                slides = DIAGONAL if kind == "b" else ORTHOGONAL if kind == "r" else DIAGONAL + ORTHOGONAL
                for dr, dc in slides:
                    r, c = row + dr, col + dc
                    while self._inside(r, c):
                        target = board[r * 8 + c]
                        if target == ".":
                            out.append({"from": index, "to": r * 8 + c, "flags": ""})
                        else:
                            if _owner(target) != seat:
                                out.append({"from": index, "to": r * 8 + c, "flags": ""})
                            break
                        r, c = r + dr, c + dc
        return out

    def _pawn(self, out, start, to, last_row, captured):
        if divmod(to, 8)[0] == last_row:
            for promotion in ("q", "r", "b", "n"):
                out.append({"from": start, "to": to, "flags": "promotion",
                            "promote": promotion, "captured": captured})
        else:
            out.append({"from": start, "to": to, "flags": "",
                        "captured": captured})

    def _castles(self, state, seat):
        board = state["board"]
        rights = state.get("castle") or ""
        out = []
        home = KING_HOME[seat == 0]
        if board[home] != ("K" if seat == 0 else "k"):
            return out
        if self._attacked(board, home, 1 - seat):
            return out
        if seat == 0:
            plan = (("K", 63, (61, 62), (62,)), ("Q", 56, (57, 58, 59), (58, 59)))
        else:
            plan = (("k", 7, (5, 6), (6,)), ("q", 0, (1, 2, 3), (2, 3)))
        for right, rook_square, empty, safe in plan:
            if right not in rights:
                continue
            rook = board[rook_square]
            if rook != ("R" if seat == 0 else "r"):
                continue
            if any(board[square] != "." for square in empty):
                continue
            if any(self._attacked(board, square, 1 - seat) for square in safe):
                continue
            destination = 62 if right in "Kk" else 58
            out.append({"from": home, "to": destination, "flags": "castle"})
        return out

    def _apply_pseudo(self, state, move):
        """The board after a pseudo-legal move, ignoring the result on the game."""
        board = list(state["board"])
        start = int(move["from"])
        end = int(move["to"])
        piece = board[start]
        flags = move.get("flags") or ""
        captured = board[end] if board[end] != "." else None
        board[start] = "."
        if flags == "ep":
            capture_square = end + (8 if _owner(piece) == 0 else -8)
            captured = board[capture_square]
            board[capture_square] = "."
        board[end] = piece
        if flags == "castle":
            if end == 62:
                board[61], board[63] = board[63], "."
            elif end == 58:
                board[59], board[56] = board[56], "."
            elif end == 6:
                board[5], board[7] = board[7], "."
            elif end == 2:
                board[3], board[0] = board[0], "."
        promote = move.get("promote")
        if promote:
            board[end] = promote.upper() if _owner(piece) == 0 else promote.lower()
        return board, captured

    # ── the contract ────────────────────────────────────────────────────────

    def _legal(self, state, seat):
        """Fully legal moves, with the king safe after each one."""
        rows = []
        for move in self._pseudo(state, seat):
            after, captured = self._apply_pseudo(state, move)
            king = self._find_king(after, seat)
            if king is None:
                continue
            if self._attacked(after, king, 1 - seat):
                continue
            row = dict(move)
            row["captured"] = captured
            rows.append(row)
        return rows

    def _castle_after(self, state, move, board):
        rights = state.get("castle") or ""
        piece = state["board"][int(move["from"])]
        flags = move.get("flags") or ""
        if flags == "castle":
            if piece == "K":
                rights = rights.replace("K", "").replace("Q", "")
            else:
                rights = rights.replace("k", "").replace("q", "")
        if piece in "Kk":
            rights = rights.replace("K" if piece == "K" else "k", "")
        if not rights:
            return ""
        # A rook that leaves home — or is captured on it — kills that right.
        for right, (square, _) in ROOK_HOME.items():
            if right not in rights:
                continue
            if int(move["from"]) == square or int(move["to"]) == square:
                rights = rights.replace(right, "")
        return "".join(character for character in "KQkq" if character in rights)

    def apply(self, state, seat, move):
        if state.get("winner") is not None:
            raise GameError("This game is already finished")
        if int(state["turn"]) != int(seat):
            raise GameError("It is not your turn", 409)
        try:
            start = int(move.get("from"))
            end = int(move.get("to"))
        except (TypeError, ValueError):
            raise GameError("Choose a piece, then a square") from None
        if not (0 <= start < 64 and 0 <= end < 64):
            raise GameError("Choose a square on the board")

        options = self._legal(state, int(seat))
        if not options:
            raise GameError("There are no moves left in this position", 409)
        wanted = str(move.get("promote") or "").lower() or None
        chosen = None
        for option in options:
            if option["from"] != start or option["to"] != end:
                continue
            if option.get("promote") and wanted and option["promote"] != wanted:
                continue
            if option.get("promote") and not wanted:
                # A promotion without a piece is a question, not a move: answer
                # with the four choices so the panel can ask properly.
                raise GameError("Choose a piece to promote to", 422)
            chosen = option
            break
        if chosen is None:
            legal_here = [row for row in options if row["from"] == start]
            if not legal_here:
                raise GameError("That piece has no legal move here")
            raise GameError("That move would leave your king in check")

        board, captured = self._apply_pseudo(state, chosen)
        piece = state["board"][start]
        flags = chosen.get("flags") or ""
        rights = self._castle_after(state, chosen, board)
        ep = None
        if flags == "double":
            ep = (start + end) // 2
        half = 0 if (captured or piece.lower() == "p") else int(state.get("half") or 0) + 1
        full = int(state.get("full") or 1) + (1 if int(seat) == 1 else 0)

        after = {"board": board, "turn": 1 - int(seat), "winner": None, "seats": 2,
                 "castle": rights, "ep": ep, "half": half, "full": full,
                 "history": list(state.get("history") or []),
                 "log": list(state.get("log") or []),
                 "last": None, "check": False, "moves": list(state.get("moves") or [])}

        key = self._key(board, after["turn"], rights, ep)
        after["history"].append(key)
        after["history"] = after["history"][-600:]

        replies = self._legal(after, after["turn"])
        in_check = self._attacked(board, self._find_king(board, after["turn"]), int(seat))
        after["check"] = in_check

        san = self._algebraic(state, chosen, piece, captured, replies, in_check)
        after["last"] = {"from": start, "to": end, "san": san,
                         "capture": bool(captured), "check": in_check,
                         "castle": flags == "castle",
                         "promote": chosen.get("promote")}
        after["moves"] = (after["moves"] + [square_name(start) + square_name(end)])[-400:]
        # The panel prints a scoresheet; SAN is the only notation a player can
        # read back without a board, so keep it here rather than re-deriving it.
        after["log"] = (after["log"] + [san])[-400:]

        winner = None
        if not replies:
            winner = int(seat) if in_check else "draw"
        elif half >= 100:
            winner = "draw"
        elif after["history"].count(key) >= 3:
            winner = "draw"
        elif self._insufficient(board):
            winner = "draw"
        after["winner"] = winner
        if winner is not None:
            after["turn"] = int(seat)
            after["end"] = "mate" if winner == int(seat) else "draw"
            after["last"]["mate"] = winner == int(seat) and in_check
        return after

    def _insufficient(self, board):
        """K vs K, K+B vs K, K+N vs K and K+B vs K+B on one colour."""
        pieces = [(index, piece) for index, piece in enumerate(board) if piece != "."]
        if any(piece.lower() in "pqr" for _, piece in pieces):
            return False
        if len(pieces) <= 2:
            return True
        if len(pieces) == 3 and any(piece.lower() in "bn" for _, piece in pieces):
            return True
        if len(pieces) == 4:
            bishops = [index for index, piece in pieces if piece.lower() == "b"]
            if len(bishops) == 2:
                colours = {(index // 8 + index % 8) % 2 for index in bishops}
                if len(colours) == 1:
                    return True
        return False

    def _algebraic(self, state, move, piece, captured, replies, in_check):
        flags = move.get("flags") or ""
        if flags == "castle":
            return "O-O" if int(move["to"]) in (62, 6) else "O-O-O"
        kind = piece.lower()
        target = square_name(move["to"])
        if kind == "p":
            body = (square_name(move["from"])[0] + "x" if captured else "") + target
            if move.get("promote"):
                body += "=" + move["promote"].upper()
        else:
            body = piece.upper() + (self._disambiguate(state, move, piece) or "") + \
                ("x" if captured else "") + target
        if not replies:
            return body + ("#" if in_check else "")
        if in_check:
            return body + "+"
        return body

    def _disambiguate(self, state, move, piece):
        """The smallest prefix that names this piece uniquely."""
        others = [other for other in self._pseudo(state, _owner(piece))
                  if other["to"] == move["to"] and other["from"] != move["from"]
                  and state["board"][other["from"]] == piece]
        if not others:
            return ""
        row, col = divmod(int(move["from"]), 8)
        same_file = any(other["from"] % 8 == col for other in others)
        same_rank = any(other["from"] // 8 == row for other in others)
        if not same_file:
            return FILES[col]
        if not same_rank:
            return str(8 - row)
        return square_name(move["from"])

    @staticmethod
    def _key(board, turn, rights, ep):
        return "".join(board) + f"|{turn}|{rights}|{ep}"

    def legal(self, state, seat):
        if state.get("winner") is not None or int(state["turn"]) != int(seat):
            return []
        rows = []
        for move in self._legal(state, int(seat)):
            row = {"from": move["from"], "to": move["to"], "flags": move.get("flags") or ""}
            if move.get("promote"):
                row["promote"] = move["promote"]
            rows.append(row)
        return rows

    def auto(self, state):
        """A timeout plays the first legal move. Deliberately dull, not random."""
        options = self.legal(state, state["turn"])
        if not options:
            return dict(state, winner="draw")
        return self.apply(state, state["turn"], options[0])

    def view(self, state, seat):
        return state

    def result(self, state):
        return state.get("winner")
