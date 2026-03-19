"""
MCP configuration templates and generators.

Provides utilities for generating MCP configuration files for various
clients (Claude Desktop, VSCode, custom) from OrmAI settings.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class McpClientType(str, Enum):
    """Supported MCP client types."""

    CLAUDE_DESKTOP = "claude_desktop"
    VSCODE = "vscode"
    CURSOR = "cursor"
    GENERIC = "generic"


@dataclass
class McpServerConfig:
    """Configuration for an MCP server."""

    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "command": self.command,
        }
        if self.args:
            result["args"] = self.args
        if self.env:
            result["env"] = self.env
        return result


@dataclass
class OrmAIServerConfig(McpServerConfig):
    """Configuration for an OrmAI MCP server."""

    # Database connection
    database_url: str = ""

    # Policy settings
    policy_preset: str = "dev"  # dev, internal, prod

    # Feature flags
    enable_writes: bool = False
    enable_audit: bool = True

    # Authentication
    auth_type: str = "none"  # none, jwt, api_key
    auth_secret: str | None = None

    def __post_init__(self):
        """Build command and args from settings."""
        if not self.command:
            self.command = "uv"
        if not self.args:
            self.args = ["run", "ormai-mcp"]

    def with_database(self, url: str) -> "OrmAIServerConfig":
        """Set database URL."""
        self.database_url = url
        self.env["ORMAI_DATABASE_URL"] = url
        return self

    def with_writes(self, enabled: bool = True) -> "OrmAIServerConfig":
        """Enable or disable write operations."""
        self.enable_writes = enabled
        self.env["ORMAI_ENABLE_WRITES"] = str(enabled).lower()
        return self

    def with_policy(self, preset: str) -> "OrmAIServerConfig":
        """Set policy preset."""
        self.policy_preset = preset
        self.env["ORMAI_POLICY_PRESET"] = preset
        return self

    def with_jwt_auth(self, secret: str) -> "OrmAIServerConfig":
        """Configure JWT authentication."""
        self.auth_type = "jwt"
        self.auth_secret = secret
        self.env["ORMAI_AUTH_TYPE"] = "jwt"
        self.env["ORMAI_JWT_SECRET"] = secret
        return self

    def with_api_key(self, key: str) -> "OrmAIServerConfig":
        """Configure API key authentication."""
        self.auth_type = "api_key"
        self.auth_secret = key
        self.env["ORMAI_AUTH_TYPE"] = "api_key"
        self.env["ORMAI_API_KEY"] = key
        return self


class McpConfigGenerator:
    """
    Generator for MCP configuration files.

    Produces config files for different MCP clients.
    """

    def __init__(self) -> None:
        self.servers: dict[str, McpServerConfig] = {}

    def add_server(
        self,
        config: McpServerConfig,
    ) -> "McpConfigGenerator":
        """Add a server configuration."""
        self.servers[config.name] = config
        return self

    def add_ormai(
        self,
        name: str = "ormai",
        database_url: str = "",
        policy_preset: str = "dev",
        enable_writes: bool = False,
    ) -> "McpConfigGenerator":
        """Add an OrmAI server with common settings."""
        config = OrmAIServerConfig(name=name)
        if database_url:
            config.with_database(database_url)
        config.with_policy(policy_preset)
        config.with_writes(enable_writes)
        self.servers[name] = config
        return self

    def generate(self, client_type: McpClientType) -> dict[str, Any]:
        """
        Generate configuration for the specified client type.

        Returns a dictionary suitable for JSON serialization.
        """
        if client_type == McpClientType.CLAUDE_DESKTOP:
            return self._generate_claude_desktop()
        elif client_type == McpClientType.VSCODE:
            return self._generate_vscode()
        elif client_type == McpClientType.CURSOR:
            return self._generate_cursor()
        else:
            return self._generate_generic()

    def _generate_claude_desktop(self) -> dict[str, Any]:
        """Generate Claude Desktop configuration."""
        servers = {}
        for name, config in self.servers.items():
            servers[name] = config.to_dict()
        return {"mcpServers": servers}

    def _generate_vscode(self) -> dict[str, Any]:
        """Generate VSCode MCP extension configuration."""
        servers = []
        for name, config in self.servers.items():
            server = {
                "name": name,
                "command": config.command,
                "args": config.args,
            }
            if config.env:
                server["env"] = config.env
            servers.append(server)
        return {"mcp.servers": servers}

    def _generate_cursor(self) -> dict[str, Any]:
        """Generate Cursor configuration."""
        # Cursor uses same format as Claude Desktop
        return self._generate_claude_desktop()

    def _generate_generic(self) -> dict[str, Any]:
        """Generate generic configuration."""
        servers = {}
        for name, config in self.servers.items():
            servers[name] = {
                "name": name,
                "command": config.command,
                "args": config.args,
                "env": config.env,
            }
        return {"servers": servers}

    def to_json(self, client_type: McpClientType, indent: int = 2) -> str:
        """Generate configuration as JSON string."""
        config = self.generate(client_type)
        return json.dumps(config, indent=indent)

    def write(
        self,
        path: str | Path,
        client_type: McpClientType,
    ) -> Path:
        """Write configuration to a file."""
        path = Path(path)
        config_json = self.to_json(client_type)
        path.write_text(config_json)
        return path


# Pre-built templates for common setups
class McpTemplates:
    """Pre-built MCP configuration templates."""

    @staticmethod
    def development(
        database_url: str = "sqlite:///./dev.db",
        name: str = "ormai-dev",
    ) -> McpConfigGenerator:
        """
        Development template with writes enabled.

        Good for local development and testing.
        """
        return (
            McpConfigGenerator()
            .add_ormai(
                name=name,
                database_url=database_url,
                policy_preset="dev",
                enable_writes=True,
            )
        )

    @staticmethod
    def readonly(
        database_url: str,
        name: str = "ormai",
    ) -> McpConfigGenerator:
        """
        Read-only production template.

        Safe for querying production data without write access.
        """
        return (
            McpConfigGenerator()
            .add_ormai(
                name=name,
                database_url=database_url,
                policy_preset="prod",
                enable_writes=False,
            )
        )

    @staticmethod
    def internal(
        database_url: str,
        name: str = "ormai-internal",
    ) -> McpConfigGenerator:
        """
        Internal tools template.

        For internal dashboards with more access than production.
        """
        return (
            McpConfigGenerator()
            .add_ormai(
                name=name,
                database_url=database_url,
                policy_preset="internal",
                enable_writes=False,
            )
        )

    @staticmethod
    def multi_tenant(
        database_url: str,
        auth_secret: str,
        name: str = "ormai-mt",
    ) -> McpConfigGenerator:
        """
        Multi-tenant template with JWT authentication.

        For SaaS applications with tenant isolation.
        """
        config = OrmAIServerConfig(name=name)
        config.with_database(database_url)
        config.with_policy("prod")
        config.with_jwt_auth(auth_secret)

        return McpConfigGenerator().add_server(config)


def get_claude_desktop_config_path() -> Path:
    """Get the default Claude Desktop config path for the current OS."""
    import platform

    system = platform.system()

    if system == "Darwin":  # macOS
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    elif system == "Windows":
        return Path.home() / "AppData/Roaming/Claude/claude_desktop_config.json"
    else:  # Linux and others
        return Path.home() / ".config/Claude/claude_desktop_config.json"


def install_claude_desktop(
    generator: McpConfigGenerator,
    merge: bool = True,
) -> Path:
    """
    Install MCP configuration to Claude Desktop.

    Args:
        generator: The configuration generator
        merge: If True, merge with existing config; if False, replace

    Returns the path to the config file.
    """
    config_path = get_claude_desktop_config_path()

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if merge and config_path.exists():
        # Load existing config and merge
        existing = json.loads(config_path.read_text())
        new_config = generator.generate(McpClientType.CLAUDE_DESKTOP)

        # Merge mcpServers
        if "mcpServers" not in existing:
            existing["mcpServers"] = {}
        existing["mcpServers"].update(new_config.get("mcpServers", {}))

        config_path.write_text(json.dumps(existing, indent=2))
    else:
        generator.write(config_path, McpClientType.CLAUDE_DESKTOP)

    return config_path
