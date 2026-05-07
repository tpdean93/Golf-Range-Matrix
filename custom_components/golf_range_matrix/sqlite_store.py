"""SQLite-backed storage for Golf Range Matrix."""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .const import DEFAULT_CATALOG, DEFAULT_SHOTS_PER_CLUB, METRIC_FIELDS, TEXT_FIELDS


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def topic_segment(value: str) -> str:
    """Return a stable lowercase segment for topics/keys."""
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(part for part in safe.split("_") if part) or "unknown"


def to_float(value: Any) -> float | None:
    """Coerce a value into a float when possible."""
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "unavailable", "none", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pick(payload: dict[str, Any], aliases: Iterable[str]) -> Any:
    """Pick a value from a raw shot payload, including nested metrics."""
    for alias in aliases:
        if alias in payload:
            return payload[alias]
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        for alias in aliases:
            if alias in metrics:
                return metrics[alias]
    return None


def rounded(value: float | int | None, digits: int = 1) -> float | None:
    """Round a number for dashboard-friendly payloads."""
    return None if value is None else round(float(value), digits)


def percentile(values: list[float], pct: float) -> float | None:
    """Return an interpolated percentile."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def avg(values: list[float]) -> float | None:
    """Return the mean value."""
    return sum(values) / len(values) if values else None


def stdev(values: list[float]) -> float | None:
    """Return population standard deviation."""
    return statistics.pstdev(values) if len(values) > 1 else None


def compact_range(low: float | None, high: float | None, digits: int = 1) -> dict[str, float | None]:
    """Return a compact low/high range."""
    return {"low": rounded(low, digits), "high": rounded(high, digits)}


def confidence_range(values: list[float]) -> dict[str, Any]:
    """Build common confidence windows for a metric."""
    return {
        "p10_p90": compact_range(percentile(values, 0.10), percentile(values, 0.90)),
        "p25_p75": compact_range(percentile(values, 0.25), percentile(values, 0.75)),
        "min_max": compact_range(min(values) if values else None, max(values) if values else None),
        "standard_deviation": rounded(stdev(values)),
    }


def offline_label(avg_offline: float | None) -> str:
    """Describe lateral miss tendency."""
    if avg_offline is None:
        return "unknown"
    if avg_offline <= -7:
        return "left miss"
    if avg_offline >= 7:
        return "right miss"
    if avg_offline < -2:
        return "slight left tendency"
    if avg_offline > 2:
        return "slight right tendency"
    return "centered"


def dispersion_label(offline_values: list[float]) -> str:
    """Describe dispersion shape."""
    if not offline_values:
        return "unknown"
    left_rate = sum(1 for value in offline_values if value < -5) / len(offline_values)
    right_rate = sum(1 for value in offline_values if value > 5) / len(offline_values)
    spread = (percentile(offline_values, 0.90) or 0) - (percentile(offline_values, 0.10) or 0)
    if left_rate >= 0.45 and right_rate >= 0.25:
        return "two-way miss, left leaning"
    if right_rate >= 0.45 and left_rate >= 0.25:
        return "two-way miss, right leaning"
    if left_rate >= 0.45:
        return "left miss pattern"
    if right_rate >= 0.45:
        return "right miss pattern"
    if spread <= 12:
        return "tight dispersion"
    if spread >= 30:
        return "wide dispersion"
    return "balanced dispersion"


def reliability_label(shot_count: int, carry_values: list[float]) -> str:
    """Return a confidence rating for a club sample."""
    carry_sd = stdev(carry_values)
    if shot_count < 5:
        return "low sample"
    if carry_sd is None:
        return "building"
    if shot_count >= 10 and carry_sd <= 5:
        return "high"
    if carry_sd <= 9:
        return "medium"
    return "low"


class NovaGolfStore:
    """Own all durable app and shot data for the integration."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create or migrate the SQLite schema."""
        with self._connect() as db:
            db.executescript(
                """
                create table if not exists app_state (
                  key text primary key,
                  value_json text not null,
                  updated_at text not null
                );

                create table if not exists players (
                  name text primary key,
                  created_at text not null,
                  updated_at text not null
                );

                create table if not exists player_bags (
                  player text primary key,
                  clubs_json text not null,
                  updated_at text not null
                );

                create table if not exists club_metadata (
                  player text not null,
                  club text not null,
                  metadata_json text not null,
                  updated_at text not null,
                  primary key(player, club)
                );

                create table if not exists wedge_matrices (
                  player text primary key,
                  matrix_json text not null,
                  updated_at text not null
                );

                create table if not exists shots (
                  id text primary key,
                  received_at text not null,
                  session_id text,
                  player text not null,
                  club text not null,
                  recording integer not null default 0,
                  bag_test_active integer not null default 0,
                  bag_test_index integer,
                  bag_test_shot_count integer,
                  shots_per_club integer,
                  carry real,
                  total real,
                  offline real,
                  ball_speed real,
                  club_speed real,
                  smash_factor real,
                  launch_angle real,
                  launch_direction real,
                  total_spin real,
                  spin_axis real,
                  backspin real,
                  sidespin real,
                  peak_height real,
                  hang_time real,
                  descent_angle real,
                  shot_name text,
                  shot_rank text,
                  discarded integer not null default 0,
                  discarded_at text,
                  raw_json text not null,
                  context_json text not null
                );

                create index if not exists idx_range_matrix_shots_player_club
                  on shots(player, club, discarded, received_at);
                create index if not exists idx_range_matrix_shots_session
                  on shots(session_id, discarded, received_at);
                """
            )
            now = utc_now()
            existing = db.execute("select count(*) as count from players").fetchone()["count"]
            if existing == 0:
                db.execute("insert into players(name, created_at, updated_at) values(?, ?, ?)", ("Tyler", now, now))
                db.execute(
                    "insert into player_bags(player, clubs_json, updated_at) values(?, ?, ?)",
                    ("Tyler", json.dumps(DEFAULT_CATALOG[:14], separators=(",", ":")), now),
                )
                self._set_state_db(db, "active_player", "Tyler")
                self._set_state_db(db, "active_club", "Driver")
                self._set_state_db(db, "recording", False)
                self._set_state_db(db, "session_mode", "Casual")
                self._set_state_db(db, "shots_per_club", DEFAULT_SHOTS_PER_CLUB)

    def _set_state_db(self, db: sqlite3.Connection, key: str, value: Any) -> None:
        db.execute(
            """
            insert into app_state(key, value_json, updated_at)
            values(?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json,
              updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, separators=(",", ":")), utc_now()),
        )

    def set_state(self, key: str, value: Any) -> None:
        """Persist a small app state value."""
        with self._connect() as db:
            self._set_state_db(db, key, value)

    def state_value(self, key: str, default: Any = None) -> Any:
        """Read a small app state value."""
        with self._connect() as db:
            row = db.execute("select value_json from app_state where key = ?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value_json"])
        except json.JSONDecodeError:
            return default

    def snapshot(self) -> dict[str, Any]:
        """Build a complete dashboard/entity snapshot."""
        with self._connect() as db:
            players = [row["name"] for row in db.execute("select name from players order by name").fetchall()]
            bags = {
                row["player"]: json.loads(row["clubs_json"])
                for row in db.execute("select player, clubs_json from player_bags").fetchall()
            }
            matrices = {
                row["player"]: json.loads(row["matrix_json"])
                for row in db.execute("select player, matrix_json from wedge_matrices").fetchall()
            }
            metadata: dict[str, dict[str, Any]] = {}
            for row in db.execute("select player, club, metadata_json from club_metadata").fetchall():
                metadata.setdefault(row["player"], {})[row["club"]] = json.loads(row["metadata_json"])
            app_state = {
                row["key"]: json.loads(row["value_json"])
                for row in db.execute("select key, value_json from app_state").fetchall()
            }
            latest = db.execute(
                "select * from shots where discarded = 0 order by received_at desc limit 1"
            ).fetchone()

        active_player = str(app_state.get("active_player") or (players[0] if players else "Tyler"))
        active_club = str(app_state.get("active_club") or ((bags.get(active_player) or ["Driver"])[0]))
        metrics = dict(latest) if latest else {}
        bag_summary = self.build_bag_summary(active_player)
        bag_summary["metadata"] = metadata.get(active_player, {})
        bag_summary["bag"] = bags.get(active_player, [])
        bag_summary["wedge_matrix"] = matrices.get(active_player, {})
        return {
            "players": players,
            "bags": bags,
            "matrices": matrices,
            "metadata": metadata,
            "active_player": active_player,
            "active_club": active_club,
            "recording": bool(app_state.get("recording", False)),
            "session_mode": app_state.get("session_mode", "Casual"),
            "session_id": app_state.get("session_id"),
            "bag_test_active": bool(app_state.get("bag_test_active", False)),
            "bag_test_index": int(app_state.get("bag_test_index", 0) or 0),
            "bag_test_shot_count": int(app_state.get("bag_test_shot_count", 0) or 0),
            "shots_per_club": int(app_state.get("shots_per_club", DEFAULT_SHOTS_PER_CLUB) or DEFAULT_SHOTS_PER_CLUB),
            "latest_shot": metrics,
            "metrics": metrics,
            "bag_summary": bag_summary,
        }

    def save_profiles(self, players: list[str]) -> None:
        """Persist the profile list without reintroducing sample profiles."""
        cleaned = [name.strip() for name in players if str(name).strip()]
        now = utc_now()
        with self._connect() as db:
            db.execute("delete from players")
            for name in cleaned:
                db.execute(
                    "insert into players(name, created_at, updated_at) values(?, ?, ?)",
                    (name, now, now),
                )
            active = self.state_value("active_player", cleaned[0] if cleaned else "Tyler")
            if active not in cleaned and cleaned:
                self._set_state_db(db, "active_player", cleaned[0])

    def save_bag(self, player: str, clubs: list[str]) -> None:
        """Persist a player bag."""
        cleaned = [club.strip() for club in clubs if str(club).strip()][:14]
        with self._connect() as db:
            db.execute(
                """
                insert into player_bags(player, clubs_json, updated_at)
                values(?, ?, ?)
                on conflict(player) do update set clubs_json = excluded.clubs_json,
                  updated_at = excluded.updated_at
                """,
                (player, json.dumps(cleaned, separators=(",", ":")), utc_now()),
            )
            active_club = self.state_value("active_club")
            if cleaned and active_club not in cleaned:
                self._set_state_db(db, "active_club", cleaned[0])

    def save_club_metadata(self, player: str, club: str, metadata: dict[str, Any]) -> None:
        """Persist editable club metadata."""
        allowed = {
            "brand": str(metadata.get("brand") or ""),
            "model": str(metadata.get("model") or ""),
            "image_url": str(metadata.get("image_url") or metadata.get("imageUrl") or ""),
        }
        with self._connect() as db:
            db.execute(
                """
                insert into club_metadata(player, club, metadata_json, updated_at)
                values(?, ?, ?, ?)
                on conflict(player, club) do update set metadata_json = excluded.metadata_json,
                  updated_at = excluded.updated_at
                """,
                (player, club, json.dumps(allowed, separators=(",", ":")), utc_now()),
            )

    def save_wedge_matrix(self, player: str, matrix: dict[str, Any]) -> None:
        """Persist a player's wedge matrix."""
        with self._connect() as db:
            db.execute(
                """
                insert into wedge_matrices(player, matrix_json, updated_at)
                values(?, ?, ?)
                on conflict(player) do update set matrix_json = excluded.matrix_json,
                  updated_at = excluded.updated_at
                """,
                (player, json.dumps(matrix, separators=(",", ":")), utc_now()),
            )

    def record_shot(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Persist a shot from MQTT and return the inserted row."""
        active_player = str(context.get("player") or context.get("active_player") or "Tyler")
        active_club = str(context.get("club") or context.get("active_club") or "Driver")
        row: dict[str, Any] = {
            "id": str(payload.get("id") or payload.get("shot_id") or uuid.uuid4()),
            "received_at": str(payload.get("timestamp") or payload.get("received_at") or utc_now()),
            "session_id": context.get("session_id"),
            "player": active_player,
            "club": active_club,
            "recording": 1 if context.get("recording") else 0,
            "bag_test_active": 1 if context.get("bag_test_active") else 0,
            "bag_test_index": context.get("bag_test_index"),
            "bag_test_shot_count": context.get("bag_test_shot_count"),
            "shots_per_club": context.get("shots_per_club"),
            "raw_json": json.dumps(payload, separators=(",", ":")),
            "context_json": json.dumps(context, separators=(",", ":")),
        }
        for field, info in METRIC_FIELDS.items():
            row[field] = to_float(pick(payload, info["aliases"]))
        for field, info in TEXT_FIELDS.items():
            value = pick(payload, info["aliases"])
            row[field] = None if value is None else str(value)

        with self._connect() as db:
            columns = ",".join(row.keys())
            placeholders = ",".join("?" for _ in row)
            db.execute(f"insert or replace into shots({columns}) values({placeholders})", tuple(row.values()))
        return row

    def discard_last_shot(self, player: str | None = None, session_id: str | None = None) -> dict[str, Any] | None:
        """Discard the most recent matching shot."""
        params: list[Any] = []
        where = ["discarded = 0"]
        if player:
            where.append("player = ?")
            params.append(player)
        if session_id:
            where.append("session_id = ?")
            params.append(session_id)
        with self._connect() as db:
            row = db.execute(
                f"select * from shots where {' and '.join(where)} order by received_at desc limit 1",
                params,
            ).fetchone()
            if not row:
                return None
            db.execute("update shots set discarded = 1, discarded_at = ? where id = ?", (utc_now(), row["id"]))
            return dict(row)

    def session_club_count(self, session_id: str | None, player: str, club: str) -> int:
        """Return valid shot count for the active workflow session and club."""
        if not session_id:
            return 0
        with self._connect() as db:
            row = db.execute(
                """
                select count(*) as shot_count
                from shots
                where discarded = 0 and session_id = ? and player = ? and club = ?
                """,
                (session_id, player, club),
            ).fetchone()
        return int(row["shot_count"] or 0)

    def club_rows(self, player: str, club: str) -> list[sqlite3.Row]:
        """Return valid shots for a player/club."""
        with self._connect() as db:
            return db.execute(
                """
                select *
                from shots
                where discarded = 0 and player = ? and club = ?
                order by received_at
                """,
                (player, club),
            ).fetchall()

    def player_clubs(self, player: str) -> list[str]:
        """Return clubs with saved shots for a player."""
        with self._connect() as db:
            rows = db.execute(
                """
                select club, min(received_at) as first_seen
                from shots
                where discarded = 0 and player = ? and club is not null and club != ''
                group by club
                order by first_seen
                """,
                (player,),
            ).fetchall()
        return [str(row["club"]) for row in rows]

    def build_club_summary(self, player: str, club: str) -> dict[str, Any]:
        """Build the analytics payload for one club."""
        rows = self.club_rows(player, club)
        numeric = {
            field: [float(row[field]) for row in rows if row[field] is not None]
            for field in METRIC_FIELDS
        }
        carry = numeric["carry"]
        total = numeric["total"]
        offline = numeric["offline"]
        avg_offline = avg(offline)
        shot_count = len(rows)
        reliability = reliability_label(shot_count, carry)
        playable_low = percentile(carry, 0.25)
        playable_high = percentile(carry, 0.75)
        tendency = {
            "direction": offline_label(avg_offline),
            "dispersion": dispersion_label(offline),
            "avg_offline": rounded(avg_offline),
            "left_rate": rounded(sum(1 for value in offline if value < -5) / len(offline), 2) if offline else None,
            "right_rate": rounded(sum(1 for value in offline if value > 5) / len(offline), 2) if offline else None,
            "center_rate": rounded(sum(1 for value in offline if -5 <= value <= 5) / len(offline), 2) if offline else None,
        }
        notes = []
        if carry:
            if playable_low is not None and playable_high is not None:
                notes.append(f"Typical carry {rounded(playable_low)}-{rounded(playable_high)} yd")
            else:
                notes.append(f"Average carry {rounded(avg(carry))} yd")
        notes.extend([tendency["dispersion"], tendency["direction"], f"{reliability} confidence"])
        return {
            "player": player,
            "club": club,
            "shot_count": shot_count,
            "last_shot_at": rows[-1]["received_at"] if rows else None,
            "averages": {
                "carry": rounded(avg(carry)),
                "total": rounded(avg(total)),
                "offline": rounded(avg_offline),
                "ball_speed": rounded(avg(numeric["ball_speed"])),
                "club_speed": rounded(avg(numeric["club_speed"])),
                "smash_factor": rounded(avg(numeric["smash_factor"]), 2),
                "launch_angle": rounded(avg(numeric["launch_angle"])),
                "launch_direction": rounded(avg(numeric["launch_direction"])),
                "total_spin": rounded(avg(numeric["total_spin"]), 0),
                "spin_axis": rounded(avg(numeric["spin_axis"])),
            },
            "confidence": {
                "rating": reliability,
                "carry": confidence_range(carry),
                "total": confidence_range(total),
                "offline": confidence_range(offline),
                "sample_size": shot_count,
            },
            "playable_yardage": {
                "carry": compact_range(playable_low, playable_high),
                "total": compact_range(percentile(total, 0.25), percentile(total, 0.75)),
            },
            "tendencies": tendency,
            "ai_notes": "; ".join(note for note in notes if note),
        }

    def build_bag_summary(self, player: str) -> dict[str, Any]:
        """Build the active player's bag summary."""
        bag = self.state_bag(player)
        shot_clubs = self.player_clubs(player)
        clubs = []
        for club in [*bag, *[club for club in shot_clubs if club not in bag]]:
            clubs.append(self.build_club_summary(player, club))
        return {
            "player": player,
            "club_count": len(clubs),
            "shot_count": sum(club["shot_count"] for club in clubs),
            "clubs": clubs,
            "updated_at": utc_now(),
        }

    def state_bag(self, player: str) -> list[str]:
        """Return a player's saved bag."""
        with self._connect() as db:
            row = db.execute("select clubs_json from player_bags where player = ?", (player,)).fetchone()
        if not row:
            return []
        try:
            return json.loads(row["clubs_json"])
        except json.JSONDecodeError:
            return []

    def export_backup(self) -> dict[str, Any]:
        """Export all app data and shot rows to JSON-serializable data."""
        snap = self.snapshot()
        with self._connect() as db:
            shots = [dict(row) for row in db.execute("select * from shots order by received_at").fetchall()]
        return {"schema": "golf-range-matrix-backup/v1", "exported_at": utc_now(), "snapshot": snap, "shots": shots}

    def import_backup(self, backup: dict[str, Any]) -> None:
        """Import a Range Matrix backup payload."""
        snapshot = backup.get("snapshot") or {}
        self.save_profiles(snapshot.get("players") or [])
        for player, clubs in (snapshot.get("bags") or {}).items():
            self.save_bag(player, clubs)
        for player, matrix in (snapshot.get("matrices") or {}).items():
            self.save_wedge_matrix(player, matrix)
        for player, clubs in (snapshot.get("metadata") or {}).items():
            for club, metadata in clubs.items():
                self.save_club_metadata(player, club, metadata)
        with self._connect() as db:
            for shot in backup.get("shots") or []:
                columns = ",".join(shot.keys())
                placeholders = ",".join("?" for _ in shot)
                db.execute(f"insert or replace into shots({columns}) values({placeholders})", tuple(shot.values()))
