CREATE TABLE IF NOT EXISTS settings_name_match_v2 (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules_name_match_v2 (
  id TEXT PRIMARY KEY,
  search_name TEXT NOT NULL,
  query_keywords TEXT NOT NULL,
  card_name TEXT NOT NULL,
  card_number TEXT,
  target_gbp REAL,
  enabled INTEGER NOT NULL DEFAULT 1,
  synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_items_name_match_v2 (
  item_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  title TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  matched INTEGER NOT NULL,
  match_reason TEXT NOT NULL,
  watch_status TEXT NOT NULL,
  PRIMARY KEY (item_id, rule_id)
);

CREATE TABLE IF NOT EXISTS matches_name_match_v2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  search_name TEXT NOT NULL,
  title TEXT NOT NULL,
  item_url TEXT,
  image_url TEXT,
  price_gbp REAL,
  delivery_gbp REAL,
  total_gbp REAL,
  target_gbp REAL,
  watch_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(item_id, rule_id)
);

CREATE TABLE IF NOT EXISTS scans_name_match_v2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  searched INTEGER NOT NULL DEFAULT 0,
  matches INTEGER NOT NULL DEFAULT 0,
  watchlisted INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_name_match_v2_created_at ON matches_name_match_v2(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_seen_name_match_v2_rule ON seen_items_name_match_v2(rule_id);
