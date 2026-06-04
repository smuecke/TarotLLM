let cards = [];
let cardsByKey = new Map();
let spreads = [];
let deck = { name: "Deck" };
let currentSpread = null;
let selectedKeys = [];
let readingText = "";
let pickerIndex = null;

const spreadSelect = document.querySelector("#spreadSelect");
const spreadHint = document.querySelector("#spreadHint");
const spreadBoard = document.querySelector("#spreadBoard");
const randomButton = document.querySelector("#randomButton");
const clearButton = document.querySelector("#clearButton");
const oracleForm = document.querySelector("#oracleForm");
const promptInput = document.querySelector("#promptInput");
const submitButton = document.querySelector("#submitButton");
const readingOutput = document.querySelector("#readingOutput");
const certaintyDots = Array.from(document.querySelectorAll("#certaintyDots i"));
const copyButton = document.querySelector("#copyButton");
const cardPicker = document.querySelector("#cardPicker");
const pickerClose = document.querySelector("#pickerClose");
const pickerPosition = document.querySelector("#pickerPosition");
const pickerTitle = document.querySelector("#pickerTitle");
const pickerSearch = document.querySelector("#pickerSearch");
const pickerGrid = document.querySelector("#pickerGrid");

async function init() {
  const [cardsResponse, spreadsResponse] = await Promise.all([
    fetch("/api/cards"),
    fetch("/api/spreads"),
  ]);
  const cardsPayload = await cardsResponse.json();
  const spreadsPayload = await spreadsResponse.json();
  deck = cardsPayload.deck || deck;
  cards = cardsPayload.cards;
  spreads = spreadsPayload.spreads || [];
  currentSpread = spreads[0] || null;
  cardsByKey = new Map(cards.map((card) => [card.key, card]));
  spreads.forEach((spread) => {
    const option = document.createElement("option");
    option.value = spread.id;
    option.textContent = spread.name;
    spreadSelect.append(option);
  });
  selectedKeys = currentSpread ? defaultKeysForSpread(currentSpread) : [];
  render();
}

function defaultKeysForSpread(spread) {
  return cards.slice(0, spread.positions.length).map((card) => card.key);
}

function render() {
  if (!currentSpread) {
    spreadHint.textContent = "No spreads found.";
    spreadBoard.innerHTML = "";
    submitButton.disabled = true;
    randomButton.disabled = true;
    clearButton.disabled = true;
    return;
  }

  submitButton.disabled = false;
  randomButton.disabled = false;
  clearButton.disabled = false;
  spreadHint.textContent = currentSpread.description;
  spreadBoard.innerHTML = "";
  currentSpread.positions.forEach((position, index) => {
    const card = cardsByKey.get(selectedKeys[index]) || cards[0];
    const slot = document.createElement("div");
    slot.className = "slot";
    slot.style.setProperty("--x", position.x);
    slot.style.setProperty("--y", position.y);
    slot.style.setProperty("--rot", position.rot || "0deg");

    const button = document.createElement("button");
    button.className = "card-button";
    button.type = "button";
    button.title = "Left click cycles cards. Right click opens the deck chooser.";
    button.addEventListener("click", () => cycleCard(index));
    button.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      openPicker(index);
    });

    const image = document.createElement("img");
    image.className = "card-face";
    image.src = card.image;
    image.alt = card.name;
    button.append(image);

    const label = document.createElement("span");
    label.className = "position-label";
    label.textContent = position.name;

    const name = document.createElement("span");
    name.className = "card-name";
    name.textContent = card.name;

    slot.append(button, label, name);
    spreadBoard.append(slot);
  });
}

function cycleCard(index) {
  if (!cards.length) return;
  const current = cardsByKey.get(selectedKeys[index]) || cards[0];
  const currentIndex = cards.findIndex((card) => card.key === current.key);
  const next = cards[(currentIndex + 1) % cards.length];
  selectedKeys[index] = next.key;
  render();
}

function openPicker(index) {
  if (!currentSpread) return;
  pickerIndex = index;
  const position = currentSpread.positions[index];
  pickerPosition.textContent = position ? position.name : "Choose card";
  pickerTitle.textContent = deck.name || "Deck";
  pickerSearch.value = "";
  renderPicker();
  cardPicker.showModal();
  pickerSearch.focus();
}

function renderPicker() {
  const query = pickerSearch.value.trim().toLowerCase();
  const visibleCards = cards.filter((card) => {
    const haystack = [card.name, ...(card.tagLabels || []), ...(card.tags || [])]
      .join(" ")
      .toLowerCase();
    return !query || haystack.includes(query);
  });

  pickerGrid.innerHTML = "";
  visibleCards.forEach((card) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "picker-card";
    button.addEventListener("click", () => chooseCard(card.key));

    const image = document.createElement("img");
    image.src = card.image;
    image.alt = card.name;

    const name = document.createElement("span");
    name.textContent = card.name;

    button.append(image, name);
    pickerGrid.append(button);
  });
}

function chooseCard(key) {
  if (pickerIndex === null) return;
  selectedKeys[pickerIndex] = key;
  cardPicker.close();
  pickerIndex = null;
  render();
}

async function dealRandom() {
  if (!currentSpread) return;
  const response = await fetch(`/api/random?count=${currentSpread.positions.length}`);
  const payload = await response.json();
  selectedKeys = payload.cards.map((card) => card.key);
  render();
}

function clearReading() {
  readingText = "";
  readingOutput.innerHTML = '<p class="muted">The reading will appear here as the oracle speaks.</p>';
  setCertainty(0);
}

function markdownish(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .split(/\n{2,}/)
    .map((block) => {
      return `<p>${block.replace(/\n/g, "<br>")}</p>`;
    })
    .join("");
}

function setCertainty(value) {
  certaintyDots.forEach((dot, index) => {
    dot.classList.toggle("active", index < value);
  });
}

async function askOracle(event) {
  event.preventDefault();
  if (!currentSpread) return;
  submitButton.disabled = true;
  readingText = "";
  setCertainty(0);
  readingOutput.innerHTML = '<p class="muted">Listening...</p>';

  const body = {
    spreadName: currentSpread.name,
    spreadDescription: currentSpread.description,
    prompt: promptInput.value,
    cards: currentSpread.positions.map((position, index) => ({
      position: position.name,
      role: position.role || "",
      key: selectedKeys[index],
    })),
  };

  try {
    const response = await fetch("/api/reading", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok || !response.body) {
      throw new Error(await response.text());
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      readingText += decoder.decode(value, { stream: true });
      renderReading();
    }
  } catch (error) {
    readingOutput.innerHTML = `<p class="muted">The oracle could not answer: ${String(error.message || error)}</p>`;
  } finally {
    submitButton.disabled = false;
  }
}

function renderReading() {
  const match = readingText.match(/\[\[CERTAINTY:(\d)\]\]/);
  const visibleText = readingText.replace(/\[\[CERTAINTY:\d\]\]/, "");
  if (match) setCertainty(Number(match[1]));
  readingOutput.innerHTML = markdownish(visibleText.trim() || "Listening...");
  readingOutput.scrollTop = readingOutput.scrollHeight;
}

spreadSelect.addEventListener("change", () => {
  currentSpread = spreads.find((spread) => spread.id === spreadSelect.value) || spreads[0];
  selectedKeys = currentSpread ? defaultKeysForSpread(currentSpread) : [];
  clearReading();
  render();
});

randomButton.addEventListener("click", dealRandom);
clearButton.addEventListener("click", () => {
  selectedKeys = currentSpread ? defaultKeysForSpread(currentSpread) : [];
  clearReading();
  render();
});
oracleForm.addEventListener("submit", askOracle);
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(readingText.replace(/\[\[CERTAINTY:\d\]\]/, "").trim());
  copyButton.textContent = "Copied";
  setTimeout(() => {
    copyButton.textContent = "Copy";
  }, 1200);
});
pickerSearch.addEventListener("input", renderPicker);
pickerClose.addEventListener("click", () => cardPicker.close());
cardPicker.addEventListener("close", () => {
  pickerIndex = null;
});

init();
