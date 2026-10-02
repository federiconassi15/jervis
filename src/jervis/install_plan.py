from __future__ import annotations

from dataclasses import dataclass, field

from .openclaw_providers import provider


@dataclass(slots=True)
class InstallPlan:
    mode: str = "desktop"
    install_openclaw: bool = True
    openclaw_auth: str = "openai"
    openclaw_accept_risk: bool = False
    openclaw_accept_plugin_capabilities: bool = False
    openclaw_agent_name: str = "main"
    openclaw_api_key: str = field(default="", repr=False)
    openclaw_gateway_bind: str = "loopback"
    openclaw_gateway_auth: str = "generated-token"
    openclaw_gateway_secret: str = field(default="", repr=False)
    openclaw_daemon_runtime: str = "node"
    openclaw_node_manager: str = "npm"
    openclaw_install_daemon: bool = True
    openclaw_setup_skills: bool = True
    openclaw_setup_hooks: bool = True
    openclaw_setup_channels: bool = False
    openclaw_setup_search: bool = True
    openclaw_custom_base_url: str = ""
    openclaw_custom_model_id: str = ""
    openclaw_custom_provider_id: str = ""
    openclaw_custom_compatibility: str = "openai"
    openclaw_custom_image_input: bool = False
    openclaw_universal_auth_choice: str = ""
    openclaw_universal_credential_env: str = ""
    openclaw_universal_plugin: str = ""
    source_kind: str = "desktop"
    input_device: int | None = None
    android_serial: str | None = None
    output_device: int | None = None
    start_at_boot: bool = True
    owner_name: str = ""
    honorific: str = "sir"
    passphrase: str = field(default="", repr=False)

    def effective_openclaw_auth_choice(self) -> str:
        if self.openclaw_auth == "universal-provider":
            return self.openclaw_universal_auth_choice.strip()
        return self.openclaw_auth

    def validate_openclaw(self) -> None:
        if not self.openclaw_auth.strip():
            raise ValueError("Choose a valid OpenClaw setup option.")

        if self.openclaw_auth == "later":
            return

        if not self.openclaw_accept_risk:
            raise ValueError(
                "Acknowledge the OpenClaw agent/system-access warning before continuing."
            )
        if not self.openclaw_agent_name.strip():
            raise ValueError("Enter an OpenClaw agent name.")
        if self.openclaw_gateway_bind not in {"auto", "loopback", "lan", "tailnet"}:
            raise ValueError("Choose a valid OpenClaw Gateway bind mode.")
        if self.openclaw_gateway_auth not in {
            "generated-token",
            "token",
            "password",
        }:
            raise ValueError("Choose a valid OpenClaw Gateway auth mode.")
        if (
            self.openclaw_gateway_auth in {"token", "password"}
            and len(self.openclaw_gateway_secret) < 8
        ):
            raise ValueError(
                "The OpenClaw Gateway token/password must be at least 8 characters."
            )
        if self.openclaw_daemon_runtime not in {"node", "bun"}:
            raise ValueError("Choose Node or Bun for the OpenClaw daemon.")
        if self.openclaw_node_manager not in {"npm", "pnpm", "bun"}:
            raise ValueError("Choose npm, pnpm, or bun for OpenClaw skills.")

        if self.openclaw_auth == "universal-provider":
            if not self.openclaw_universal_auth_choice.strip():
                raise ValueError("Enter the OpenClaw auth-choice id.")
            env_name = self.openclaw_universal_credential_env.strip()
            if env_name and not env_name.replace("_", "").isalnum():
                raise ValueError(
                    "The provider credential environment variable must contain only letters, numbers, and underscores."
                )
            if self.openclaw_api_key.strip() and not env_name:
                raise ValueError(
                    "Enter the provider credential environment variable name."
                )
            if env_name and not self.openclaw_api_key.strip():
                raise ValueError("Enter the provider credential.")
            plugin = self.openclaw_universal_plugin.strip()
            if plugin:
                if not plugin.startswith("@openclaw/"):
                    raise ValueError(
                        "Automatic capability approval is limited to official @openclaw provider plugins."
                    )
                if not self.openclaw_accept_plugin_capabilities:
                    raise ValueError(
                        "Approve required OpenClaw provider plugin capabilities before continuing."
                    )
            return

        if self.openclaw_auth == "custom-api-key":
            if not self.openclaw_custom_base_url.strip():
                raise ValueError("Enter the custom provider base URL.")
            if not self.openclaw_custom_model_id.strip():
                raise ValueError("Enter the custom provider model ID.")
            if self.openclaw_custom_compatibility not in {
                "openai",
                "openai-responses",
                "anthropic",
            }:
                raise ValueError("Choose a valid custom provider compatibility mode.")
            return

        spec = provider(self.openclaw_auth)
        if spec is None:
            raise ValueError(
                "This OpenClaw provider is not in the current Jervis catalog. "
                "Choose Any OpenClaw provider for pass-through setup."
            )

        if (
            spec.credential_env
            and not spec.credential_optional
            and not self.openclaw_api_key.strip()
        ):
            raise ValueError("Enter the provider credential for OpenClaw.")
        if spec.requires_base_url and not self.openclaw_custom_base_url.strip():
            raise ValueError("Enter the provider base URL.")
        if spec.plugin and not self.openclaw_accept_plugin_capabilities:
            raise ValueError(
                "Approve required OpenClaw provider plugin capabilities before continuing."
            )

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
    openclaw_needs_auth: bool = False
    openclaw_configured: bool = False
    warnings: list[str] = field(default_factory=list)
