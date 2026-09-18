"""
Campus Data Store — in-memory store for active dataset management.

Two modes per session:
  DEMO   – uses synthetic JSON files (default, preserves existing behaviour)
  USER   – uses campus data submitted via the API

Session isolation:
  Each browser session is identified by a cryptographically random session ID
  stored in an HttpOnly cookie ("gc_sid").  User campus data is keyed by that
  session ID so multiple browser tabs/clients do not share user datasets.

  The demo dataset is global / read-only and is never keyed by session.
  A single legacy global slot is kept for backward compatibility with tests
  that call set_user_campus_data / get_user_campus_data without a session ID.

No database required — state lives in-memory for this prototype.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

_MODE_DEMO = "demo"
_MODE_USER = "user"

SESSION_COOKIE = "gc_sid"
_SESSION_ID_BYTES = 24          # 192 bits — more than enough for prototype
_COOKIE_MAX_AGE  = 60 * 60 * 8  # 8 hours

# ── Per-session storage ───────────────────────────────────────────────────────
# { session_id: {"mode": "demo"|"user", "data": dict|None} }
_sessions: Dict[str, Dict[str, Any]] = {}

# ── Legacy global slot (used by tests that don't pass a session ID) ───────────
_active_mode: str = _MODE_DEMO
_user_campus_data: Optional[Dict[str, Any]] = None

# Persistence file — store global user data across restarts (legacy / single-user)
_PERSIST_FILE = Path(__file__).parent / "user_campus_data.json"


# ── Session helpers ───────────────────────────────────────────────────────────

def make_session_id() -> str:
    """Return a new cryptographically-random session ID (URL-safe base64)."""
    return secrets.token_urlsafe(_SESSION_ID_BYTES)


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, bool]:
    """
    Return (session_id, is_new).
    Creates a fresh demo-mode slot if the ID is unknown or None.
    """
    if session_id and session_id in _sessions:
        return session_id, False
    new_id = make_session_id()
    _sessions[new_id] = {"mode": _MODE_DEMO, "data": None}
    return new_id, True


# ── Session-scoped API ────────────────────────────────────────────────────────

def get_session_mode(session_id: str) -> str:
    slot = _sessions.get(session_id)
    if slot:
        return slot["mode"]
    return _MODE_DEMO


def get_session_data(session_id: str) -> Optional[Dict[str, Any]]:
    slot = _sessions.get(session_id)
    if slot and slot["mode"] == _MODE_USER:
        return slot["data"]
    return None


def set_session_data(session_id: str, data: Dict[str, Any]) -> None:
    """Activate user dataset for this session."""
    if session_id not in _sessions:
        _sessions[session_id] = {}
    _sessions[session_id]["mode"] = _MODE_USER
    _sessions[session_id]["data"] = data


def reset_session_to_demo(session_id: str) -> None:
    """Reset this session to demo mode, discarding user data."""
    _sessions[session_id] = {"mode": _MODE_DEMO, "data": None}


def is_session_user_mode(session_id: str) -> bool:
    return get_session_mode(session_id) == _MODE_USER


# ── Legacy global API (kept for backward-compatible tests) ───────────────────

def get_active_mode() -> str:
    """Return 'demo' or 'user' (uses global legacy slot)."""
    return _active_mode


def is_user_mode() -> bool:
    return _active_mode == _MODE_USER


def get_user_campus_data() -> Optional[Dict[str, Any]]:
    """Return the active user campus data dict (global legacy slot), or None."""
    if _active_mode == _MODE_USER:
        return _user_campus_data
    return None


def set_user_campus_data(data: Dict[str, Any]) -> None:
    """
    Activate user dataset (global legacy slot).
    Also persists to disk so data survives a server restart.
    """
    global _active_mode, _user_campus_data
    _user_campus_data = data
    _active_mode = _MODE_USER
    _persist_to_disk(data)


def reset_to_demo() -> None:
    """Discard user data and revert global legacy slot to demo dataset."""
    global _active_mode, _user_campus_data
    _active_mode = _MODE_DEMO
    _user_campus_data = None
    if _PERSIST_FILE.exists():
        try:
            _PERSIST_FILE.unlink()
        except OSError:
            pass


def clear_user_data() -> None:
    """Same as reset_to_demo — exposed separately for clarity."""
    reset_to_demo()


# ── Label / completeness helpers (accept optional session_id) ─────────────────

def get_data_source_label(session_id: Optional[str] = None) -> str:
    """Human-readable label for the active data source."""
    if session_id:
        if is_session_user_mode(session_id):
            data = get_session_data(session_id) or {}
        else:
            return "Demo Synthetic Data"
    else:
        if _active_mode != _MODE_USER:
            return "Demo Synthetic Data"
        data = _user_campus_data or {}

    campus_info = data.get("campus", {})
    name = campus_info.get("name", "")
    if name:
        return f"User Campus Data ({name})"
    return "User Campus Data"


def get_completeness_flags(
    data: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Check which analytics are available given the active dataset.
    Returns a dict of section → available.
    """
    if data is None:
        if session_id:
            data = get_session_data(session_id)
        else:
            data = _user_campus_data if _active_mode == _MODE_USER else None

    if data is None:
        # Demo mode — everything available
        return {
            "energy": True, "water": True, "waste": True,
            "co2": True, "ecosimopt": True, "monthly_energy": True,
            "monthly_water": True, "monthly_waste": True,
        }

    energy  = data.get("energy", {})
    water   = data.get("water", {})
    waste   = data.get("waste", {})

    has_energy = (energy.get("annual_kwh") or 0) > 0
    has_water  = (water.get("annual_m3") or 0) > 0
    has_waste  = (waste.get("annual_kg") or 0) > 0

    monthly_e   = energy.get("monthly_kwh") or []
    monthly_w   = water.get("monthly_m3") or []
    monthly_wst = waste.get("monthly_kg") or []

    return {
        "energy":         has_energy,
        "water":          has_water,
        "waste":          has_waste,
        "co2":            has_energy or has_water or has_waste,
        "ecosimopt":      has_energy or has_water or has_waste,
        "monthly_energy": bool(monthly_e) and len(monthly_e) == 12,
        "monthly_water":  bool(monthly_w) and len(monthly_w) == 12,
        "monthly_waste":  bool(monthly_wst) and len(monthly_wst) == 12,
    }


# ── Derived metrics helpers ───────────────────────────────────────────────────

def derive_energy_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build an energy data structure from user campus data.
    If monthly values are provided, compute annual from them.
    If only annual is provided, keep it and mark monthly as unavailable.
    """
    energy  = data.get("energy", {})
    monthly = energy.get("monthly_kwh") or []
    annual  = energy.get("annual_kwh") or 0

    if monthly and len(monthly) == 12:
        annual_from_monthly = sum(monthly)
        return {
            "unit": "kWh",
            "year": 2024,
            "note": "User-provided campus data",
            "annual_kwh": annual_from_monthly,
            "monthly_kwh": monthly,
            "has_monthly": True,
            "buildings": [],
            "campus_name": data.get("campus", {}).get("name", "Campus"),
        }
    return {
        "unit": "kWh",
        "year": 2024,
        "note": "User-provided campus data (annual only — monthly breakdown unavailable)",
        "annual_kwh": annual,
        "monthly_kwh": [],
        "has_monthly": False,
        "buildings": [],
        "campus_name": data.get("campus", {}).get("name", "Campus"),
    }


def derive_water_data(data: Dict[str, Any]) -> Dict[str, Any]:
    water   = data.get("water", {})
    monthly = water.get("monthly_m3") or []
    annual  = water.get("annual_m3") or 0

    if monthly and len(monthly) == 12:
        annual_from_monthly = sum(monthly)
        return {
            "unit": "m3",
            "year": 2024,
            "note": "User-provided campus data",
            "annual_m3": annual_from_monthly,
            "monthly_m3": monthly,
            "has_monthly": True,
            "buildings": [],
            "campus_name": data.get("campus", {}).get("name", "Campus"),
        }
    return {
        "unit": "m3",
        "year": 2024,
        "note": "User-provided campus data (annual only — monthly breakdown unavailable)",
        "annual_m3": annual,
        "monthly_m3": [],
        "has_monthly": False,
        "buildings": [],
        "campus_name": data.get("campus", {}).get("name", "Campus"),
    }


def derive_waste_data(data: Dict[str, Any]) -> Dict[str, Any]:
    waste       = data.get("waste", {})
    annual_kg   = waste.get("annual_kg") or 0
    recycled_pct  = waste.get("recycled_pct") or 0
    composted_pct = waste.get("composted_pct") or 0
    landfill_pct  = waste.get("landfill_pct") or 0
    monthly_kg    = waste.get("monthly_kg") or []

    if monthly_kg and len(monthly_kg) == 12:
        annual_kg = sum(monthly_kg)

    return {
        "unit": "kg",
        "year": 2024,
        "note": "User-provided campus data",
        "annual_kg": annual_kg,
        "recycled_pct":  recycled_pct,
        "composted_pct": composted_pct,
        "landfill_pct":  landfill_pct,
        "monthly_kg": monthly_kg,
        "has_monthly": bool(monthly_kg) and len(monthly_kg) == 12,
        "campus_name": data.get("campus", {}).get("name", "Campus"),
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def _persist_to_disk(data: Dict[str, Any]) -> None:
    try:
        with open(_PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass  # Non-fatal — in-memory state is the source of truth


def load_persisted_data() -> None:
    """Called on startup — reload persisted user data if it exists (legacy global slot)."""
    global _active_mode, _user_campus_data
    if _PERSIST_FILE.exists():
        try:
            with open(_PERSIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _user_campus_data = data
            _active_mode = _MODE_USER
        except (OSError, json.JSONDecodeError):
            pass  # Ignore corrupt or missing file
