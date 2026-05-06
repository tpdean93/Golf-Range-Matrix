#!/usr/bin/env python3
"""Local MQTT-to-SQLite shot logger for NOVA/OpenGolfCoach data."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
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
            f"select id, player, club from shots where {' and '.join(where)} order by received_at desc limit 1",
            params,
        ).fetchone()
        if not row:
            LOGGER.info("Discard requested but no matching shot was found")
            return

        self.db.execute("update shots set discarded = 1, discarded_at = ? where id = ?", (utc_now(), row["id"]))
        self.db.commit()
        LOGGER.info("Discarded shot %s", row["id"])
        self.publish_summary(row["player"], row["club"])

    def publish_summary(self, player: str, club: str) -> None:
        row = self.db.execute(
            """
            select count(*) as shot_count,
              avg(carry) as avg_carry,
              avg(total) as avg_total,
              avg(offline) as avg_offline,
              avg(ball_speed) as avg_ball_speed,
              avg(club_speed) as avg_club_speed,
              avg(smash_factor) as avg_smash_factor,
              avg(launch_angle) as avg_launch_angle,
              avg(total_spin) as avg_total_spin,
              min(carry) as min_carry,
              max(carry) as max_carry
            from shots
            where discarded = 0 and player = ? and club = ?
            """,
            (player, club),
        ).fetchone()
        payload = {
            "player": player,
            "club": club,
            "shot_count": row["shot_count"],
            "averages": {
                "carry": row["avg_carry"],
                "total": row["avg_total"],
                "offline": row["avg_offline"],
                "ball_speed": row["avg_ball_speed"],
                "club_speed": row["avg_club_speed"],
                "smash_factor": row["avg_smash_factor"],
                "launch_angle": row["avg_launch_angle"],
                "total_spin": row["avg_total_spin"],
            },
            "carry_range": {"min": row["min_carry"], "max": row["max_carry"]},
            "updated_at": utc_now(),
        }
        topic = f"{self.args.summary_prefix}/{topic_segment(player)}/{topic_segment(club)}"
        self.client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=1, retain=True)

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
