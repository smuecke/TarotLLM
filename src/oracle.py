from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from .cards import CARD_BY_KEY, DECK, DivinationCard


ROOT = Path(__file__).resolve().parent.parent
PROMPT_LOG_PATH = ROOT / "logs" / "prompts.log"
SYSTEM_PROMPT = (
    "You are a mystical but grounded Oracle that reads and interprets fortune-telling "
    "cards, mainly Tarot. You receive a spread of cards with information about each "
    "card and its role within the spread. Moreover, you receive input from a user, "
    "possibly consisting of a question or background info about their situation. "
    "Interpret the cards with care, do not claim certainty about facts you cannot "
    "know, and do not present the reading as medical, legal, financial, or "
    "safety-critical advice. Return one continuous reading that feels like a spoken "
    "oracle transcript, not a report, outline, or card-by-card list. Mention cards "
    "and their spread positions naturally and colloquially, weaving them into the "
    "flow instead of using headings such as 'Past - The Devil' or 'Future - Six of "
    "Wands'. Do not create a separate answer section. If possible, let a concrete "
    "answer emerge within the same mystical, grounded prose. Answer in the user's "
    "language. If the user did not write anything, use the language of the deck."
)


class SpreadCard(BaseModel):
    position: str
    key: str
    role: str = ""


class ReadingRequest(BaseModel):
    spread_name: str = Field(alias="spreadName")
    spread_description: str = Field(default="", alias="spreadDescription")
    prompt: str
    cards: list[SpreadCard]


class ReadingResult(BaseModel):
    reading: str
    certainty: int = Field(ge=1, le=4)


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def prompt_logging_enabled() -> bool:
    return os.getenv("PROMPT_LOGGING", "").strip().lower() in {"1", "true", "yes", "on"}


def append_prompt_log(*, model_name: str, system_prompt: str, user_prompt: str) -> None:
    if not prompt_logging_enabled():
        return

    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    PROMPT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROMPT_LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(
            "\n"
            + "=" * 88
            + "\n"
            + f"Timestamp: {timestamp}\n"
            + f"Model: {model_name}\n"
            + "-" * 88
            + "\n"
            + "SYSTEM PROMPT\n"
            + "-" * 88
            + "\n"
            + system_prompt
            + "\n"
            + "-" * 88
            + "\n"
            + "USER PROMPT\n"
            + "-" * 88
            + "\n"
            + user_prompt
            + "\n"
        )


def resolve_cards(cards: list[SpreadCard]) -> list[tuple[SpreadCard, DivinationCard]]:
    resolved: list[tuple[SpreadCard, DivinationCard]] = []
    for item in cards:
        card = CARD_BY_KEY.get(item.key)
        if card is None:
            raise ValueError(f"Unknown card key: {item.key}")
        resolved.append((item, card))
    return resolved


def relevant_tag_lines(resolved: list[tuple[SpreadCard, DivinationCard]]) -> list[str]:
    seen_tags: set[str] = set()
    lines: list[str] = []
    for _, card in resolved:
        for tag in card.tags:
            if tag in seen_tags:
                continue
            seen_tags.add(tag)
            tag_info = DECK.tags.get(tag)
            if tag_info and tag_info.context:
                lines.append(f"- {tag_info.label}: {tag_info.context}")
    return lines


def drawing_lines(resolved: list[tuple[SpreadCard, DivinationCard]]) -> list[str]:
    lines: list[str] = []
    for item, card in resolved:
        tags = ", ".join(card.tag_labels) if card.tag_labels else ", ".join(card.tags)
        lines.extend(
            [
                f"- {item.position}: {card.name}{f' [{tags}]' if tags else ''}",
                f"Visual: {card.visual}",
                f"Interpretation: {card.meaning}",
                f"Role within the spread: {item.role or 'No role supplied.'}",
            ]
        )
    return lines


def card_context(cards: list[SpreadCard]) -> tuple[list[tuple[SpreadCard, DivinationCard]], str]:
    resolved = resolve_cards(cards)
    drawing = "\n".join(drawing_lines(resolved))
    relevant = "\n".join(relevant_tag_lines(resolved)) or "No shared tag context supplied."
    context = (
        f"Deck: {DECK.name}\n"
        f"Language: {DECK.language or 'Unknown'}\n\n"
        f"Drawing:\n{drawing}\n\n"
        f"Relevant information for this spread:\n{relevant}"
    )
    return resolved, context


def build_user_prompt(request: ReadingRequest) -> str:
    _, context = card_context(request.cards)
    return (
        f"Spread: {request.spread_name}\n"
        f"Description: {request.spread_description or 'No spread description supplied.'}\n\n"
        f"Cards and context:\n"
        f"{context}\n\n"
        f"User input:\n"
        f"{request.prompt.strip() or 'No user input supplied.'}"
    )


async def generate_reading(request: ReadingRequest) -> ReadingResult:
    load_env()
    if os.getenv("OPENAI_API_KEY"):
        try:
            return await generate_with_llm(request)
        except Exception as exc:
            fallback = generate_local_reading(request)
            fallback.reading += (
                "\n\nThe live oracle could not be reached, so this reading was "
                f"formed from the local card context instead. Backend note: {exc}"
            )
            fallback.certainty = min(fallback.certainty, 2)
            return fallback
    return generate_local_reading(request)


async def generate_with_llm(request: ReadingRequest) -> ReadingResult:
    model_name = os.getenv("LLM_MODEL", "openai:gpt-4o-mini")
    agent = Agent(model_name, output_type=ReadingResult, system_prompt=SYSTEM_PROMPT)
    user_prompt = build_user_prompt(request)
    append_prompt_log(
        model_name=model_name,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    result = await agent.run(user_prompt)
    if hasattr(result, "output"):
        return result.output
    return result.data


def generate_local_reading(request: ReadingRequest) -> ReadingResult:
    resolved, _ = card_context(request.cards)
    prompt = request.prompt.strip()
    tag_counts: dict[str, int] = {}
    for _, card in resolved:
        for tag in card.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    certainty = 2
    if len(resolved) >= 5:
        certainty += 1
    repeated_tags = [tag for tag, count in tag_counts.items() if count > 1]
    if repeated_tags:
        certainty += 1
    certainty = max(1, min(4, certainty))

    card_phrases = []
    for item, card in resolved:
        role = item.role.rstrip(".")
        card_phrases.append(
            f"In the place of {item.position.lower()}, {card.name} carries the sense that "
            f"{card.meaning[0].lower() + card.meaning[1:]}"
            f"{f' It belongs to {role.lower()}.' if role else ''}"
        )

    if repeated_tags:
        tag_names = [
            DECK.tags[tag].label for tag in repeated_tags if tag in DECK.tags
        ] or repeated_tags
        tag_sentence = (
            f"A repeated current moves through the spread: {', '.join(tag_names[:3])}. "
        )
    else:
        tag_sentence = (
            "The spread does not speak with one repeated symbol, but with changing weather. "
        )
    final_card = resolved[-1][1]
    user_reference = (
        f"Holding your question, \"{prompt}\", " if prompt else "Without a stated question, "
    )
    reading = (
        f"{tag_sentence}"
        f"{user_reference}the cards seem to speak less like a verdict and more like a lantern "
        f"held over the path. "
        f"{' '.join(card_phrases)} "
        f"The final note rests with {final_card.name}, so the movement of the reading bends "
        f"toward this: {final_card.meaning[0].lower() + final_card.meaning[1:]} "
        "Take it as a symbolic reading of the pattern, not as fate sealed in wax."
    )
    return ReadingResult(
        reading=reading,
        certainty=certainty,
    )


async def stream_text(result: ReadingResult) -> AsyncIterator[str]:
    payload = f"{result.reading}\n\n[[CERTAINTY:{result.certainty}]]"
    for token in re.split(r"(\s+)", payload):
        if token:
            yield token
            await asyncio.sleep(0.012)
