"""Tests for MCP configuration utilities."""

import json
import tempfile
from pathlib import Path

from ormai.mcp.config import (
    McpClientType,
    McpConfigGenerator,
    McpServerConfig,
    McpTemplates,
    OrmAIServerConfig,
)


class TestMcpServerConfig:
    """Tests for McpServerConfig."""

    def test_basic_config(self):
        """Test basic server config."""
        config = McpServerConfig(
            name="test-server",
            command="python",
            args=["-m", "my_server"],
            env={"API_KEY": "secret"},
        )

        assert config.name == "test-server"
        assert config.command == "python"
        assert config.args == ["-m", "my_server"]
        assert config.env == {"API_KEY": "secret"}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = McpServerConfig(
            name="test",
            command="node",
            args=["index.js"],
            env={"PORT": "3000"},
        )

        result = config.to_dict()

        assert result["command"] == "node"
        assert result["args"] == ["index.js"]
        assert result["env"] == {"PORT": "3000"}

    def test_minimal_config(self):
        """Test config with only required fields."""
        config = McpServerConfig(name="test", command="python")

        result = config.to_dict()

        assert result == {"command": "python"}
        assert "args" not in result
        assert "env" not in result


class TestOrmAIServerConfig:
    """Tests for OrmAIServerConfig."""

    def test_default_command(self):
        """Test default command is uv run ormai-mcp."""
        config = OrmAIServerConfig(name="ormai")

        assert config.command == "uv"
        assert config.args == ["run", "ormai-mcp"]

    def test_with_database(self):
        """Test setting database URL."""
        config = OrmAIServerConfig(name="ormai")
        config.with_database("postgresql://localhost/mydb")

        assert config.database_url == "postgresql://localhost/mydb"
        assert config.env["ORMAI_DATABASE_URL"] == "postgresql://localhost/mydb"

    def test_with_writes(self):
        """Test enabling writes."""
        config = OrmAIServerConfig(name="ormai")
        config.with_writes(True)

        assert config.enable_writes is True
        assert config.env["ORMAI_ENABLE_WRITES"] == "true"

    def test_with_policy(self):
        """Test setting policy preset."""
        config = OrmAIServerConfig(name="ormai")
        config.with_policy("prod")

        assert config.policy_preset == "prod"
        assert config.env["ORMAI_POLICY_PRESET"] == "prod"

    def test_with_jwt_auth(self):
        """Test JWT authentication."""
        config = OrmAIServerConfig(name="ormai")
        config.with_jwt_auth("secret123")

        assert config.auth_type == "jwt"
        assert config.auth_secret == "secret123"
        assert config.env["ORMAI_AUTH_TYPE"] == "jwt"
        assert config.env["ORMAI_JWT_SECRET"] == "secret123"

    def test_with_api_key(self):
        """Test API key authentication."""
        config = OrmAIServerConfig(name="ormai")
        config.with_api_key("key123")

        assert config.auth_type == "api_key"
        assert config.env["ORMAI_API_KEY"] == "key123"

    def test_fluent_api(self):
        """Test fluent API chaining."""
        config = (
            OrmAIServerConfig(name="ormai")
            .with_database("sqlite:///test.db")
            .with_policy("internal")
            .with_writes(True)
        )

        assert config.database_url == "sqlite:///test.db"
        assert config.policy_preset == "internal"
        assert config.enable_writes is True


class TestMcpConfigGenerator:
    """Tests for McpConfigGenerator."""

    def test_add_server(self):
        """Test adding a server."""
        generator = McpConfigGenerator()
        config = McpServerConfig(name="test", command="python")

        generator.add_server(config)

        assert "test" in generator.servers

    def test_add_ormai(self):
        """Test adding OrmAI server."""
        generator = McpConfigGenerator()
        generator.add_ormai(
            name="my-ormai",
            database_url="sqlite:///test.db",
            policy_preset="dev",
            enable_writes=True,
        )

        assert "my-ormai" in generator.servers
        config = generator.servers["my-ormai"]
        assert config.env["ORMAI_DATABASE_URL"] == "sqlite:///test.db"
        assert config.env["ORMAI_POLICY_PRESET"] == "dev"

    def test_generate_claude_desktop(self):
        """Test Claude Desktop config generation."""
        generator = McpConfigGenerator()
        generator.add_ormai(name="ormai", database_url="sqlite:///test.db")

        result = generator.generate(McpClientType.CLAUDE_DESKTOP)

        assert "mcpServers" in result
        assert "ormai" in result["mcpServers"]
        assert result["mcpServers"]["ormai"]["command"] == "uv"

    def test_generate_vscode(self):
        """Test VSCode config generation."""
        generator = McpConfigGenerator()
        generator.add_ormai(name="ormai")

        result = generator.generate(McpClientType.VSCODE)

        assert "mcp.servers" in result
        assert len(result["mcp.servers"]) == 1
        assert result["mcp.servers"][0]["name"] == "ormai"

    def test_generate_cursor(self):
        """Test Cursor config generation (same as Claude Desktop)."""
        generator = McpConfigGenerator()
        generator.add_ormai(name="ormai")

        result = generator.generate(McpClientType.CURSOR)

        assert "mcpServers" in result

    def test_generate_generic(self):
        """Test generic config generation."""
        generator = McpConfigGenerator()
        generator.add_ormai(name="ormai")

        result = generator.generate(McpClientType.GENERIC)

        assert "servers" in result
        assert "ormai" in result["servers"]

    def test_to_json(self):
        """Test JSON output."""
        generator = McpConfigGenerator()
        generator.add_ormai(name="ormai")

        json_str = generator.to_json(McpClientType.CLAUDE_DESKTOP)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "mcpServers" in parsed

    def test_write(self):
        """Test writing to file."""
        generator = McpConfigGenerator()
        generator.add_ormai(name="ormai")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            result_path = generator.write(path, McpClientType.CLAUDE_DESKTOP)

            assert result_path == path
            assert path.exists()

            content = json.loads(path.read_text())
            assert "mcpServers" in content

    def test_fluent_api(self):
        """Test fluent API for building configs."""
        result = (
            McpConfigGenerator()
            .add_ormai("ormai1", database_url="sqlite:///db1.db")
            .add_ormai("ormai2", database_url="sqlite:///db2.db")
            .generate(McpClientType.CLAUDE_DESKTOP)
        )

        assert "ormai1" in result["mcpServers"]
        assert "ormai2" in result["mcpServers"]


class TestMcpTemplates:
    """Tests for pre-built templates."""

    def test_development_template(self):
        """Test development template."""
        generator = McpTemplates.development(
            database_url="sqlite:///dev.db",
            name="my-dev",
        )

        config = generator.generate(McpClientType.CLAUDE_DESKTOP)

        assert "my-dev" in config["mcpServers"]
        server = generator.servers["my-dev"]
        assert server.env.get("ORMAI_ENABLE_WRITES") == "true"
        assert server.env.get("ORMAI_POLICY_PRESET") == "dev"

    def test_readonly_template(self):
        """Test read-only production template."""
        generator = McpTemplates.readonly(
            database_url="postgresql://localhost/prod",
        )

        server = generator.servers["ormai"]
        assert server.env.get("ORMAI_ENABLE_WRITES") == "false"
        assert server.env.get("ORMAI_POLICY_PRESET") == "prod"

    def test_internal_template(self):
        """Test internal template."""
        generator = McpTemplates.internal(
            database_url="postgresql://localhost/internal",
        )

        server = generator.servers["ormai-internal"]
        assert server.env.get("ORMAI_POLICY_PRESET") == "internal"

    def test_multi_tenant_template(self):
        """Test multi-tenant template."""
        generator = McpTemplates.multi_tenant(
            database_url="postgresql://localhost/saas",
            auth_secret="jwt-secret-key",
        )

        server = generator.servers["ormai-mt"]
        assert server.env.get("ORMAI_AUTH_TYPE") == "jwt"
        assert server.env.get("ORMAI_JWT_SECRET") == "jwt-secret-key"


class TestMcpClientType:
    """Tests for MCP client types."""

    def test_client_types(self):
        """Test all client types exist."""
        assert McpClientType.CLAUDE_DESKTOP == "claude_desktop"
        assert McpClientType.VSCODE == "vscode"
        assert McpClientType.CURSOR == "cursor"
        assert McpClientType.GENERIC == "generic"
