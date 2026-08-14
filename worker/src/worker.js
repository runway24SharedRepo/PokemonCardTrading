import { isListingNewSince, parseRule, titleMatchesRule } from "./matcher.js";

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };
const XML_ENDPOINT = "https://api.ebay.com/ws/api.dll";
const TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token";
const BROWSE_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search";
const SCAN_LOCK_TTL_MS = 300_000;
let appTokenCache = null;
let userTokenCache = null;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}

function xmlEscape(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function xmlDecode(value) {
  return String(value || "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

function xmlValues(xml, tag) {
  const pattern = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tag}>`, "gi");
  return [...String(xml).matchAll(pattern)].map((match) => xmlDecode(match[1].trim()));
}

function requireDashboardAuth(request, env) {
  const expected = `Bearer ${env.POKEBID_API_KEY}`;
  return request.headers.get("authorization") === expected;
}

async function oauthToken(env, kind) {
  const cache = kind === "app" ? appTokenCache : userTokenCache;
  if (cache && Date.now() < cache.expiresAt - 60_000) return cache.value;
  const credentials = btoa(`${env.EBAY_CLIENT_ID}:${env.EBAY_CLIENT_SECRET}`);
  const body = new URLSearchParams();
  if (kind === "app") {
    body.set("grant_type", "client_credentials");
    body.set("scope", "https://api.ebay.com/oauth/api_scope");
  } else {
    body.set("grant_type", "refresh_token");
    body.set("refresh_token", env.EBAY_REFRESH_TOKEN);
  }
  const response = await fetch(TOKEN_ENDPOINT, {
    method: "POST",
    headers: {
      authorization: `Basic ${credentials}`,
      "content-type": "application/x-www-form-urlencoded",
    },
    body,
  });
  const data = await response.json();
  if (!response.ok || !data.access_token) {
    throw new Error(`eBay OAuth ${kind} token failed (${response.status}): ${JSON.stringify(data)}`);
  }
  const result = { value: data.access_token, expiresAt: Date.now() + Number(data.expires_in || 7200) * 1000 };
  if (kind === "app") appTokenCache = result;
  else userTokenCache = result;
  return result.value;
}

async function tradingCall(env, callName, innerXml) {
  const authnAuthToken = String(env.EBAY_AUTH_TOKEN || "").trim();
  const oauthAccessToken = authnAuthToken ? "" : await oauthToken(env, "user");
  const requesterCredentials = authnAuthToken
    ? `<RequesterCredentials><eBayAuthToken>${xmlEscape(authnAuthToken)}</eBayAuthToken></RequesterCredentials>`
    : "";
  const body = `<?xml version="1.0" encoding="utf-8"?>\n<${callName}Request xmlns="urn:ebay:apis:eBLBaseComponents">${requesterCredentials}${innerXml}</${callName}Request>`;
  const headers = {
    "content-type": "text/xml",
    "x-ebay-api-call-name": callName,
    "x-ebay-api-siteid": env.EBAY_SITE_ID || "3",
    "x-ebay-api-compatibility-level": "1455",
  };
  if (oauthAccessToken) headers["x-ebay-api-iaf-token"] = oauthAccessToken;
  const response = await fetch(XML_ENDPOINT, {
    method: "POST",
    headers,
    body,
  });
  const text = await response.text();
  const ack = xmlValues(text, "Ack")[0] || "Failure";
  if (!response.ok || !["Success", "Warning"].includes(ack)) {
    const errors = xmlValues(text, "LongMessage").join("; ") || `HTTP ${response.status}`;
    throw new Error(`${callName} failed: ${errors}`);
  }
  return text;
}

async function syncRules(env) {
  const xml = await tradingCall(env, "GetMyeBayBuying", "<DetailLevel>ReturnAll</DetailLevel><FavoriteSearches><Include>true</Include><MaxResults>200</MaxResults></FavoriteSearches>");
  const blocks = [...xml.matchAll(/<FavoriteSearch>([\s\S]*?)<\/FavoriteSearch>/gi)].map((match) => match[1]);
  const now = new Date().toISOString();
  const rules = [];
  for (const block of blocks) {
    const searchName = xmlValues(block, "SearchName")[0] || "";
    const queryKeywords = xmlValues(block, "QueryKeywords")[0] || "";
    if (!searchName.trim()) continue;
    try {
      const parsed = parseRule(searchName, queryKeywords);
      const id = await sha256(`${parsed.searchName}|${parsed.queryKeywords}|${parsed.cardName}|${parsed.cardNumber}`);
      const rule = { id, ...parsed };
      await env.DB.prepare(`INSERT INTO rules_name_match_v2 (id, search_name, query_keywords, card_name, card_number, target_gbp, enabled, synced_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?) ON CONFLICT(id) DO UPDATE SET search_name=excluded.search_name, query_keywords=excluded.query_keywords, card_name=excluded.card_name, card_number=excluded.card_number, target_gbp=excluded.target_gbp, enabled=1, synced_at=excluded.synced_at`)
        .bind(id, parsed.searchName, parsed.queryKeywords, parsed.cardName, parsed.cardNumber || null, parsed.targetGbp, now).run();
      rules.push(rule);
    } catch (_) {
      // Non-card saved searches are deliberately ignored.
    }
  }
  if (rules.length) {
    const ids = rules.map((rule) => `'${rule.id.replace(/'/g, "''")}'`).join(",");
    await env.DB.prepare(`UPDATE rules_name_match_v2 SET enabled=0 WHERE id NOT IN (${ids})`).run();
  } else {
    await env.DB.prepare("UPDATE rules_name_match_v2 SET enabled=0").run();
  }
  await putSetting(env, "last_rules_sync", now);
  return { eligibleRules: rules.length };
}

async function putSetting(env, key, value) {
  await env.DB.prepare("INSERT INTO settings_name_match_v2 (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at")
    .bind(key, String(value), new Date().toISOString()).run();
}

async function getSetting(env, key) {
  return (await env.DB.prepare("SELECT value FROM settings_name_match_v2 WHERE key=?").bind(key).first())?.value;
}

async function acquireScanLock(env) {
  const owner = crypto.randomUUID();
  const now = Date.now();
  const value = `${owner}|${now + SCAN_LOCK_TTL_MS}`;
  await env.DB.prepare("INSERT OR IGNORE INTO settings_name_match_v2 (key, value, updated_at) VALUES ('scan_lock', '0', ?)")
    .bind(new Date().toISOString()).run();
  const result = await env.DB.prepare("UPDATE settings_name_match_v2 SET value=?, updated_at=? WHERE key='scan_lock' AND (value='0' OR CAST(substr(value, instr(value, '|') + 1) AS INTEGER) < ?)")
    .bind(value, new Date().toISOString(), now).run();
  return result.meta.changes ? value : "";
}

async function releaseScanLock(env, lockValue) {
  await env.DB.prepare("UPDATE settings_name_match_v2 SET value='0', updated_at=? WHERE key='scan_lock' AND value=?")
    .bind(new Date().toISOString(), lockValue).run();
}

async function ensureRules(env) {
  const active = await env.DB.prepare("SELECT COUNT(*) AS count FROM rules_name_match_v2 WHERE enabled=1").first();
  const lastSync = Date.parse(await getSetting(env, "last_rules_sync") || "");
  if (!active?.count || !Number.isFinite(lastSync) || Date.now() - lastSync > 3_600_000) {
    await syncRules(env);
  }
}

async function selectRoundRobinRules(env, rules) {
  if (!rules.length) return [];
  const perCycle = Math.min(rules.length, Math.max(1, Number(env.SEARCHES_PER_CYCLE || 1)));
  const stored = Number(await getSetting(env, "round_robin_cursor") || 0);
  const cursor = Number.isFinite(stored) ? Math.abs(Math.trunc(stored)) % rules.length : 0;
  const selected = Array.from({ length: perCycle }, (_, offset) => rules[(cursor + offset) % rules.length]);
  await putSetting(env, "round_robin_cursor", (cursor + perCycle) % rules.length);
  await putSetting(env, "last_search_name", selected.map((rule) => rule.search_name).join(" | "));
  return selected;
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function legacyItemId(itemId) {
  const match = String(itemId || "").match(/^(?:v1\|)?(\d+)(?:\|\d+)?$/i);
  return match ? match[1] : "";
}

function money(item, key) {
  const value = Number(item?.[key]?.value || 0);
  return Number.isFinite(value) ? value : 0;
}

async function browseSearch(env, rule) {
  const token = await oauthToken(env, "app");
  const url = new URL(BROWSE_ENDPOINT);
  url.searchParams.set("q", rule.query_keywords || `${rule.card_name} ${rule.card_number || ""}`.trim());
  url.searchParams.set("limit", String(Math.min(200, Math.max(1, Number(env.MAX_RESULTS_PER_SEARCH || 50)))));
  url.searchParams.set("sort", "newlyListed");
  url.searchParams.set("filter", "deliveryCountry:GB,itemLocationCountry:GB");
  const response = await fetch(url, {
    headers: {
      authorization: `Bearer ${token}`,
      "x-ebay-c-marketplace-id": env.EBAY_MARKETPLACE_ID || "EBAY_GB",
      "x-ebay-c-enduserctx": "contextualLocation=country%3DGB",
    },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(`Browse search failed (${response.status}): ${JSON.stringify(data)}`);
  return data.itemSummaries || [];
}

async function addToWatchList(env, itemIds) {
  const unique = [...new Set(itemIds.map(legacyItemId).filter(Boolean))];
  if (!unique.length) return new Map();
  const result = new Map();
  for (const id of unique) {
    try {
      await tradingCall(env, "AddToWatchList", `<ItemID>${xmlEscape(id)}</ItemID>`);
      result.set(id, "added");
    } catch (error) {
      result.set(id, `failed: ${error.message}`);
    }
  }
  return result;
}

async function persistMatch(env, rule, item, itemId, watchStatus) {
  const delivery = money(item.shippingOptions?.[0], "shippingCost");
  const price = money(item, "price");
  await env.DB.batch([
    env.DB.prepare("UPDATE seen_items_name_match_v2 SET watch_status=? WHERE item_id=? AND rule_id=?").bind(watchStatus, itemId, rule.id),
    env.DB.prepare("INSERT OR IGNORE INTO matches_name_match_v2 (item_id, rule_id, search_name, title, item_url, image_url, price_gbp, delivery_gbp, total_gbp, target_gbp, watch_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
      .bind(itemId, rule.id, rule.search_name, item.title || "", item.itemWebUrl || "", item.image?.imageUrl || "", price, delivery, price + delivery, rule.target_gbp, watchStatus, new Date().toISOString()),
  ]);
}

async function scan(env) {
  const scanLock = await acquireScanLock(env);
  if (!scanLock) return { skipped: true, reason: "another scan is already running" };
  const startedAt = new Date().toISOString();
  let scanId = 0;
  let searched = 0;
  let matchCount = 0;
  let watchlisted = 0;
  let failed = 0;
  try {
    const scanInsert = await env.DB.prepare("INSERT INTO scans_name_match_v2 (started_at, status) VALUES (?, 'running')").bind(startedAt).run();
    scanId = scanInsert.meta.last_row_id;
    await ensureRules(env);
    const { results: rules } = await env.DB.prepare("SELECT * FROM rules_name_match_v2 WHERE enabled=1 ORDER BY search_name").all();
    const selectedRules = await selectRoundRobinRules(env, rules);
    const maxAdds = Math.min(10, Math.max(1, Number(env.MAX_WATCHLIST_ADDS_PER_SEARCH || 10)));
    const ruleErrors = [];
    const cycleModes = [];
    for (const rule of selectedRules) {
      try {
        const items = await browseSearch(env, rule);
        searched += items.length;
        const memoryKey = `search_memory_v3:${rule.id}`;
        const previousViewValue = await getSetting(env, memoryKey);
        const previousViewAt = Date.parse(previousViewValue || "");
        const memoryInitialized = Number.isFinite(previousViewAt);
        const mode = memoryInitialized ? "NEW-LISTINGS" : "BASELINE";
        cycleModes.push(mode);
        const pending = [];
        for (const item of items) {
          const itemId = legacyItemId(item.itemId);
          if (!itemId) continue;
          const seen = await env.DB.prepare("SELECT 1 FROM seen_items_name_match_v2 WHERE item_id=? AND rule_id=?").bind(itemId, rule.id).first();
          if (seen) continue;
          const decision = titleMatchesRule(item.title, { cardName: rule.card_name, cardNumber: rule.card_number || "" });
          const newSinceLastView = isListingNewSince(previousViewValue, item.itemCreationDate, item.itemOriginDate);
          let watchStatus = "ignored";
          if (!memoryInitialized) watchStatus = "baseline";
          else if (!newSinceLastView) watchStatus = "ignored: older than last view";
          else if (decision.matched && pending.length < maxAdds) watchStatus = "pending";
          else if (decision.matched) watchStatus = `skipped: per-search limit ${maxAdds}`;
          await env.DB.prepare("INSERT OR IGNORE INTO seen_items_name_match_v2 (item_id, rule_id, title, first_seen_at, matched, match_reason, watch_status) VALUES (?, ?, ?, ?, ?, ?, ?)")
            .bind(itemId, rule.id, item.title || "", new Date().toISOString(), decision.matched ? 1 : 0, decision.reason, watchStatus).run();
          if (newSinceLastView && decision.matched) {
            matchCount += 1;
            if (watchStatus === "pending") pending.push({ item, itemId });
            else await persistMatch(env, rule, item, itemId, watchStatus);
          }
        }
        const statuses = await addToWatchList(env, pending.map((entry) => entry.itemId));
        for (const { item, itemId } of pending) {
          const watchStatus = statuses.get(itemId) || "failed: no status";
          const added = watchStatus === "added";
          if (added) watchlisted += 1;
          else failed += 1;
          await persistMatch(env, rule, item, itemId, watchStatus);
        }
        await putSetting(env, memoryKey, startedAt);
      } catch (error) {
        ruleErrors.push(`${rule.search_name}: ${error.message}`);
      }
    }
    const finalStatus = ruleErrors.length ? `completed with errors: ${ruleErrors.join("; ").slice(0, 800)}` : "completed";
    const completedAt = new Date().toISOString();
    await env.DB.prepare("UPDATE scans_name_match_v2 SET completed_at=?, searched=?, matches=?, watchlisted=?, failed=?, status=? WHERE id=?")
      .bind(completedAt, searched, matchCount, watchlisted, failed, finalStatus, scanId).run();
    await putSetting(env, "last_completed_search", selectedRules.map((rule) => rule.search_name).join(" | "));
    await putSetting(env, "last_completed_at", completedAt);
    await putSetting(env, "last_completed_checked", searched);
    await putSetting(env, "last_completed_matches", matchCount);
    await putSetting(env, "last_completed_added", watchlisted);
    await putSetting(env, "last_completed_failed", failed);
    await putSetting(env, "last_completed_mode", cycleModes.join(" | "));
    return { scanId, searched, matches: matchCount, watchlisted, failed, mode: cycleModes, searches: selectedRules.map((rule) => rule.search_name), maxAddsPerSearch: maxAdds };
  } catch (error) {
    if (scanId) {
      await env.DB.prepare("UPDATE scans_name_match_v2 SET completed_at=?, searched=?, matches=?, watchlisted=?, failed=?, status=? WHERE id=?")
        .bind(new Date().toISOString(), searched, matchCount, watchlisted, failed + 1, `failed: ${error.message}`.slice(0, 800), scanId).run();
    }
    throw error;
  } finally {
    await releaseScanLock(env, scanLock);
  }
}

async function status(env) {
  const latestRun = await env.DB.prepare("SELECT * FROM scans_name_match_v2 ORDER BY id DESC LIMIT 1").first();
  const latestCompleted = await env.DB.prepare("SELECT * FROM scans_name_match_v2 WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 1").first();
  const active = await env.DB.prepare("SELECT COUNT(*) AS count FROM rules_name_match_v2 WHERE enabled=1").first();
  const totals = await env.DB.prepare("SELECT COUNT(*) AS total_matches, SUM(CASE WHEN watch_status='added' THEN 1 ELSE 0 END) AS watchlisted, SUM(CASE WHEN watch_status LIKE 'failed:%' THEN 1 ELSE 0 END) AS failed FROM matches_name_match_v2").first();
  const enabled = (await env.DB.prepare("SELECT value FROM settings_name_match_v2 WHERE key='enabled'").first())?.value !== "false";
  const lastSearch = await getSetting(env, "last_search_name") || "not scanned yet";
  const lastSearchResult = {
    search_name: await getSetting(env, "last_completed_search") || "not completed yet",
    completed_at: await getSetting(env, "last_completed_at") || latestCompleted?.completed_at || null,
    checked: Number(await getSetting(env, "last_completed_checked") || latestCompleted?.searched || 0),
    matches: Number(await getSetting(env, "last_completed_matches") || latestCompleted?.matches || 0),
    added: Number(await getSetting(env, "last_completed_added") || latestCompleted?.watchlisted || 0),
    failed: Number(await getSetting(env, "last_completed_failed") || latestCompleted?.failed || 0),
    mode: await getSetting(env, "last_completed_mode") || "LEGACY",
  };
  return { enabled, active_rules: active?.count || 0, total_matches: totals?.total_matches || 0, watchlisted: totals?.watchlisted || 0, failed: totals?.failed || 0, latest: latestCompleted || latestRun, current_scan: latestRun && !latestRun.completed_at ? { id: latestRun.id, started_at: latestRun.started_at, search_name: lastSearch } : null, last_search: lastSearch, last_search_result: lastSearchResult, searches_per_cycle: Math.max(1, Number(env.SEARCHES_PER_CYCLE || 1)), max_adds_per_search: Math.min(10, Math.max(1, Number(env.MAX_WATCHLIST_ADDS_PER_SEARCH || 10))), matching_policy: "per-search-memory-v3; name-and-number; all prices; UK-located; round-robin; max-10", ebay_user_auth: env.EBAY_AUTH_TOKEN ? "authn-auth" : "oauth-refresh" };
}

async function route(request, env, ctx) {
  const url = new URL(request.url);
  if (url.pathname === "/health") return json({ ok: true, policy: "per-search-memory-v3; name-and-number; all prices; UK-located; round-robin; max-10" });
  if (!requireDashboardAuth(request, env)) return json({ error: "Unauthorized" }, 401);
  if (request.method === "GET" && url.pathname === "/api/status") return json(await status(env));
  if (request.method === "GET" && url.pathname === "/api/matches") {
    const limit = Math.min(500, Math.max(1, Number(url.searchParams.get("limit") || 150)));
    const { results } = await env.DB.prepare("SELECT * FROM matches_name_match_v2 ORDER BY id DESC LIMIT ?").bind(limit).all();
    return json({ matches: results });
  }
  if (request.method === "POST" && url.pathname === "/api/rules/sync") return json(await syncRules(env));
  if (request.method === "POST" && url.pathname === "/api/automation") {
    const body = await request.json().catch(() => ({}));
    const enabled = body.enabled !== false;
    await env.DB.prepare("INSERT INTO settings_name_match_v2 (key, value, updated_at) VALUES ('enabled', ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at")
      .bind(String(enabled), new Date().toISOString()).run();
    return json({ enabled });
  }
  if (request.method === "POST" && url.pathname === "/api/scan") {
    ctx.waitUntil(scan(env));
    return json({ queued: true, policy: "per-search-memory-v3; name-and-number; all prices; UK-located; round-robin; max-10" }, 202);
  }
  return json({ error: "Not found" }, 404);
}

export default {
  fetch(request, env, ctx) {
    return route(request, env, ctx).catch((error) => json({ error: error.message }, 500));
  },
  async scheduled(_controller, env, ctx) {
    const enabled = (await env.DB.prepare("SELECT value FROM settings_name_match_v2 WHERE key='enabled'").first())?.value !== "false";
    if (enabled) ctx.waitUntil(scan(env));
  },
};
