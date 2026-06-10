"""Architecture guards for host smoke script and installability.

Asserts that host smoke and install surfaces do not import provider
SDKs, network clients, broker/order constructs, or server/daemon
modules. Asserts the OpenCode plugin does not spawn Python or
subprocesses. Asserts the runtime bridge remains a local CLI.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BANNED_IMPORTS = [
    "tavily", "finnhub", "exa", "firecrawl", "akshare",
    "openai", "anthropic", "langchain", "requests", "httpx",
    "aiohttp", "urllib3", "socket",
]

BANNED_CONSTRUCTS_IMPORT = [
    "broker", "order_execution", "trade_execution",
]


def _source_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _import_lines(path: Path) -> list[str]:
    return [
        line for line in _source_lines(path)
        if line.strip().startswith(("import ", "from "))
    ]


class TestSmokeScriptBoundaries:
    def test_smoke_script_no_provider_sdks(self):
        lines = _import_lines(ROOT / "scripts" / "smoke_host_install.py")
        for line in lines:
            for sdk in BANNED_IMPORTS:
                assert sdk not in line.lower(), f"Smoke script imports banned SDK: {sdk}"

    def test_smoke_script_no_network_clients(self):
        source = (ROOT / "scripts" / "smoke_host_install.py").read_text(encoding="utf-8").lower()
        for banned in ["requests", "httpx", "aiohttp", "urllib3", "socket"]:
            assert banned not in source, f"Smoke script references network client: {banned}"

    def test_smoke_script_no_broker_order_constructs(self):
        lines = _import_lines(ROOT / "scripts" / "smoke_host_install.py")
        for line in lines:
            for construct in BANNED_CONSTRUCTS_IMPORT:
                assert construct not in line.lower(), f"Smoke script imports banned construct: {construct}"

    def test_smoke_script_no_server_daemon(self):
        lines = _import_lines(ROOT / "scripts" / "smoke_host_install.py")
        for line in lines:
            assert "daemon" not in line.lower()
            assert "scheduler" not in line.lower()


class TestHostSmokeHelpersBoundaries:
    def test_host_smoke_cases_no_provider_sdks(self):
        lines = _import_lines(ROOT / "tests" / "support" / "host_smoke_cases.py")
        for line in lines:
            for sdk in BANNED_IMPORTS:
                assert sdk not in line.lower(), f"host_smoke_cases imports banned SDK: {sdk}"

    def test_host_smoke_cases_no_network_clients(self):
        source = (ROOT / "tests" / "support" / "host_smoke_cases.py").read_text(encoding="utf-8").lower()
        for banned in ["requests", "httpx", "aiohttp", "urllib3", "socket"]:
            assert banned not in source


class TestOpenCodePluginBoundaries:
    def test_plugin_no_python_spawn(self):
        source = (ROOT / "opencode.plugin.js").read_text(encoding="utf-8")
        code_lines = [
            line for line in source.splitlines()
            if not line.lstrip().startswith("//")
        ]
        code = "\n".join(code_lines).lower()
        assert "python" not in code or "python runtime" in code, (
            "OpenCode plugin must not spawn Python"
        )

    def test_plugin_no_child_process(self):
        source = (ROOT / "opencode.plugin.js").read_text(encoding="utf-8").lower()
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("//")
        )
        assert "child_process" not in code
        assert "subprocess" not in code
        assert "spawn(" not in code
        assert "shell(" not in code

    def test_plugin_no_server_daemon(self):
        source = (ROOT / "opencode.plugin.js").read_text(encoding="utf-8").lower()
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("//")
        )
        assert "daemon" not in code
        assert "scheduler" not in code
        assert "http_api" not in code


class TestRuntimeBridgeBoundaries:
    def test_runtime_bridge_remains_local_cli(self):
        lines = _import_lines(ROOT / "src" / "skillpack" / "run_skill.py")
        for line in lines:
            assert "daemon" not in line.lower()
            assert "scheduler" not in line.lower()
            assert "http_api" not in line.lower()
