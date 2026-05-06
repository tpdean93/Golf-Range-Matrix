#!/usr/bin/env python3
"""Local MQTT-to-SQLite shot logger for NOVA/OpenGolfCoach data."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt


LOGGER = logging.getLogger("nova-shot-logger")

DEFAULT_CONTEXT_TOPIC = "golf/context/current"
DEFAULT_SHOT_TOPIC = "golf/shot/raw"
DEFAULT_DISCARD_TOPIC = "golf/context/discard_last_shot"
DEFAULT_SUMMARY_PREFIX = "golf/summary"
DEFAULT_EXPORT_PREFIX = "golf/export"

NUMERIC_FIELDS = {
    "carry": ("carry", "golf_carry", "carry_yards", "estimated_carry"),
    "total": ("total", "golf_total", "total_yards", "distance"),
    "offline": ("offline", "golf_offline", "offline_yards"),
    "ball_speed": ("ball_speed", "golf_ball_speed", "ballSpeed"),
    "club_speed": ("club_speed", "clubhead_speed", "golf_clubhead_speed", "clubSpeed"),
    "smash_factor": ("smash_factor", "golf_smash_factor", "smashFactor"),
    "launch_angle": ("launch_angle", "golf_launch_angle", "launchAngle"),
    "launch_direction": ("launch_direction", "golf_launch_direction", "launchDirection"),
    "total_spin": ("total_spin", "golf_total_spin", "totalSpin"),
    "spin_axis": ("spin_axis", "golf_spin_axis", "spinAxis"),
    "backspin": ("backspin", "golf_backspin", "backSpin"),
    "sidespin": ("sidespin", "golf_sidespin", "sideSpin"),
}

TEXT_FIELDS = {
    "shot_name": ("shot_name", "golf_shot_name", "shape", "shotShape"),
    "shot_rank": ("shot_rank", "golf_shot_rank", "grade", "rank"),
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on", "record", "recording"}


def to_int(value: Any) -> int | None:
    number = to_float(value)
    return None if number is None else int(number)


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "unavailable", "none", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pick(payload: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        for name in names:
            if name in metrics:
                return metrics[name]
    return None


def topic_segment(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(part for part in safe.split("_") if part) or "unknown"


def rounded(value: float | int | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def compact_range(low: float | None, high: float | None, digits: int = 1) -> dict[str, float | None]:
    return {"low": rounded(low, digits), "high": rounded(high, digits)}


def percentile(values: list[float], pct: float) -> float | None:
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


def numeric_values(rows: list[sqlite3.Row], field: str) -> list[float]:
    return [float(row[field]) for row in rows if row[field] is not None]


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stdev(values: list[float]) -> float | None:
    return statistics.pstdev(values) if len(values) > 1 else None


def confidence_range(values: list[float]) -> dict[str, Any]:
    return {
        "p10_p90": compact_range(percentile(values, 0.10), percentile(values, 0.90)),
        "p25_p75": compact_range(percentile(values, 0.25), percentile(values, 0.75)),
        "min_max": compact_range(min(values) if values else None, max(values) if values else None),
        "standard_deviation": rounded(stdev(values)),
    }


def offline_label(avg_offline: float | None) -> str:
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


class NovaShotLogger:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.context: dict[str, Any] = {}
        self.db_path = Path(args.db)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self._init_db()
        self.client = self._build_client()

    def _build_client(self) -> mqtt.Client:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.args.client_id)
        except AttributeError:
            client = mqtt.Client(client_id=self.args.client_id)

        if self.args.username:
            client.username_pw_set(self.args.username, self.args.password)

        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_disconnect = self.on_disconnect
        return client

    def _init_db(self) -> None:
        self.db.executescript(
            """
            create table if not exists latest_context (
              id integer primary key check (id = 1),
              updated_at text not null,
              payload_json text not null
            );

            create table if not exists shots (
              id text primary key,
              received_at text not null,
              session_id text,
              player text,
              club text,
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
              shot_name text,
              shot_rank text,
              discarded integer not null default 0,
              discarded_at text,
              raw_json text not null,
              context_json text not null
            );

            create index if not exists idx_shots_player_club
              on shots(player, club, discarded, received_at);
            create index if not exists idx_shots_session
              on shots(session_id, discarded, received_at);
            """
        )
        self.db.commit()

    def load_context(self) -> None:
        row = self.db.execute("select payload_json from latest_context where id = 1").fetchone()
        if not row:
            return
        try:
            self.context = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            LOGGER.warning("Ignoring invalid persisted context")

    def connect(self) -> None:
        self.load_context()
        LOGGER.info("Connecting to MQTT %s:%s", self.args.host, self.args.port)
        self.client.connect(self.args.host, self.args.port, keepalive=60)

    def on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        LOGGER.info("Connected to MQTT with result %s", reason_code)
        client.subscribe(
            [
                (self.args.context_topic, 1),
                (self.args.shot_topic, 1),
                (self.args.discard_topic, 1),
            ]
        )

    def on_disconnect(self, client: mqtt.Client, userdata: Any, reason_code: Any, properties: Any = None) -> None:
        LOGGER.warning("Disconnected from MQTT with result %s", reason_code)

    def on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            LOGGER.warning("Ignoring non-JSON payload on %s", message.topic)
            return

        if message.topic == self.args.context_topic:
            self.update_context(payload)
        elif message.topic == self.args.shot_topic:
            self.record_shot(payload)
        elif message.topic == self.args.discard_topic:
            self.discard_last_shot(payload)

    def update_context(self, payload: dict[str, Any]) -> None:
        self.context = payload
        self.db.execute(
            """
            insert into latest_context(id, updated_at, payload_json)
            values(1, ?, ?)
            on conflict(id) do update set updated_at = excluded.updated_at,
              payload_json = excluded.payload_json
            """,
            (utc_now(), json.dumps(payload, separators=(",", ":"))),
        )
        self.db.commit()
        LOGGER.info(
            "Context updated: player=%s club=%s recording=%s",
            payload.get("player"),
            payload.get("club"),
            payload.get("recording"),
        )

    def record_shot(self, payload: dict[str, Any]) -> None:
        context = dict(self.context)
        recording = parse_bool(context.get("recording"))
        if not recording and not self.args.store_unrecorded:
            LOGGER.info("Skipping shot because recording is off")
            return

        row: dict[str, Any] = {
            "id": str(payload.get("id") or payload.get("shot_id") or uuid.uuid4()),
            "received_at": str(payload.get("timestamp") or payload.get("received_at") or utc_now()),
            "session_id": context.get("session_id"),
            "player": str(context.get("player") or "Unknown"),
            "club": str(context.get("club") or "Unknown"),
            "recording": 1 if recording else 0,
            "bag_test_active": 1 if parse_bool(context.get("bag_test_active")) else 0,
            "bag_test_index": to_int(context.get("bag_test_index")),
            "bag_test_shot_count": to_int(context.get("bag_test_shot_count")),
            "shots_per_club": to_int(context.get("shots_per_club")),
            "raw_json": json.dumps(payload, separators=(",", ":")),
            "context_json": json.dumps(context, separators=(",", ":")),
        }

        for field, aliases in NUMERIC_FIELDS.items():
            row[field] = to_float(pick(payload, aliases))
        for field, aliases in TEXT_FIELDS.items():
            value = pick(payload, aliases)
            row[field] = None if value is None else str(value)

        columns = ",".join(row.keys())
        placeholders = ",".join("?" for _ in row)
        self.db.execute(f"insert or replace into shots({columns}) values({placeholders})", tuple(row.values()))
        self.db.commit()

        LOGGER.info("Recorded shot %s for %s / %s", row["id"], row["player"], row["club"])
        self.publish_summary(str(row["player"]), str(row["club"]))
        self.publish_player_exports(str(row["player"]))
        if row["session_id"]:
            self.publish_session_progress(str(row["session_id"]), str(row["player"]))

    def discard_last_shot(self, payload: dict[str, Any]) -> None:
        context = dict(self.context)
        player = str(payload.get("player") or context.get("player") or "")
        session_id = str(payload.get("session_id") or context.get("session_id") or "")
        params: list[Any] = []
        where = ["discarded = 0"]

        if session_id:
            where.append("session_id = ?")
            params.append(session_id)
        if player:
            where.append("player = ?")
            params.append(player)

        row = self.db.execute(
            f"select id, player, club, session_id from shots where {' and '.join(where)} order by received_at desc limit 1",
            params,
        ).fetchone()
        if not row:
            LOGGER.info("Discard requested but no matching shot was found")
            return

        self.db.execute("update shots set discarded = 1, discarded_at = ? where id = ?", (utc_now(), row["id"]))
        self.db.commit()
        LOGGER.info("Discarded shot %s", row["id"])
        self.publish_summary(row["player"], row["club"])
        self.publish_player_exports(row["player"])
        if row["session_id"]:
            self.publish_session_progress(row["session_id"], row["player"])

    def club_rows(self, player: str, club: str) -> list[sqlite3.Row]:
        return self.db.execute(
            """
            select *
            from shots
            where discarded = 0 and player = ? and club = ?
            order by received_at
            """,
            (player, club),
        ).fetchall()

    def player_clubs(self, player: str) -> list[str]:
        rows = self.db.execute(
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
        rows = self.club_rows(player, club)
        carry = numeric_values(rows, "carry")
        total = numeric_values(rows, "total")
        offline = numeric_values(rows, "offline")
        ball_speed = numeric_values(rows, "ball_speed")
        club_speed = numeric_values(rows, "club_speed")
        smash_factor = numeric_values(rows, "smash_factor")
        launch_angle = numeric_values(rows, "launch_angle")
        launch_direction = numeric_values(rows, "launch_direction")
        total_spin = numeric_values(rows, "total_spin")
        spin_axis = numeric_values(rows, "spin_axis")
        avg_offline = avg(offline)
        shot_count = len(rows)
        carry_window = confidence_range(carry)
        tendency = {
            "direction": offline_label(avg_offline),
            "dispersion": dispersion_label(offline),
            "avg_offline": rounded(avg_offline),
            "left_rate": rounded(sum(1 for value in offline if value < -5) / len(offline), 2) if offline else None,
            "right_rate": rounded(sum(1 for value in offline if value > 5) / len(offline), 2) if offline else None,
            "center_rate": rounded(sum(1 for value in offline if -5 <= value <= 5) / len(offline), 2) if offline else None,
        }
        playable_low = percentile(carry, 0.25)
        playable_high = percentile(carry, 0.75)
        reliability = reliability_label(shot_count, carry)
        notes = []
        if carry:
            notes.append(
                f"Typical carry {rounded(playable_low)}-{rounded(playable_high)} yd"
                if playable_low is not None and playable_high is not None
                else f"Average carry {rounded(avg(carry))} yd"
            )
        notes.append(tendency["dispersion"])
        notes.append(tendency["direction"])
        notes.append(f"{reliability} confidence")
        return {
            "player": player,
            "club": club,
            "shot_count": shot_count,
            "last_shot_at": rows[-1]["received_at"] if rows else None,
            "averages": {
                "carry": rounded(avg(carry)),
                "total": rounded(avg(total)),
                "offline": rounded(avg_offline),
                "ball_speed": rounded(avg(ball_speed)),
                "club_speed": rounded(avg(club_speed)),
                "smash_factor": rounded(avg(smash_factor), 2),
                "launch_angle": rounded(avg(launch_angle)),
                "launch_direction": rounded(avg(launch_direction)),
                "total_spin": rounded(avg(total_spin), 0),
                "spin_axis": rounded(avg(spin_axis)),
            },
            "confidence": {
                "rating": reliability,
                "carry": carry_window,
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

    def publish_summary(self, player: str, club: str) -> None:
        payload = self.build_club_summary(player, club)
        payload["updated_at"] = utc_now()
        topic = f"{self.args.summary_prefix}/{topic_segment(player)}/{topic_segment(club)}"
        self.client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=1, retain=True)

    def build_bag_summary(self, player: str) -> dict[str, Any]:
        clubs = [self.build_club_summary(player, club) for club in self.player_clubs(player)]
        return {
            "player": player,
            "club_count": len(clubs),
            "shot_count": sum(club["shot_count"] for club in clubs),
            "clubs": clubs,
            "updated_at": utc_now(),
        }

    def build_ai_export(self, player: str) -> dict[str, Any]:
        bag_summary = self.build_bag_summary(player)
        return {
            "schema": "nova-golf-ai-export/v1",
            "player": player,
            "generated_at": bag_summary["updated_at"],
            "purpose": "Use this profile to reason about realistic club selection, expected distances, dispersion, and misses.",
            "bag": [
                {
                    "club": club["club"],
                    "shot_count": club["shot_count"],
                    "confidence": club["confidence"]["rating"],
                    "expected_carry_yards": club["averages"]["carry"],
                    "playable_carry_yards": club["playable_yardage"]["carry"],
                    "carry_80_percent_window": club["confidence"]["carry"]["p10_p90"],
                    "expected_total_yards": club["averages"]["total"],
                    "offline_tendency": club["tendencies"]["direction"],
                    "dispersion_tendency": club["tendencies"]["dispersion"],
                    "avg_offline_yards": club["tendencies"]["avg_offline"],
                    "launch_angle": club["averages"]["launch_angle"],
                    "spin": club["averages"]["total_spin"],
                    "notes": club["ai_notes"],
                }
                for club in bag_summary["clubs"]
            ],
            "raw_summary": bag_summary,
        }

    def publish_player_exports(self, player: str) -> None:
        bag_summary = self.build_bag_summary(player)
        player_slug = topic_segment(player)
        self.client.publish(
            f"{self.args.summary_prefix}/{player_slug}/bag",
            json.dumps(bag_summary, separators=(",", ":")),
            qos=1,
            retain=True,
        )
        self.client.publish(
            f"{self.args.export_prefix}/{player_slug}/ai",
            json.dumps(self.build_ai_export(player), separators=(",", ":")),
            qos=1,
            retain=True,
        )

    def publish_session_progress(self, session_id: str, player: str) -> None:
        rows = self.db.execute(
            """
            select club, count(*) as shot_count, avg(carry) as avg_carry
            from shots
            where discarded = 0 and session_id = ? and player = ?
            group by club
            order by min(received_at)
            """,
            (session_id, player),
        ).fetchall()
        payload = {
            "session_id": session_id,
            "player": player,
            "clubs": [dict(row) for row in rows],
            "updated_at": utc_now(),
        }
        topic = f"{self.args.summary_prefix}/session/{topic_segment(session_id)}"
        self.client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=1, retain=True)

    def close(self) -> None:
        self.client.disconnect()
        self.db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Store NOVA launch monitor shots from MQTT in SQLite.")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD"))
    parser.add_argument("--client-id", default=os.getenv("MQTT_CLIENT_ID", "nova-shot-logger"))
    parser.add_argument("--db", default=os.getenv("NOVA_LOGGER_DB", "data/nova-shots.sqlite3"))
    parser.add_argument("--context-topic", default=os.getenv("NOVA_CONTEXT_TOPIC", DEFAULT_CONTEXT_TOPIC))
    parser.add_argument("--shot-topic", default=os.getenv("NOVA_SHOT_TOPIC", DEFAULT_SHOT_TOPIC))
    parser.add_argument("--discard-topic", default=os.getenv("NOVA_DISCARD_TOPIC", DEFAULT_DISCARD_TOPIC))
    parser.add_argument("--summary-prefix", default=os.getenv("NOVA_SUMMARY_PREFIX", DEFAULT_SUMMARY_PREFIX))
    parser.add_argument("--export-prefix", default=os.getenv("NOVA_EXPORT_PREFIX", DEFAULT_EXPORT_PREFIX))
    parser.add_argument(
        "--store-unrecorded",
        action="store_true",
        default=parse_bool(os.getenv("NOVA_STORE_UNRECORDED", "false")),
        help="Store shots even when HA recording context is false.",
    )
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    return parser


def main() -> int:
    load_dotenv(Path(".env"))
    args = build_parser().parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")
    service = NovaShotLogger(args)
    should_stop = False

    def stop(signum: int, frame: Any) -> None:
        nonlocal should_stop
        should_stop = True
        LOGGER.info("Stopping...")
        service.client.loop_stop()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    service.connect()
    service.client.loop_start()
    try:
        while not should_stop:
            time.sleep(0.5)
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
