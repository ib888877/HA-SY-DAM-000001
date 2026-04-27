#!/usr/bin/env python3
"""
Home Assistant exporter

What it does:
- Reads Home Assistant URL + token from .env
- Exports many REST API resources into separate JSON files
- Uses WebSocket API for richer registries/metadata when available
- Optionally captures live events for a short window
- Stores everything in a timestamped export folder

Tested style:
- Python 3.10+
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None


@dataclass
class Settings:
    ha_url: str
    ha_token: str
    export_root: Path
    verify_ssl: bool
    timeout_seconds: int
    history_days: int
    logbook_days: int
    live_event_capture_seconds: int


class HomeAssistantExporter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.settings.ha_token}",
                "Content-Type": "application/json",
            }
        )
        self.run_dir = self.settings.export_root / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.meta: Dict[str, Any] = {
            "started_at": self._now_iso(),
            "ha_url": self.settings.ha_url,
            "verify_ssl": self.settings.verify_ssl,
            "files": [],
            "warnings": [],
            "errors": [],
        }

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _record_file(self, filename: str) -> None:
        self.meta["files"].append(filename)

    def save_json(self, filename: str, data: Any) -> None:
        path = self.run_dir / filename
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        self._record_file(filename)

    def log_warning(self, message: str) -> None:
        print(f"[WARN] {message}")
        self.meta["warnings"].append(message)

    def log_error(self, message: str) -> None:
        print(f"[ERROR] {message}", file=sys.stderr)
        self.meta["errors"].append(message)

    def rest_get(
        self,
        api_path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        allow_error: bool = True,
    ) -> Any:
        url = f"{self.settings.ha_url.rstrip('/')}/{api_path.lstrip('/')}"
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.settings.timeout_seconds,
                verify=self.settings.verify_ssl,
            )
            content_type = response.headers.get("content-type", "")
            if response.status_code >= 400:
                msg = f"GET {api_path} failed: HTTP {response.status_code} - {response.text[:500]}"
                if allow_error:
                    self.log_warning(msg)
                    return {
                        "_error": msg,
                        "status_code": response.status_code,
                        "body": response.text,
                    }
                raise RuntimeError(msg)

            if "application/json" in content_type:
                return response.json()

            text = response.text
            return {"_raw_text": text}
        except Exception as exc:
            msg = f"GET {api_path} exception: {exc}"
            if allow_error:
                self.log_warning(msg)
                return {"_error": msg}
            raise

    def _ws_url(self) -> str:
        if self.settings.ha_url.startswith("https://"):
            return self.settings.ha_url.replace("https://", "wss://", 1).rstrip("/") + "/api/websocket"
        return self.settings.ha_url.replace("http://", "ws://", 1).rstrip("/") + "/api/websocket"

    def ws_call_many(self, commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Connect once, authenticate, then run a list of WS commands.
        Unsupported commands are captured as errors and do not stop the export.
        """
        if websocket is None:
            return {
                "_error": "websocket-client is not installed. Run: pip install websocket-client"
            }

        results: Dict[str, Any] = {}
        ws = None

        try:
            sslopt: Dict[str, Any] = {}
            if self._ws_url().startswith("wss://") and not self.settings.verify_ssl:
                sslopt = {"cert_reqs": ssl.CERT_NONE}

            ws = websocket.create_connection(
                self._ws_url(),
                timeout=self.settings.timeout_seconds,
                sslopt=sslopt,
            )

            hello = json.loads(ws.recv())
            if hello.get("type") != "auth_required":
                raise RuntimeError(f"Unexpected WS hello: {hello}")

            ws.send(json.dumps({"type": "auth", "access_token": self.settings.ha_token}))
            auth_result = json.loads(ws.recv())
            if auth_result.get("type") != "auth_ok":
                raise RuntimeError(f"WS auth failed: {auth_result}")

            msg_id = 1
            for command in commands:
                payload = {"id": msg_id, **command}
                ws.send(json.dumps(payload))
                reply = json.loads(ws.recv())
                key = command["type"].replace("/", "_")
                results[key] = reply
                msg_id += 1

            return results

        except Exception as exc:
            return {"_error": f"WebSocket export failed: {exc}"}
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    def ws_capture_live_events(self, seconds: int) -> Dict[str, Any]:
        """
        Subscribe to all events and capture them briefly.
        Useful for seeing what HA is emitting in your setup.
        """
        if websocket is None:
            return {
                "_error": "websocket-client is not installed. Run: pip install websocket-client"
            }

        ws = None
        captured: List[Dict[str, Any]] = []

        try:
            sslopt: Dict[str, Any] = {}
            if self._ws_url().startswith("wss://") and not self.settings.verify_ssl:
                sslopt = {"cert_reqs": ssl.CERT_NONE}

            ws = websocket.create_connection(
                self._ws_url(),
                timeout=self.settings.timeout_seconds,
                sslopt=sslopt,
            )

            hello = json.loads(ws.recv())
            if hello.get("type") != "auth_required":
                raise RuntimeError(f"Unexpected WS hello: {hello}")

            ws.send(json.dumps({"type": "auth", "access_token": self.settings.ha_token}))
            auth_result = json.loads(ws.recv())
            if auth_result.get("type") != "auth_ok":
                raise RuntimeError(f"WS auth failed: {auth_result}")

            # subscribe to all events
            ws.send(json.dumps({"id": 1, "type": "subscribe_events"}))
            sub_reply = json.loads(ws.recv())

            end_time = time.time() + seconds
            while time.time() < end_time:
                remaining = max(1, int(end_time - time.time()))
                ws.settimeout(remaining)
                try:
                    msg = json.loads(ws.recv())
                    captured.append(msg)
                except Exception:
                    break

            return {
                "subscription_reply": sub_reply,
                "captured_seconds": seconds,
                "captured_count": len(captured),
                "events": captured,
            }

        except Exception as exc:
            return {"_error": f"Live event capture failed: {exc}"}
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    def export_rest_basics(self) -> List[str]:
        files: List[str] = []

        endpoints = {
            "api_root.json": "api/",
            "config.json": "api/config",
            "states.json": "api/states",
            "services.json": "api/services",
            "event_types.json": "api/events",
            "components.json": "api/components",
        }

        for filename, path in endpoints.items():
            data = self.rest_get(path)
            self.save_json(filename, data)
            files.append(filename)

        return files

    def export_history(self) -> Optional[str]:
        start = (datetime.now(timezone.utc) - timedelta(days=self.settings.history_days)).isoformat()
        encoded_start = quote(start, safe="")
        path = f"api/history/period/{encoded_start}"

        # Add the entities you want history for
        filter_entities = [
            "sensor.sonoff_1002328b17_power",
            "switch.sonoff_100255f378",
            "switch.sonoff_100242e465_1",
        ]

        params = {
            "filter_entity_id": ",".join(filter_entities),
            "minimal_response": "0",
            "significant_changes_only": "0",
        }

        data = self.rest_get(path, params=params)
        filename = "history_recent.json"
        self.save_json(filename, data)
        return filename

    def export_logbook(self) -> Optional[str]:
        start = (datetime.now(timezone.utc) - timedelta(days=self.settings.logbook_days)).isoformat()
        encoded_start = quote(start, safe="")
        path = f"api/logbook/{encoded_start}"

        data = self.rest_get(path)
        filename = "logbook_recent.json"
        self.save_json(filename, data)
        return filename

    def export_ws_metadata(self) -> List[str]:
        files: List[str] = []

        # These WS commands are commonly used by the frontend / registries.
        # Some may be unavailable depending on version or permissions.
        commands = [
            {"type": "get_states"},
            {"type": "config/area_registry/list"},
            {"type": "config/device_registry/list"},
            {"type": "config/entity_registry/list"},
            {"type": "config/floor_registry/list"},
            {"type": "config/label_registry/list"},
            {"type": "lovelace/config"},
        ]

        results = self.ws_call_many(commands)
        self.save_json("ws_metadata.json", results)
        files.append("ws_metadata.json")

        # Split selected pieces into their own files for easier later analysis
        mapping = {
            "get_states": "ws_states.json",
            "config_area_registry_list": "areas.json",
            "config_device_registry_list": "devices.json",
            "config_entity_registry_list": "entity_registry.json",
            "config_floor_registry_list": "floors.json",
            "config_label_registry_list": "labels.json",
            "lovelace_config": "lovelace_config.json",
        }

        for key, filename in mapping.items():
            if key in results:
                self.save_json(filename, results[key])
                files.append(filename)

        return files

    def export_live_events(self) -> Optional[str]:
        seconds = self.settings.live_event_capture_seconds
        if seconds <= 0:
            return None

        data = self.ws_capture_live_events(seconds)
        filename = "live_events_capture.json"
        self.save_json(filename, data)
        return filename

    def build_summary(self) -> str:
        summary_path = self.run_dir / "README.txt"
        lines = [
            "Home Assistant Export Summary",
            "============================",
            f"Created: {self.meta['started_at']}",
            f"Home Assistant URL: {self.settings.ha_url}",
            f"Export folder: {self.run_dir}",
            "",
            "Generated files:",
        ]
        for file_name in self.meta["files"]:
            lines.append(f"- {file_name}")

        if self.meta["warnings"]:
            lines.extend(["", "Warnings:"])
            lines.extend([f"- {w}" for w in self.meta["warnings"]])

        if self.meta["errors"]:
            lines.extend(["", "Errors:"])
            lines.extend([f"- {e}" for e in self.meta["errors"]])

        summary_path.write_text("\n".join(lines), encoding="utf-8")
        self._record_file("README.txt")
        return str(summary_path)

    def run(self) -> int:
        print(f"[INFO] Export folder: {self.run_dir}")

        try:
            self.export_rest_basics()
            self.export_history()
            self.export_logbook()
            self.export_ws_metadata()
            self.export_live_events()

            self.meta["finished_at"] = self._now_iso()
            self.save_json("export_meta.json", self.meta)
            self.build_summary()

            print("[INFO] Export completed successfully.")
            return 0

        except KeyboardInterrupt:
            self.log_error("Export interrupted by user.")
            self.meta["finished_at"] = self._now_iso()
            self.save_json("export_meta.json", self.meta)
            return 130
        except Exception as exc:
            self.log_error(f"Export failed: {exc}")
            self.meta["finished_at"] = self._now_iso()
            self.save_json("export_meta.json", self.meta)
            return 1


def parse_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv()

    ha_url = os.getenv("HA_URL", "").strip()
    ha_token = os.getenv("HA_TOKEN", "").strip()

    if not ha_url:
        raise ValueError("Missing HA_URL in .env")
    if not ha_token:
        raise ValueError("Missing HA_TOKEN in .env")

    export_dir = Path(os.getenv("EXPORT_DIR", "ha_exports")).resolve()
    verify_ssl = parse_bool(os.getenv("VERIFY_SSL", "true"), default=True)
    timeout_seconds = int(os.getenv("TIMEOUT_SECONDS", "30"))
    history_days = int(os.getenv("HISTORY_DAYS", "2"))
    logbook_days = int(os.getenv("LOGBOOK_DAYS", "2"))
    live_event_capture_seconds = int(os.getenv("LIVE_EVENT_CAPTURE_SECONDS", "20"))

    return Settings(
        ha_url=ha_url.rstrip("/"),
        ha_token=ha_token,
        export_root=export_dir,
        verify_ssl=verify_ssl,
        timeout_seconds=timeout_seconds,
        history_days=history_days,
        logbook_days=logbook_days,
        live_event_capture_seconds=live_event_capture_seconds,
    )


def main() -> int:
    settings = load_settings()
    exporter = HomeAssistantExporter(settings)
    return exporter.run()


if __name__ == "__main__":
    raise SystemExit(main())