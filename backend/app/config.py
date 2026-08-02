"""Configuration model and loader.

All numbers, paths and limits used anywhere in the application come from here
(CLAUDE.md rule 6). The YAML file is validated against these Pydantic models;
unknown keys are rejected (``extra="forbid"``) instead of being silently ignored.

An invalid ``config.yaml`` must produce a readable message at startup, not a
traceback deep inside the application (milestone M1). ``load_config`` therefore
converts every ``ValidationError`` into a :class:`ConfigError` with a plain,
German, line-oriented explanation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _Model(BaseModel):
    """Base for all config sections: reject unknown keys, validate live edits."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CameraConfig(_Model):
    backend: Literal["gphoto2", "mock"] = "gphoto2"
    # Welche DSLR ausgelöst wird: "auto" = erste erkannte, sonst Modellname oder Port.
    select: str = "auto"
    # off = sofort auslösen (manueller Fokus, Fotobox-Standard, nie blockiert);
    # before_capture = AF vor der Auslösung, aber mit Auslösepriorität (blockiert nie).
    autofocus: Literal["off", "before_capture"] = "off"
    # gphoto2-Widget-Werte, die vor dem Auslösen gesetzt werden; leer = Kamera nicht
    # verändern. "JPEG" verhindert, dass eine Kamera im RAW+JPEG-Modus (Sony a7 IV)
    # die unbrauchbare RAW-Datei liefert. Passt der Wert nicht zur Kamera, bleibt die
    # Einstellung unverändert und der JPEG-Umweg unten greift.
    image_quality: str = "JPEG"
    capture_target: str = ""
    capture_timeout_seconds: float = Field(gt=0)
    reconnect_backoff_seconds: list[float]
    usbreset_after_failures: int = Field(ge=0)
    # If the DSLR is unavailable (e.g. dead battery), take the photo with the
    # preview camera instead of failing — a lower-quality but working backup.
    fallback_to_preview: bool = True


class PreviewConfig(_Model):
    # gphoto2 = Live-Bild aus der DSLR. Regel 1 will eine eigene Vorschaukamera;
    # ohne zweite Kamera gäbe es sonst gar kein Live-Bild.
    backend: Literal["picamera2", "v4l2", "gphoto2", "mock", "auto"] = "picamera2"
    device: str = "/dev/video0"  # "auto", /dev/videoN, gphoto2-Port oder Geräte-ID
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0)
    jpeg_quality: int = Field(ge=1, le=100)


class PrinterConfig(_Model):
    backend: Literal["cups", "mock"] = "cups"
    queue_name: str
    status_poll_seconds: float = Field(gt=0)


class HardwareConfig(_Model):
    mode: Literal["real", "mock"] = "real"
    camera: CameraConfig
    preview: PreviewConfig
    printer: PrinterConfig


class CountdownConfig(_Model):
    duration_seconds: int = Field(ge=1)
    # Vorlauf: so viel früher als "0" wird ausgelöst, um die Verzögerung zwischen
    # Auslösebefehl und Belichtung auszugleichen (Blitz + Kameralatenz). 0 = aus.
    shutter_lead_ms: int = Field(default=0, ge=0, le=5000)
    sound_enabled: bool = False
    sound_tick: str = ""
    sound_shutter: str = ""


class TimeoutsConfig(_Model):
    background_select_seconds: float = Field(gt=0)
    countdown_cancel_grace_seconds: float = Field(ge=0)
    capture_seconds: float = Field(gt=0)
    processing_warn_seconds: float = Field(gt=0)
    processing_seconds: float = Field(gt=0)
    preview_seconds: float = Field(gt=0)
    error_seconds: float = Field(gt=0)


class UIConfig(_Model):
    background_select_enabled: bool = True
    default_background: str = "none"
    mirror_preview: bool = True
    idle_hint_pulse: bool = True
    # Screen flash as a fill light: the screen turns white for flash_duration_ms
    # *before* the shutter fires, then stays white through the capture.
    flash_enabled: bool = True
    flash_duration_ms: int = Field(default=400, ge=0)
    admin_corner: Literal["top_left", "top_right"] = "top_left"
    admin_longpress_seconds: float = Field(gt=0)
    admin_pin: str


class ChromaDefaults(_Model):
    hue_center: float
    hue_tolerance: float
    saturation_min: float
    value_min: float
    spill_suppression: float
    edge_feather_px: float


class AIConfig(_Model):
    model: str
    model_path: str
    max_seconds: float = Field(gt=0)


class PipelineConfig(_Model):
    chroma_defaults: ChromaDefaults
    ai: AIConfig
    jpeg_quality: int = Field(ge=1, le=100)
    thumbnail_width: int = Field(gt=0)


class CaptionConfig(_Model):
    enabled: bool = False
    text: str = ""
    position: Literal["bottom_center", "bottom_right", "top_center"] = "bottom_center"
    font: str = ""
    size_px: int = Field(gt=0)
    color: str = "#ffffff"
    shadow: bool = True


class QRConfig(_Model):
    enabled: bool = False
    base_url: str = ""
    size_px: int = Field(gt=0)
    position: Literal["bottom_right", "bottom_left", "bottom_center"] = "bottom_right"


class PrintingConfig(_Model):
    enabled: bool = True
    orientation: Literal["portrait", "landscape"] = "landscape"
    canvas_width: int = Field(gt=0)
    canvas_height: int = Field(gt=0)
    safe_margin_x: int = Field(ge=0)
    safe_margin_y: int = Field(ge=0)
    max_per_photo: int = Field(ge=0)
    max_per_event: int = Field(ge=0)
    queue_warn_length: int = Field(ge=0)
    sheets_per_cartridge: int = Field(gt=0)
    caption: CaptionConfig
    qr: QRConfig


class StorageConfig(_Model):
    data_dir: str
    warn_threshold_percent: int = Field(ge=0, le=100)
    block_threshold_percent: int = Field(ge=0, le=100)


class AccessPointConfig(_Model):
    enabled: bool = False
    ssid: str = "Fotobox"
    passphrase: str = ""
    channel: int = Field(ge=1, le=196)
    address: str = "192.168.4.1"


class NetworkConfig(_Model):
    gallery_enabled: bool = True
    access_point: AccessPointConfig


class LoggingConfig(_Model):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str
    max_bytes: int = Field(gt=0)
    backup_count: int = Field(ge=0)


class RuntimeConfig(_Model):
    # How often the state-machine clock is polled (countdown ticks, timeouts).
    tick_interval_seconds: float = Field(default=0.1, gt=0)
    # Name given to the automatically created default event on a fresh install.
    default_event_name: str = "Fotobox"


class Config(_Model):
    hardware: HardwareConfig
    countdown: CountdownConfig
    timeouts: TimeoutsConfig
    ui: UIConfig
    pipeline: PipelineConfig
    printing: PrintingConfig
    storage: StorageConfig
    network: NetworkConfig
    logging: LoggingConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    @property
    def data_dir(self) -> Path:
        return Path(self.storage.data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "fotobox.db"

    @property
    def events_dir(self) -> Path:
        return self.data_dir / "events"

    @property
    def backgrounds_dir(self) -> Path:
        return self.data_dir / "backgrounds"


class ConfigError(Exception):
    """A readable configuration problem, safe to print at startup."""


def _format_validation_error(path: Path, error: ValidationError) -> str:
    lines = [f"Fehler in der Konfiguration ({path}):"]
    for err in error.errors():
        location = ".".join(str(part) for part in err["loc"]) or "(Wurzel)"
        lines.append(f"  - {location}: {err['msg']}")
    return "\n".join(lines)


def _apply_env_overrides(raw: dict) -> None:
    """Environment overrides used during development.

    Only the two knobs the workstation needs: hardware mode (mock vs. real) and
    a writable data directory (the Pi uses /data, a dev box does not).
    """
    hardware_mode = os.environ.get("FOTOBOX_HARDWARE")
    if hardware_mode:
        raw.setdefault("hardware", {})["mode"] = hardware_mode

    data_dir = os.environ.get("FOTOBOX_DATA_DIR")
    if data_dir:
        raw.setdefault("storage", {})["data_dir"] = data_dir
        # Keep the log inside the writable dev data dir, not the Pi's /data.
        raw.setdefault("logging", {})["file"] = str(Path(data_dir) / "logs" / "fotobox.log")


def default_config_path() -> Path:
    """Where the config lives: env override, else /data, else the bundled example."""
    override = os.environ.get("FOTOBOX_CONFIG")
    if override:
        return Path(override)
    deployed = Path("/data/config.yaml")
    if deployed.exists():
        return deployed
    # Development fallback: the example shipped in the repository root.
    return Path(__file__).resolve().parents[2] / "config.example.yaml"


def load_config(path: Path | None = None) -> Config:
    """Load, override and validate the configuration.

    Raises :class:`ConfigError` with a readable message on any problem.
    """
    path = path or default_config_path()
    if not path.exists():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Konfiguration ist kein gültiges YAML ({path}):\n  {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(
            f"Konfiguration ({path}) muss ein YAML-Objekt sein, nicht {type(raw).__name__}."
        )

    _apply_env_overrides(raw)

    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(path, exc)) from exc


def save_config(config: Config, path: Path) -> None:
    """Write the config back to disk (used by runtime admin changes).

    Note: this rewrites the file from the model, so YAML comments are not
    preserved — the file becomes machine-managed once written.
    """
    data = config.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
