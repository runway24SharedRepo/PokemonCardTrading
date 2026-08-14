import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync(new URL("../src/worker.js", import.meta.url), "utf8");
assert.doesNotMatch(source, /total\s*<=\s*target/i);
assert.doesNotMatch(source, /price\s*<=\s*target/i);
assert.doesNotMatch(source, /delivery\s*<=\s*target/i);
assert.match(source, /titleMatchesRule/);
assert.match(source, /AddToWatchList/);
assert.match(source, /sort", "newlyListed"/);
assert.match(source, /env\.EBAY_AUTH_TOKEN/);
assert.match(source, /<RequesterCredentials><eBayAuthToken>/);
console.log("all-price policy tests passed");
