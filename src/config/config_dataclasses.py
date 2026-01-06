"""
Configuration Dataclasses
All configuration dataclass definitions
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ConnectionConfig:
    """Connection management configuration (applies to all servers)"""
    keepalive_interval: int = 30
    reconnect_attempts: int = 3
    connection_timeout: int = 10


@dataclass
class RemoteConfig:
    """DEPRECATED: Remote machine connection configuration
    Kept for backward compatibility. Use hosts.yaml instead.
    """
    host: str = ""
    user: str = ""
    password: str = ""
    port: int = 22
    keepalive_interval: int = 30
    reconnect_attempts: int = 3
    connection_timeout: int = 10


@dataclass
class CommandExecutionConfig:
    """Command execution configuration"""
    default_timeout: int = 10  # CHANGED: 30 → 10
    max_timeout: int = 3600
    prompt_grace_period: float = 0.3
    check_interval: float = 0.5
    max_command_history: int = 50
    cleanup_interval: int = 300
    warn_on_long_timeout: int = 60


@dataclass
class PromptDetectionConfig:
    """Prompt detection configuration"""
    patterns: list = None
    verification_enabled: bool = True
    verification_delay: float = 0.3
    prompt_changing_commands: list = None
    background_command_pattern: str = r"&\s*$"
    warn_on_background: bool = True

    def __post_init__(self):
        if self.patterns is None:
            self.patterns = [
                "{user}@{host}:~$",
                "{user}@{host}:.*[$#]",
                "root@{host}:~#",
                "root@{host}:.*#"
            ]
        if self.prompt_changing_commands is None:
            self.prompt_changing_commands = [
                {"command": "sudo su", "new_pattern": "root@{host}:.*[#$]"},
                {"command": "sudo -i", "new_pattern": "root@{host}:.*[#$]"},
                {"command": "su", "new_pattern": ".*@.*[#$]"},
                {"command": "ssh", "new_pattern": ".*@.*[$#]"},
                {"command": "docker exec", "new_pattern": ".*[@#]"}
            ]


@dataclass
class BufferConfig:
    """Output buffer configuration"""
    max_lines: int = 10000
    cleanup_on_full: bool = True


@dataclass
class TerminalConfig:
    """Terminal display configuration"""
    scrollback_lines: int = 1000
    theme: str = "dark"
    font_size: int = 14
    font_family: str = "Consolas, Monaco, monospace"
    cursor_blink: bool = True
    cursor_style: str = "block"


@dataclass
class HistoryConfig:
    """Command history configuration"""
    enabled: bool = True
    file: str = "~/.remote_terminal_history"
    max_commands: int = 1000
    save_on_exit: bool = True
    load_on_start: bool = True


@dataclass
class ShortcutsConfig:
    """Keyboard shortcuts configuration"""
    copy: str = "Ctrl+C"
    paste: str = "Ctrl+V"
    clear: str = "Ctrl+L"
    search: str = "Ctrl+F"
    interrupt: str = "Ctrl+C"
    history_previous: str = "ArrowUp"
    history_next: str = "ArrowDown"
    history_search: str = "Ctrl+R"


@dataclass
class SearchConfig:
    """Search configuration"""
    case_sensitive: bool = True
    highlight_color: str = "#ffff00"
    wrap_around: bool = True


@dataclass
class OutputModesConfig:
    """Output modes configuration for Claude integration"""
    full_output_threshold: int = 100
    preview_head_lines: int = 10
    preview_tail_lines: int = 10
    installation_summary_lines: int = 10  # Last N lines for successful installations
    max_error_contexts: int = 10          # Maximum errors to return with context
    summary_mode_commands: list = None
    analysis_commands: list = None

    def __post_init__(self):
        # Default commands that produce large output
        if self.summary_mode_commands is None:
            self.summary_mode_commands = [
                "apt", "apt-get", "yum", "dnf",
                "pip install", "npm install", "yarn install",
                "make", "cargo build", "docker build",
                "mvn", "gradle", "composer install", "composer update"
            ]

        # Default commands where full output needed
        if self.analysis_commands is None:
            self.analysis_commands = [
                "grep", "awk", "sed", "find", "jq", "locate"
            ]


@dataclass
class ClaudeConfig:
    """Claude AI integration configuration"""
    auto_send_errors: bool = True
    output_modes: OutputModesConfig = None
    thresholds: Dict[str, int] = None
    truncation: Dict[str, int] = None
    error_patterns: list = None

    def __post_init__(self):
        # Initialize output_modes
        if self.output_modes is None:
            self.output_modes = OutputModesConfig()

        # Default thresholds
        default_thresholds = {
            "system_info": 50,
            "network_info": 100,
            "file_listing": 50,
            "file_viewing": 100,
            "install": 100,
            "generic": 50
        }

        # Merge with defaults instead of replacing
        if self.thresholds is None:
            self.thresholds = default_thresholds
        else:
            self.thresholds = {**default_thresholds, **self.thresholds}

        # Default truncation
        default_truncation = {
            "head_lines": 30,
            "tail_lines": 20
        }

        if self.truncation is None:
            self.truncation = default_truncation
        else:
            self.truncation = {**default_truncation, **self.truncation}

        # Default error patterns - comprehensive
        if self.error_patterns is None:
            self.error_patterns = [
                "ERROR", "FAILED", "FATAL", "Cannot",
                "Permission denied", "No such file", "command not found",
                "error:", "Error:", "E:",
                "failed", "Failed", "fatal", "Fatal",
                "unable to", "Unable to", "could not", "Could not",
                "cannot", "Can't", "can't", "Couldn't", "couldn't",
                "not found", "Not found", "Err:",
                "Aborting", "aborting", "denied", "Denied"
            ]


@dataclass
class ServerConfig:
    """Web server configuration"""
    host: str = "localhost"
    port: int = 8080
    auto_open_browser: bool = True
    debug: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: str = "remote_terminal.log"
    max_size_mb: int = 10
    backup_count: int = 3
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
