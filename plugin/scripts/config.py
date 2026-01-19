"""
Overlap plugin configuration.

This module loads configuration from:
1. Environment variables (OVERLAP_*)
2. Config file (~/.claude/overlap/config.json)

Claude Code recommends storing persistent state in ~/.claude/ for user-level data.
"""

import json
import os
from pathlib import Path
from typing import Optional

# Import logger - but handle case where it fails (avoid circular issues)
try:
    import logger as _logger
except ImportError:
    _logger = None  # type: ignore

# Store in ~/.claude/overlap/ as recommended by Claude Code docs
CONFIG_DIR = Path.home() / ".claude" / "overlap"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_FILE = CONFIG_DIR / "session.json"


def get_config() -> dict:
    """Load configuration from file and environment."""
    config = {
        "server_url": None,
        "team_token": None,
        "user_token": None,
    }

    # Load from config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                file_config = json.load(f)
                config.update(file_config)
        except json.JSONDecodeError as e:
            if _logger:
                _logger.warn("Config file has invalid JSON", path=str(CONFIG_FILE), error=str(e))
        except IOError as e:
            if _logger:
                _logger.warn("Failed to read config file", path=str(CONFIG_FILE), error=str(e))

    # Override with environment variables
    if os.environ.get("OVERLAP_SERVER_URL"):
        config["server_url"] = os.environ["OVERLAP_SERVER_URL"]
    if os.environ.get("OVERLAP_TEAM_TOKEN"):
        config["team_token"] = os.environ["OVERLAP_TEAM_TOKEN"]
    if os.environ.get("OVERLAP_USER_TOKEN"):
        config["user_token"] = os.environ["OVERLAP_USER_TOKEN"]

    return config


def save_config(config: dict) -> None:
    """Save configuration to file."""
    import sys
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        if _logger:
            _logger.info("Config saved", path=str(CONFIG_FILE))
        print(f"[Overlap] Config: Saved config to {CONFIG_FILE}", file=sys.stderr)
    except Exception as e:
        if _logger:
            _logger.error("Failed to save config", exc=e, path=str(CONFIG_FILE))
        print(f"[Overlap] Config: FAILED to save config: {e}", file=sys.stderr)
        raise


def get_current_session() -> Optional[str]:
    """Get the current session ID if one is active."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                data = json.load(f)
                return data.get("session_id")
        except json.JSONDecodeError as e:
            if _logger:
                _logger.warn("Session file has invalid JSON", path=str(SESSION_FILE), error=str(e))
        except IOError as e:
            if _logger:
                _logger.warn("Failed to read session file", path=str(SESSION_FILE), error=str(e))
    return None


def save_current_session(session_id: str) -> None:
    """Save the current session ID."""
    import sys
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w") as f:
            json.dump({"session_id": session_id}, f)
        if _logger:
            _logger.info("Session saved", session_id=session_id, path=str(SESSION_FILE))
        print(f"[Overlap] Config: Successfully wrote session file to {SESSION_FILE}", file=sys.stderr)
    except Exception as e:
        if _logger:
            _logger.error("Failed to save session", exc=e, session_id=session_id)
        print(f"[Overlap] Config: FAILED to write session file: {e}", file=sys.stderr)
        raise


def clear_current_session() -> None:
    """Clear the current session."""
    if SESSION_FILE.exists():
        try:
            SESSION_FILE.unlink()
            if _logger:
                _logger.info("Session cleared", path=str(SESSION_FILE))
        except OSError as e:
            if _logger:
                _logger.warn("Failed to clear session file", path=str(SESSION_FILE), error=str(e))


def is_configured() -> bool:
    """Check if the plugin is properly configured."""
    config = get_config()
    return all([
        config.get("server_url"),
        config.get("team_token"),
        config.get("user_token"),
    ])
