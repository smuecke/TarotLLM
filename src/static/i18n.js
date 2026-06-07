const TEXT = {
  English: {
    appTitle: "Tarot Oracle",
    tableAria: "Tarot spread workspace",
    spreadHint: "Choose a spread, set the cards, and ask.",
    spreadLabel: "Spread",
    randomButton: "Random",
    clearButton: "Clear",
    promptPlaceholder: "Describe the situation or ask the oracle a question...",
    certaintyAria: "Certainty rating",
    certaintyLabel: "Certainty",
    submitButton: "Ask Oracle",
    readingPaneAria: "Oracle reading",
    readingTitle: "Reading",
    copyButton: "Copy",
    copiedButton: "Copied",
    readingPlaceholder: "The reading will appear here as the oracle speaks.",
    noSpreads: "No spreads found.",
    cardButtonTitle: "Left click cycles cards. Right click opens the deck chooser.",
    chooseCard: "Choose card",
    deckTitle: "Deck",
    closeButton: "Close",
    closeAria: "Close",
    searchPlaceholder: "Search cards or tags...",
    listening: "Listening...",
    oracleError: "The oracle could not answer:",
  },
  German: {
    appTitle: "Tarot-Orakel",
    tableAria: "Arbeitsfläche für die Tarot-Legung",
    spreadHint: "Wähle ein Legesystem, lege die Karten und frage das Orakel.",
    spreadLabel: "Legesystem",
    randomButton: "Zufällig",
    clearButton: "Zurücksetzen",
    promptPlaceholder: "Beschreibe die Situation oder stelle dem Orakel eine Frage...",
    certaintyAria: "Sicherheitsbewertung",
    certaintyLabel: "Sicherheit",
    submitButton: "Orakel befragen",
    readingPaneAria: "Orakel-Deutung",
    readingTitle: "Deutung",
    copyButton: "Kopieren",
    copiedButton: "Kopiert",
    readingPlaceholder: "Die Deutung erscheint hier, während das Orakel spricht.",
    noSpreads: "Keine Legesysteme gefunden.",
    cardButtonTitle: "Linksklick wechselt die Karte. Rechtsklick öffnet die Kartenauswahl.",
    chooseCard: "Karte wählen",
    deckTitle: "Deck",
    closeButton: "Schließen",
    closeAria: "Schließen",
    searchPlaceholder: "Karten oder Tags suchen...",
    listening: "Lausche...",
    oracleError: "Das Orakel konnte nicht antworten:",
  },
};

let currentLanguage = "English";

export function setLanguage(language) {
  const normalized = String(language || "").trim().toLowerCase();
  currentLanguage = normalized.startsWith("de") || normalized.startsWith("ger")
    ? "German"
    : "English";
}

export function t(key) {
  return TEXT[currentLanguage][key] || TEXT.English[key] || key;
}

export function applyStaticText() {
  document.documentElement.lang = currentLanguage === "German" ? "de" : "en";
  document.title = t("appTitle");

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAria));
  });
}
