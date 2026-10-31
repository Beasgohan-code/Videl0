"""Safe, bounded group FAQ records used by welcome and the /faq command."""
from __future__ import annotations

MAX_ITEMS = 8
MAX_QUESTION = 100
MAX_ANSWER = 600


def normalize(raw) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    items = []
    for value in raw[:MAX_ITEMS]:
        if not isinstance(value, dict):
            continue
        question, answer = value.get("question"), value.get("answer")
        if (isinstance(question, str) and isinstance(answer, str)
                and 0 < len(question.strip()) <= MAX_QUESTION
                and 0 < len(answer.strip()) <= MAX_ANSWER):
            items.append({"question": question.strip(), "answer": answer.strip()})
    return items


def add(raw, question: str, answer: str) -> list[dict[str, str]]:
    if not isinstance(question, str) or not isinstance(answer, str):
        raise ValueError("Enter a question and answer.")
    question, answer = question.strip(), answer.strip()
    if not question or len(question) > MAX_QUESTION:
        raise ValueError(f"Questions must be 1–{MAX_QUESTION} characters.")
    if not answer or len(answer) > MAX_ANSWER:
        raise ValueError(f"Answers must be 1–{MAX_ANSWER} characters.")
    items = normalize(raw)
    for item in items:
        if item["question"].casefold() == question.casefold():
            item["answer"] = answer
            return items
    if len(items) >= MAX_ITEMS:
        raise ValueError(f"This FAQ already has {MAX_ITEMS} entries. Remove one before adding another.")
    items.append({"question": question, "answer": answer})
    return items


def remove(raw, index: int) -> list[dict[str, str]]:
    items = normalize(raw)
    if type(index) is not int or not 1 <= index <= len(items):
        raise ValueError("Choose a question number shown by /setfaq.")
    del items[index - 1]
    return items
