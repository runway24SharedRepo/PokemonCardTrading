import assert from "node:assert/strict";
import { parseRule, titleMatchesRule } from "../src/matcher.js";

const pikachu = parseRule("Pikachu 58 - target £12.50", "Pikachu Base 58 Pokemon card");
assert.equal(pikachu.cardName, "Pikachu");
assert.equal(pikachu.cardNumber, "58");
assert.equal(pikachu.targetGbp, 12.5);
assert.equal(titleMatchesRule("Pokemon Base Set Pikachu 58/102 NM", pikachu).matched, true);
assert.equal(titleMatchesRule("Pokemon Pikachu 58 Base Set overpriced", pikachu).matched, true);
assert.equal(titleMatchesRule("Pokemon Pikachu 158 card", pikachu).matched, false);
assert.equal(titleMatchesRule("Pokemon Raichu 58 card", pikachu).matched, false);

const mime = parseRule("Mr Mime 6 - target £20", "Mr Mime Jungle 6");
assert.equal(titleMatchesRule("Mr. Mime 6/64 Jungle Holo Pokemon", mime).matched, true);

const promo = parseRule("Mudkip XY38 - target £8", "Mudkip XY38");
assert.equal(titleMatchesRule("Pokemon Mudkip XY38 Black Star Promo", promo).matched, true);
assert.equal(titleMatchesRule("Pokemon Mudkip XY39 Black Star Promo", promo).matched, false);

assert.throws(() => parseRule("Unrelated saved search", "anything"), /not target-labelled/);

console.log("matcher tests passed");
