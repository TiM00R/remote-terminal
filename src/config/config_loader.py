"""
Configuration Loader
Main configuration class with loading and parsing logic
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from .config_dataclasses import (
    ConnectionConfig, RemoteConfig, CommandExecutionConfig, PromptDetectionConfig,
    BufferConfig, TerminalConfig, HistoryConfig, ShortcutsConfig, SearchConfig,
    OutputModesConfig, ClaudeConfig, ServerConfig, LoggingConfig
)

logger = logging.getLogger(__name__)


class Config:
    """Main configuration class"""

    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self._raw_config: Dict[str, Any] = {}

        # Configuration sections
        self.connection: Optional[ConnectionConfig] = None
        self.remote: Optional[RemoteConfig] = None  # Deprecated, kept for compatibility
        self.command_execution: Optional[CommandExecutionConfig] = None
        self.prompt_detection: Optional[PromptDetectionConfig] = None
        self.buffer: Optional[BufferConfig] = None
        self.terminal: Optional[TerminalConfig] = None
        self.history: Optional[HistoryConfig] = None
        self.shortcuts: Optional[ShortcutsConfig] = None
        self.search: Optional[SearchConfig] = None
        self.claude: Optional[ClaudeConfig] = None
        self.server: Optional[ServerConfig] = None
        self.logging: Optional[LoggingConfig] = None

        self.load()

    def load(self) -> None:
        """Load configuration from YAML file"""
        config_path = Path(self.config_file)

        if not config_path.exists():
            logger.warning(f"Config file not found: {self.config_file}, using defaults")
            self._load_defaults()
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._raw_config = yaml.safe_load(f) or {}

            self._parse_config()
            logger.info(f"Configuration loaded from {self.config_file}")

        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self._load_defaults()

    def _parse_config(self) -> None:
        """Parse configuration into dataclass objects"""

        # NEW: Connection configuration (v3.0+)
        connection_data = self._raw_config.get('connection', {})
        self.connection = ConnectionConfig(
            keepalive_interval=connection_data.get('keepalive_interval', 30),
            reconnect_attempts=connection_data.get('reconnect_attempts', 3),
            connection_timeout=connection_data.get('connection_timeout', 10)
        )

        # DEPRECATED: Remote configuration (backward compatibility)
        # If 'remote' section exists, load it; otherwise create empty
        remote_data = self._raw_config.get('remote', {})
        if remote_data:
            logger.warning("'remote' section in config.yaml is deprecated. Use hosts.yaml for server configuration.")
            self.remote = RemoteConfig(
                host=remote_data.get('host', ''),
                user=remote_data.get('user', ''),
                password=remote_data.get('password', ''),
                port=remote_data.get('port', 22),
                keepalive_interval=remote_data.get('keepalive_interval', self.connection.keepalive_interval),
                reconnect_attempts=remote_data.get('reconnect_attempts', self.connection.reconnect_attempts),
                connection_timeout=remote_data.get('connection_timeout', self.connection.connection_timeout)
            )
        else:
            # No remote section - this is expected in v3.0+
            self.remote = RemoteConfig()  # Empty remote config

        # Command execution configuration
        cmd_exec_data = self._raw_config.get('command_execution', {})
        self.command_execution = CommandExecutionConfig(
            default_timeout=cmd_exec_data.get('default_timeout', 10),
            max_timeout=cmd_exec_data.get('max_timeout', 3600),
            prompt_grace_period=cmd_exec_data.get('prompt_grace_period', 0.3),
            check_interval=cmd_exec_data.get('check_interval', 0.5),
            max_command_history=cmd_exec_data.get('max_command_history', 50),
            cleanup_interval=cmd_exec_data.get('cleanup_interval', 300),
            warn_on_long_timeout=cmd_exec_data.get('warn_on_long_timeout', 60)
        )

        # Prompt detection configuration
        prompt_data = self._raw_config.get('prompt_detection', {})
        self.prompt_detection = PromptDetectionConfig(
            patterns=prompt_data.get('patterns'),
            verification_enabled=prompt_data.get('verification_enabled', True),
            verification_delay=prompt_data.get('verification_delay', 0.3),
            prompt_changing_commands=prompt_data.get('prompt_changing_commands'),
            background_command_pattern=prompt_data.get('background_command_pattern', r"&\s*$"),
            warn_on_background=prompt_data.get('warn_on_background', True)
        )

        # Buffer configuration
        buffer_data = self._raw_config.get('buffer', {})
        self.buffer = BufferConfig(
            max_lines=buffer_data.get('max_lines', 10000),
            cleanup_on_full=buffer_data.get('cleanup_on_full', True)
        )

        # Terminal configuration
        terminal_data = self._raw_config.get('terminal', {})
        self.terminal = TerminalConfig(
            scrollback_lines=terminal_data.get('scrollback_lines', 1000),
            theme=terminal_data.get('theme', 'dark'),
            font_size=terminal_data.get('font_size', 14),
            font_family=terminal_data.get('font_family', 'Consolas, Monaco, monospace'),
            cursor_blink=terminal_data.get('cursor_blink', True),
            cursor_style=terminal_data.get('cursor_style', 'block')
        )

        # History configuration
        history_data = self._raw_config.get('history', {})
        self.history = HistoryConfig(
            enabled=history_data.get('enabled', True),
            file=history_data.get('file', '~/.remote_terminal_history'),
            max_commands=history_data.get('max_commands', 1000),
            save_on_exit=history_data.get('save_on_exit', True),
            load_on_start=history_data.get('load_on_start', True)
        )

        # Shortcuts configuration
        shortcuts_data = self._raw_config.get('shortcuts', {})
        self.shortcuts = ShortcutsConfig(
            copy=shortcuts_data.get('copy', 'Ctrl+C'),
            paste=shortcuts_data.get('paste', 'Ctrl+V'),
            clear=shortcuts_data.get('clear', 'Ctrl+L'),
            search=shortcuts_data.get('search', 'Ctrl+F'),
            interrupt=shortcuts_data.get('interrupt', 'Ctrl+C'),
            history_previous=shortcuts_data.get('history_previous', 'ArrowUp'),
            history_next=shortcuts_data.get('history_next', 'ArrowDown'),
            history_search=shortcuts_data.get('history_search', 'Ctrl+R')
        )

        # Search configuration
        search_data = self._raw_config.get('search', {})
        self.search = SearchConfig(
            case_sensitive=search_data.get('case_sensitive', True),
            highlight_color=search_data.get('highlight_color', '#ffff00'),
            wrap_around=search_data.get('wrap_around', True)
        )

        # Claude configuration
        claude_data = self._raw_config.get('claude', {})

        # Parse output_modes
        output_modes_data = claude_data.get('output_modes', {})
        output_modes = OutputModesConfig(
            full_output_threshold=output_modes_data.get('full_output_threshold', 100),
            preview_head_lines=output_modes_data.get('preview_head_lines', 10),
            preview_tail_lines=output_modes_data.get('preview_tail_lines', 10),
            installation_summary_lines=output_modes_data.get('installation_summary_lines', 10),
            max_error_contexts=output_modes_data.get('max_error_contexts', 10),
            summary_mode_commands=output_modes_data.get('summary_mode_commands'),
            analysis_commands=output_modes_data.get('analysis_commands')
        )

        self.claude = ClaudeConfig(
            auto_send_errors=claude_data.get('auto_send_errors', True),
            output_modes=output_modes,
            thresholds=claude_data.get('thresholds'),
            truncation=claude_data.get('truncation'),
            error_patterns=claude_data.get('error_patterns')
        )

        # Server configuration
        server_data = self._raw_config.get('server', {})
        self.server = ServerConfig(
            host=server_data.get('host', 'localhost'),
            port=server_data.get('port', 8080),
            auto_open_browser=server_data.get('auto_open_browser', True),
            debug=server_data.get('debug', False)
        )

        # Logging configuration
        logging_data = self._raw_config.get('logging', {})
        self.logging = LoggingConfig(
            level=logging_data.get('level', 'INFO'),
            file=logging_data.get('file', 'remote_terminal.log'),
            max_size_mb=logging_data.get('max_size_mb', 10),
            backup_count=logging_data.get('backup_count', 3),
            format=logging_data.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )

    def _load_defaults(self) -> None:
        """Load default configuration"""
        self.connection = ConnectionConfig()
        self.remote = RemoteConfig()  # Empty remote config
        self.command_execution = CommandExecutionConfig()
        self.prompt_detection = PromptDetectionConfig()
        self.buffer = BufferConfig()
        self.terminal = TerminalConfig()
        self.history = HistoryConfig()
        self.shortcuts = ShortcutsConfig()
        self.search = SearchConfig()
        self.claude = ClaudeConfig()
        self.server = ServerConfig()
        self.logging = LoggingConfig()

    def validate(self) -> bool:
        """Validate configuration - no longer requires remote config"""
        # In v3.0+, remote section is optional (servers in hosts.yaml)
        # Only validate other critical settings

        errors = []

        # Validate numeric ranges
        if self.command_execution.default_timeout <= 0:
            errors.append("default_timeout must be positive")
        if self.command_execution.max_timeout < self.command_execution.default_timeout:
            errors.append("max_timeout must be >= default_timeout")

        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False

        return True

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key"""
        keys = key.split('.')
        value = self._raw_config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default
