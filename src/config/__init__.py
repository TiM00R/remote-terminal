"""Configuration management module"""

from .config_dataclasses import (
    ConnectionConfig, RemoteConfig, CommandExecutionConfig, PromptDetectionConfig,
    BufferConfig, TerminalConfig, HistoryConfig, ShortcutsConfig, SearchConfig,
    OutputModesConfig, ClaudeConfig, ServerConfig, LoggingConfig
)
from .config_loader import Config
from .config_init import get_config_root, get_package_config_dir, ensure_config_files

__all__ = [
    'ConnectionConfig',
    'RemoteConfig',
    'CommandExecutionConfig',
    'PromptDetectionConfig',
    'BufferConfig',
    'TerminalConfig',
    'HistoryConfig',
    'ShortcutsConfig',
    'SearchConfig',
    'OutputModesConfig',
    'ClaudeConfig',
    'ServerConfig',
    'LoggingConfig',
    'Config',
    'get_config_root',
    'get_package_config_dir',
    'ensure_config_files'
]
