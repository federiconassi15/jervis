from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class InstallPlan:
    mode: str = "desktop"
    install_openclaw: bool = True
    openclaw_setup: str = "wizard"
    source_kind: str = "desktop"
    input_device: int | None = None
    android_serial: str | None = None
    output_device: int | None = None
    start_at_boot: bool = True
    owner_name: str = ""
    honorific: str = "sir"
    passphrase: str = field(default="", repr=False)

    def validate_openclaw(self) -> None:
        if self.openclaw_setup not in {"wizard", "later"}:
            raise ValueError("Choose Full OpenClaw setup or Configure later.")

    def validate(self) -> None:
        if self.mode not in {"desktop", "server"}:
            raise ValueError("Choose Desktop or Server.")
        if self.source_kind not in {"desktop", "android"}:
            raise ValueError("Choose a microphone source.")
        if self.source_kind == "desktop" and self.input_device is None:
            raise ValueError("Choose a microphone.")
        if self.output_device is None:
            raise ValueError("Choose a speaker/output device.")
        self.validate_openclaw()
        if not self.owner_name.strip():
            raise ValueError("Enter your name.")
        if self.honorific not in {"sir", "maam"}:
            raise ValueError("Choose Sir or Ma'am.")
        if len(self.passphrase) < 8:
            raise ValueError("The Jervis passphrase must be at least 8 characters.")


@dataclass(slots=True)
class InstallOutcome:
    openclaw_cli: str | None = None
    openclaw_needs_wizard: bool = False
    openclaw_configured: bool = False
    warnings: list[str] = field(default_factory=list)
