-- MySQL schema for LoadSuite user workflow persistence.
-- Applies to the cPanel MySQL database (e.g. orbiizny_loadsuite).

CREATE TABLE IF NOT EXISTS user_preferences (
  user_id VARCHAR(255) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS watchlist_items (
  id CHAR(36) NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  item_type VARCHAR(32) NOT NULL,
  load_id VARCHAR(255) NULL,
  lane VARCHAR(255) NULL,
  payload_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_watchlist_user (user_id),
  KEY idx_watchlist_load (user_id, item_type, load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alert_rules (
  id CHAR(36) NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_alert_rules_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS filter_presets (
  id CHAR(36) NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_filter_presets_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
