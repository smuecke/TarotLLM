from __future__ import annotations

import random
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .cards import CARDS, DECK
from .oracle import ReadingRequest, generate_reading, stream_text
from .spreads import SPREADS


ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Tarot Oracle")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/img", StaticFiles(directory=ROOT / "img"), name="img")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/cards")
async def cards() -> dict[str, object]:
    return {
        "deck": DECK.to_public(),
        "cards": [card.to_public() for card in CARDS],
    }


@app.get("/api/random")
async def random_cards(count: int = 3) -> dict[str, object]:
    if count < 1 or count > len(CARDS):
        raise HTTPException(status_code=400, detail="Invalid card count")
    return {"cards": [card.to_public() for card in random.sample(CARDS, count)]}


@app.get("/api/spreads")
async def spreads() -> dict[str, object]:
    return {"spreads": [spread.to_public() for spread in SPREADS]}


@app.post("/api/reading")
async def reading(request: ReadingRequest) -> StreamingResponse:
    try:
        result = await generate_reading(request)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(stream_text(result), media_type="text/plain; charset=utf-8")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    import uvicorn

    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
