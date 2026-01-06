"""
Configuration Management
Loads and validates configuration from YAML file
Version 3.0 - Multi-Server Support
"""

import logging

logger = logging.getLogger(__name__)

from config.config_dataclasses import (
    ConnectionConfig, RemoteConfig, CommandExecutionConfig, PromptDetectionConfig,
    BufferConfig, TerminalConfig, HistoryConfig, ShortcutsConfig, SearchConfig,
    OutputModesConfig, ClaudeConfig, ServerConfig, LoggingConfig
)
from config.config_loader import Config
