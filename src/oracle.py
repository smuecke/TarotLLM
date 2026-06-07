from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.capabilities.web_search import WebSearch
from pydantic_ai.models.openai import OpenAIResponsesModel

from .cards import CARD_BY_KEY, DECK, DivinationCard
from .config import ROOT, load_env


LOGS_DIR = ROOT / "logs"
SYSTEM_PROMPTS = {
    "English": (
        "You are a mystical, wise, but down-to-earth Oracle that interprets "
        "fortune-telling cards, especially Tarot. As input, you receive a deck, a "
        "spread, and the specific drawn cards plus information and their roles "
        "within the spread. You also receive input from a person, possibly a "
        "question or background information about their situation. Interpret the "
        "cards carefully with reference to the person in about 100 to 300 words. "
        "Do not consider the cards only in isolation; instead, try to draw "
        "connections and find a holistic interpretation in which all cards work "
        "together to reveal a truth. Do not claim to be certain about things you "
        "cannot know, and do not present the interpretation as medical, legal, "
        "financial, or safety-critical advice. Return a single continuous "
        "interpretation as flowing text that feels like a spoken oracle. Do not use "
        "text structuring such as headings or lists. Wherever it makes sense, let "
        "specific cards and their functions in the current spread flow in naturally "
        "and explain them. If the person asked a question, try to give an answer, "
        "also in flowing text. Write in the language of the asking person. If they "
        "wrote nothing, use the language of the deck. If you need more information, "
        "use the web search tool, if it is available. Also return an assessment of "
        "how certain or unambiguous your interpretation is (1: very uncertain/"
        "unclear, to 4: very certain/unambiguous)."
    ),
    "German": (
        "Du bist ein mystisches, weises, aber bodenständiges Orakel, das Wahrsagekarten "
        "interpretiert, vor allem Tarot. Du erhältst als Eingabe ein Deck, ein Legesystem, "
        "und die konkreten gezogenen Karten plus Infos und ihre Rollen innerhalb "
        "des Legesystems. Außerdem erhältst du eine Eingabe von einer Person, "
        "möglicherweise eine Frage, oder Hintergrundinformationen zu ihrer Situation. "
        "Deute die Karten sorgfältig mit Bezug auf die Person in etwa 100 bis 300 "
        "Wörtern. Betrachte die Karten nicht nur isoliert, sondern versuche, Verbindungen "
        "zu ziehen und eine ganzheitliche Deutung zu finden, "
        "in der alle Karten zusammenspielen um eine Wahrheit zu enthüllen. "
        "Behaupte nicht, sicher zu sein bei Dingen, die du nicht wissen kannst, "
        "und stelle die Deutung nicht als medizinischen, juristischen, finanziellen "
        "oder sicherheitskritischen Rat dar. Gib eine einzige zusammenhängende Deutung "
        "als Fließtext zurück, die sich wie ein gesprochenes Orakel anfühlt. Nutze "
        "keine Textstrukturierung wie Überschriften oder Listen. Wo immer es sinnvoll "
        "ist, lass konkrete Karten und ihre Funktionen in der aktuellen Legung natürlich "
        "einfließen und erläutere sie. Wenn die Person eine Frage gestellt hat, "
        "versuch, eine Antwort zu geben, ebenfalls im Fließtext. Schreibe in der "
        "Sprache der fragenden Person. Wenn sie nichts geschrieben hat, verwende "
        "die Sprache des Decks. Wenn du mehr Informationen brauchst, nutze das Websuchwerkzeug, "
        "sofern es verfügbar ist. Gib außerdem eine Einschätzung zurück, wie sicher oder eindeutig "
        "deine Deutung ist (1: sehr unsicher/unklar, bis 4: sehr sicher/eindeutig)."
    ),
}

PROMPT_LABELS = {
    "English": {
        "current_context": "Current context",
        "current_date": "Current date",
        "current_time": "Current time",
        "day_of_week": "Day of the week",
        "time_zone": "Time zone",
        "spread": "Spread",
        "description": "Description",
        "cards_and_context": "Cards and context",
        "deck": "Deck",
        "language": "Language",
        "drawing": "Drawing",
        "visual": "Visual",
        "interpretation": "Interpretation",
        "role": "Role within the spread",
        "relevant": "Relevant information for this spread",
        "user_input": "User input",
        "unknown": "Unknown",
        "no_role": "No role supplied.",
        "no_relevant": "No shared tag context supplied.",
        "no_description": "No spread description supplied.",
        "no_user_input": "No user input supplied.",
    },
    "German": {
        "current_context": "Aktueller Kontext",
        "current_date": "Aktuelles Datum",
        "current_time": "Aktuelle Uhrzeit",
        "day_of_week": "Wochentag",
        "time_zone": "Zeitzone",
        "spread": "Legesystem",
        "description": "Beschreibung",
        "cards_and_context": "Karten und Infos",
        "deck": "Deck",
        "language": "Sprache",
        "drawing": "Legung",
        "visual": "Bildbeschreibung",
        "interpretation": "Bedeutung",
        "role": "Rolle im Legesystem",
        "relevant": "Relevante Informationen für diese Legung",
        "user_input": "Eingabe der Person",
        "unknown": "Unbekannt",
        "no_role": "Keine Rolle angegeben.",
        "no_relevant": "Kein gemeinsamer Tag-Kontext",
        "no_description": "Keine Beschreibung",
        "no_user_input": "Keine Eingabe",
    },
}


class SpreadCard(BaseModel):
    position: str
    key: str
    role: str = ""


class ReadingRequest(BaseModel):
    spread_name: str = Field(alias="spreadName")
    spread_description: str = Field(default="", alias="spreadDescription")
    time_zone: str = Field(default="", alias="timeZone")
    prompt: str
    cards: list[SpreadCard]


class ReadingResult(BaseModel):
    reading: str
    certainty: int = Field(ge=1, le=4)


def prompt_logging_enabled() -> bool:
    return os.getenv("PROMPT_LOGGING", "").strip().lower() in {"1", "true", "yes", "on"}


def web_search_enabled() -> bool:
    return os.getenv("WEB_SEARCH_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def openai_responses_model_name() -> str:
    model_name = os.getenv("LLM_MODEL", "gpt-5-mini").strip()
    for prefix in ("openai-responses:", "openai:"):
        if model_name.startswith(prefix):
            return model_name.removeprefix(prefix)
    return model_name


def deck_language() -> str:
    language = (DECK.language or "").strip().lower()
    if language.startswith(("de", "ger")):
        return "German"
    return "English"


def prompt_labels() -> dict[str, str]:
    return PROMPT_LABELS[deck_language()]


def system_prompt() -> str:
    return SYSTEM_PROMPTS[deck_language()]


def display_deck_language() -> str:
    if deck_language() == "German":
        return "Deutsch"
    return DECK.language or prompt_labels()["unknown"]


def weekday_name(now: datetime) -> str:
    if deck_language() == "German":
        names = [
            "Montag",
            "Dienstag",
            "Mittwoch",
            "Donnerstag",
            "Freitag",
            "Samstag",
            "Sonntag",
        ]
        return names[now.weekday()]
    return now.strftime("%A")


def current_context(
    *, labels: dict[str, str], request_time_zone: str = ""
) -> str:
    time_zone_name = request_time_zone.strip()
    if time_zone_name:
        try:
            now = datetime.now(ZoneInfo(time_zone_name))
        except ZoneInfoNotFoundError:
            now = datetime.now().astimezone()
            time_zone_name = now.tzinfo.tzname(now) if now.tzinfo else "Unknown"
    else:
        now = datetime.now().astimezone()
        time_zone_name = now.tzinfo.tzname(now) if now.tzinfo else "Unknown"

    return (
        f"{labels['current_date']}: {now.date().isoformat()}\n"
        f"{labels['current_time']}: {now.strftime('%H:%M:%S %Z%z')}\n"
        f"{labels['day_of_week']}: {weekday_name(now)}\n"
        f"{labels['time_zone']}: {time_zone_name}"
    )


def llm_log_path() -> Path | None:
    if not prompt_logging_enabled():
        return None

    file_stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / f"llm-call-{file_stamp}.log"


def write_llm_log(
    *,
    path: Path | None,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    web_search: bool,
) -> None:
    if path is None:
        return

    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with path.open("w", encoding="utf-8") as log:
        log.write(
            "=" * 88
            + "\n"
            + f"Timestamp: {timestamp}\n"
            + f"Model: {model_name}\n"
            + f"Web search enabled: {web_search}\n"
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


def append_llm_log_section(path: Path | None, heading: str, content: str) -> None:
    if path is None:
        return

    with path.open("a", encoding="utf-8") as log:
        log.write(
            "-" * 88
            + "\n"
            + heading
            + "\n"
            + "-" * 88
            + "\n"
            + content.rstrip()
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


def drawing_lines(
    resolved: list[tuple[SpreadCard, DivinationCard]], labels: dict[str, str]
) -> list[str]:
    lines: list[str] = []
    for item, card in resolved:
        tags = ", ".join(card.tag_labels) if card.tag_labels else ", ".join(card.tags)
        lines.extend(
            [
                f"- {item.position}: {card.name}{f' [{tags}]' if tags else ''}",
                f"{labels['visual']}: {card.visual}",
                f"{labels['interpretation']}: {card.meaning}",
                f"{labels['role']}: {item.role or labels['no_role']}",
            ]
        )
    return lines


def card_context(cards: list[SpreadCard]) -> tuple[list[tuple[SpreadCard, DivinationCard]], str]:
    labels = prompt_labels()
    resolved = resolve_cards(cards)
    drawing = "\n".join(drawing_lines(resolved, labels))
    relevant = "\n".join(relevant_tag_lines(resolved)) or labels["no_relevant"]
    context = (
        f"{labels['deck']}: {DECK.name}\n"
        f"{labels['language']}: {display_deck_language()}\n\n"
        f"{labels['drawing']}:\n{drawing}\n\n"
        f"{labels['relevant']}:\n{relevant}"
    )
    return resolved, context


def build_user_prompt(request: ReadingRequest) -> str:
    labels = prompt_labels()
    _, context = card_context(request.cards)
    return (
        f"{labels['current_context']}:\n"
        f"{current_context(labels=labels, request_time_zone=request.time_zone)}\n\n"
        f"{labels['spread']}: {request.spread_name}\n"
        f"{labels['description']}: {request.spread_description or labels['no_description']}\n\n"
        f"{labels['cards_and_context']}:\n"
        f"{context}\n\n"
        f"{labels['user_input']}:\n"
        f"{request.prompt.strip() or labels['no_user_input']}"
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
    model_name = openai_responses_model_name()
    search_enabled = web_search_enabled()
    active_system_prompt = system_prompt()
    capabilities = (
        [WebSearch(native=True, local=False, search_context_size="medium", max_uses=3)]
        if search_enabled
        else []
    )
    model = OpenAIResponsesModel(model_name)
    agent = Agent(
        model,
        output_type=ReadingResult,
        system_prompt=active_system_prompt,
        capabilities=capabilities,
    )
    user_prompt = build_user_prompt(request)
    log_path = llm_log_path()
    write_llm_log(
        path=log_path,
        model_name=model_name,
        system_prompt=active_system_prompt,
        user_prompt=user_prompt,
        web_search=search_enabled,
    )
    try:
        result = await agent.run(user_prompt)
    except Exception as exc:
        append_llm_log_section(log_path, "ERROR", repr(exc))
        raise

    output = result.output if hasattr(result, "output") else result.data
    append_llm_log_section(
        log_path,
        "LLM RESPONSE",
        json.dumps(output.model_dump(), ensure_ascii=False, indent=2),
    )
    usage = result.usage
    if callable(usage):
        usage = usage()
    append_llm_log_section(
        log_path,
        "USAGE",
        json.dumps(usage.__dict__, ensure_ascii=False, indent=2, default=str),
    )
    trace = result.all_messages_json()
    if isinstance(trace, bytes):
        trace = trace.decode("utf-8")
    append_llm_log_section(log_path, "MESSAGE AND TOOL TRACE", str(trace))
    return output


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
