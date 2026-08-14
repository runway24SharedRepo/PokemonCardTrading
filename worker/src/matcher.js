export function normalizeTitle(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

export function parseRule(searchName, queryKeywords = "") {
  const original = String(searchName || "").trim();
  const targetMatch = original.match(/\s*[-–—]\s*target\s*£?\s*([\d,.]+)\s*$/i);
  if (!targetMatch) {
    throw new Error(`Saved Search '${original}' is not target-labelled.`);
  }
  const withoutTarget = original.slice(0, targetMatch.index).trim();
  const identity = withoutTarget || String(queryKeywords || "").trim();
  const tokens = identity.split(/\s+/).filter(Boolean);
  let cardNumber = "";
  if (tokens.length > 1 && /^(?:[a-z]{0,4}\d+[a-z]{0,4}|\d+\/\d+)$/i.test(tokens.at(-1))) {
    cardNumber = tokens.pop();
  }
  const cardName = tokens.join(" ").trim();
  if (!cardName) throw new Error(`Saved Search '${original}' has no card name.`);
  return {
    searchName: original,
    queryKeywords: String(queryKeywords || identity).trim() || identity,
    cardName,
    cardNumber,
    // Retained for the dashboard label only. It is never used for filtering.
    targetGbp: Number(targetMatch[1].replace(/,/g, "")) || 0,
  };
}

function containsTokenSequence(titleTokens, wantedTokens) {
  if (!wantedTokens.length || wantedTokens.length > titleTokens.length) return false;
  for (let start = 0; start <= titleTokens.length - wantedTokens.length; start += 1) {
    let equal = true;
    for (let offset = 0; offset < wantedTokens.length; offset += 1) {
      if (titleTokens[start + offset] !== wantedTokens[offset]) {
        equal = false;
        break;
      }
    }
    if (equal) return true;
  }
  return false;
}

export function titleMatchesRule(title, rule) {
  const titleTokens = normalizeTitle(title).split(" ").filter(Boolean);
  const nameTokens = normalizeTitle(rule.cardName).split(" ").filter(Boolean);
  if (!containsTokenSequence(titleTokens, nameTokens)) {
    return { matched: false, reason: "card name absent from title" };
  }
  if (rule.cardNumber) {
    const wanted = normalizeTitle(rule.cardNumber).split(" ").filter(Boolean);
    const compactNumber = normalizeTitle(rule.cardNumber).replace(/\s+/g, "");
    const numberFound = containsTokenSequence(titleTokens, wanted)
      || titleTokens.some((token) => token === compactNumber)
      || titleTokens.some((token) => token.startsWith(`${compactNumber}/`));
    if (!numberFound) {
      return { matched: false, reason: "card number absent from title" };
    }
  }
  return {
    matched: true,
    reason: rule.cardNumber ? "card name and number matched" : "card name matched",
  };
}

export function isListingNewSince(previousViewValue, itemCreationDate, itemOriginDate = "") {
  const previousViewAt = Date.parse(String(previousViewValue || ""));
  const listedAt = Date.parse(String(itemCreationDate || itemOriginDate || ""));
  return Number.isFinite(previousViewAt) && Number.isFinite(listedAt) && listedAt > previousViewAt;
}
