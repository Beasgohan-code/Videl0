"""Validated, plain-text poll builder for the current Telegram Bot API."""

from __future__ import annotations


def build_poll(text: str, quiz: bool = False) -> dict:
    parts = [part.strip() for part in text.split("|")]
    if len(parts) < 3:
        raise ValueError(
            "Use Question | Option 1 | Option 2. Mark correct quiz answers with a leading *."
        )
    question = parts[0]
    flags = []
    while question.startswith("--"):
        flag, separator, rest = question.partition(" ")
        if not separator:
            raise ValueError("Add a question after the poll options.")
        flags.append(flag)
        question = rest.lstrip()
    known = {
        "--multiple",
        "--public",
        "--shuffle",
        "--revote",
        "--add-options",
        "--hide-results",
        "--members-only",
    }
    if any(flag not in known for flag in flags):
        raise ValueError("Unknown poll flag. Use /modernhelp for supported options.")
    if not question or len(question.encode("utf-16-le")) // 2 > 300:
        raise ValueError("Questions must contain 1–300 characters.")
    answers, correct = [], []
    for index, part in enumerate(parts[1:]):
        if quiz and part.startswith("*"):
            correct.append(index)
            part = part[1:].strip()
        if not part or len(part.encode("utf-16-le")) // 2 > 100:
            raise ValueError("Each option must contain 1–100 characters.")
        answers.append({"text": part})
    if not 2 <= len(answers) <= 10:
        raise ValueError("Add 2–10 options.")
    if len({option["text"].casefold() for option in answers}) != len(answers):
        raise ValueError("Poll options must be different.")
    if quiz and not correct:
        raise ValueError("Mark at least one correct quiz answer with *.")
    if quiz and "--add-options" in flags:
        raise ValueError("Quiz participants cannot add answer options.")
    result = {
        "question": question,
        "options": answers,
        "type": "quiz" if quiz else "regular",
        "is_anonymous": "--public" not in flags,
        "allows_multiple_answers": len(correct) > 1 if quiz else "--multiple" in flags,
        "allows_revoting": "--revote" in flags if quiz else True,
        "shuffle_options": "--shuffle" in flags,
        "hide_results_until_closes": "--hide-results" in flags,
        "members_only": "--members-only" in flags,
    }
    if quiz:
        result["correct_option_ids"] = correct
    else:
        result["allow_adding_options"] = "--add-options" in flags
    return result
