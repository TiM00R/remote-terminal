"""
Shared terminal state management
Singleton state shared between MCP server and Web UI
Version 3.2 - Phase 1 Enhanced: Conversation workflow automation
CLEANED: Removed unused HistoryManager
"""

import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)
from config.config_loader import Config
from ssh.ssh_manager import SSHManager
from output.output_buffer import FilteredBuffer
from output.output_filter import SmartOutputFilter
from utils.utils import strip_ansi_codes
from command_state import CommandRegistry
from prompt.prompt_detector import PromptDetector
from database.database_manager import DatabaseManager
from state.shared_state_conversation import ConversationState
from state.shared_state_transfer import TransferState
from state.shared_state_monitor import monitor_command as _monitor_command


class SharedTerminalState:
    """
    Singleton shared state between MCP server and Web UI
    Ensures both use the same SSH connection and see the same output
    Phase 1 Enhanced: Conversation workflow automation
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config: Optional[Config] = None
        self.ssh_manager: Optional[SSHManager] = None
        self.filter: Optional[SmartOutputFilter] = None
        self.buffer: Optional[FilteredBuffer] = None
        self.command_registry: Optional[CommandRegistry] = None
        self.prompt_detector: Optional[PromptDetector] = None
        self.database: Optional[DatabaseManager] = None

        # Initialize conversation and transfer state
        self._conversation_state = ConversationState()
        self._transfer_state = TransferState()

        self.web_server_running = False
        self.output_queue = []
        self.output_lock = threading.Lock()

        self._initialized = True

    def initialize(self, config: Config):
        """Initialize shared components"""
        if self.ssh_manager is not None:
            return  # Already initialized

        self.config = config

        # Initialize filter
        self.filter = SmartOutputFilter(
            thresholds=config.claude.thresholds,
            truncation=config.claude.truncation,
            error_patterns=config.claude.error_patterns,
            auto_send_errors=config.claude.auto_send_errors
        )

        # Initialize buffer with new max_lines from config
        self.buffer = FilteredBuffer(
            max_lines=config.buffer.max_lines,
            output_filter=self.filter
        )

        # Initialize command registry
        self.command_registry = CommandRegistry(
            max_commands=config.command_execution.max_command_history
        )

        # REMOVED: HistoryManager initialization (unused - bash handles history)

        # Initialize database manager (SQLite - Phase 1)
        try:
            self.database = DatabaseManager()

            # Try to connect (non-fatal if fails)
            if self.database.connect():
                logger.info("SQLite database connection established")
            else:
                logger.warning("Database connection failed - conversation tracking disabled")
                self.database = None
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self.database = None

        # Initialize SSH manager with connection settings
        # In v3.0+, specific server details come from hosts.yaml, not config.yaml
        # Use connection settings from config, but allow empty host/user/password
        if config.remote and config.remote.host:
            # Backward compatibility: Old config.yaml with remote section
            self.ssh_manager = SSHManager(
                host=config.remote.host,
                user=config.remote.user,
                password=config.remote.password,
                port=config.remote.port,
                keepalive_interval=config.remote.keepalive_interval,
                reconnect_attempts=config.remote.reconnect_attempts,
                connection_timeout=config.remote.connection_timeout
            )
        else:
            # New v3.0+ mode: Initialize with connection settings only
            # Actual server details will be set when select_server is called
            self.ssh_manager = SSHManager(
                host="",  # Will be set by select_server
                user="",  # Will be set by select_server
                password="",  # Will be set by select_server
                port=22,
                keepalive_interval=config.connection.keepalive_interval,
                reconnect_attempts=config.connection.reconnect_attempts,
                connection_timeout=config.connection.connection_timeout
            )

        # Initialize prompt detector
        self.prompt_detector = PromptDetector(
            config=config._raw_config,
            ssh_manager=self.ssh_manager
        )

        # Set credentials for prompt detection (only if we have them)
        if config.remote and config.remote.host:
            self.prompt_detector.set_credentials(
                user=config.remote.user,
                host=config.remote.host
            )

        # Set output callback to route to output queue
        self.ssh_manager.set_output_callback(self._handle_output)

    def update_credentials(self, user: str, host: str):
        """
        Update prompt detector credentials when switching servers

        Args:
            user: New username
            host: New hostname
        """
        if self.prompt_detector:
            self.prompt_detector.set_credentials(user=user, host=host)
            logger.info(f"Updated prompt detector credentials: {user}@{host}")

        logger.info(f"DEBUG: update_credentials called with user='{user}', host='{host}'")
        if self.prompt_detector:
            logger.info(f"DEBUG: BEFORE set_credentials - prompt_detector.user='{self.prompt_detector.user}', prompt_detector.host='{self.prompt_detector.host}'")
            self.prompt_detector.set_credentials(user=user, host=host)
            logger.info(f"DEBUG: AFTER set_credentials - prompt_detector.user='{self.prompt_detector.user}', prompt_detector.host='{self.prompt_detector.host}'")
            logger.info(f"Updated prompt detector credentials: {user}@{host}")
        else:
            logger.warning("DEBUG: prompt_detector is None!")


    # Phase 1 Enhancement: Conversation state management - delegate to ConversationState

    def set_current_server(self, machine_id: str) -> None:
        """Set the current server ID"""
        self._conversation_state.set_current_server(machine_id)

    @property
    def current_machine_id(self) -> Optional[str]:
        """Get current machine ID"""
        return self._conversation_state.current_machine_id

    @current_machine_id.setter
    def current_machine_id(self, value: str) -> None:
        """Set current machine ID"""
        self._conversation_state.current_machine_id = value

    @property
    def active_conversations(self):
        """Get active conversations dict"""
        return self._conversation_state.active_conversations

    @property
    def conversation_modes(self):
        """Get conversation modes dict"""
        return self._conversation_state.conversation_modes

    @property
    def sudo_preauth_timestamps(self):
        """Get sudo preauth timestamps dict"""
        return self._conversation_state.sudo_preauth_timestamps

    @property
    def machine_id_cache(self):
        """Get machine ID cache dict"""
        return self._conversation_state.machine_id_cache

    def pause_conversation(self, machine_id: str) -> None:
        """Pause active conversation for a machine"""
        self._conversation_state.pause_conversation(machine_id, self.database)

    def resume_conversation(self, machine_id: str, conversation_id: int) -> None:
        """Resume a paused conversation"""
        self._conversation_state.resume_conversation(machine_id, conversation_id, self.database)

    def get_active_conversation_for_server(self, machine_id: str) -> Optional[int]:
        """Get active conversation ID for a server"""
        return self._conversation_state.get_active_conversation_for_server(machine_id)

    def set_active_conversation(self, machine_id: str, conversation_id: int) -> None:
        """Set active conversation for a server"""
        self._conversation_state.set_active_conversation(machine_id, conversation_id)

    def clear_active_conversation(self, machine_id: str) -> None:
        """Clear active conversation for a server"""
        self._conversation_state.clear_active_conversation(machine_id)

    def get_current_conversation_mode(self) -> Optional[str]:
        """Get conversation mode for current server"""
        return self._conversation_state.get_current_conversation_mode()

    def set_conversation_mode(self, mode: str) -> None:
        """Set conversation mode for current server"""
        self._conversation_state.set_conversation_mode(mode)

    def clear_conversation_mode(self) -> None:
        """Clear conversation mode for current machine"""
        self._conversation_state.clear_conversation_mode()

    def should_preauth_sudo(self, validity_seconds: int = 300) -> bool:
        """Check if sudo preauth is needed"""
        return self._conversation_state.should_preauth_sudo(validity_seconds)

    def mark_sudo_preauth(self) -> None:
        """Mark that sudo preauth was successful for current machine"""
        self._conversation_state.mark_sudo_preauth()

    def get_cached_machine_id(self, host: str, port: int, user: str) -> Optional[str]:
        """Get cached machine_id for connection"""
        return self._conversation_state.get_cached_machine_id(host, port, user)

    def cache_machine_id(self, host: str, port: int, user: str, machine_id: str) -> None:
        """Cache machine_id for connection (only if valid)"""
        self._conversation_state.cache_machine_id(host, port, user, machine_id)

    def clear_machine_id_cache(self, host: str = None, port: int = None, user: str = None) -> None:
        """Clear machine_id cache (all or specific connection)"""
        self._conversation_state.clear_machine_id_cache(host, port, user)

    def get_auto_conversation_id(self) -> Optional[int]:
        """Get conversation_id to auto-inject based on current mode"""
        return self._conversation_state.get_auto_conversation_id()

    @staticmethod
    def is_valid_machine_id(machine_id: str) -> bool:
        """Validate that a machine_id is legitimate"""
        return ConversationState.is_valid_machine_id(machine_id)

    def _handle_output(self, output: str):
        """
        Handle output from SSH - add to queue for web UI

        Args:
            output: Raw output from SSH (includes ANSI codes)
        """
        # Add to output queue for xterm.js
        with self.output_lock:
            self.output_queue.append(output)

        # Add to buffer (for Claude filtering) - strip ANSI for filtering
        if self.buffer:
            clean = strip_ansi_codes(output)
            self.buffer.add(clean)

    def get_output(self):
        """Get queued output for web UI"""
        with self.output_lock:
            if self.output_queue:
                output = ''.join(self.output_queue)
                self.output_queue.clear()
                return output
            return ''

    def is_connected(self) -> bool:
        """Check if connected to any server"""
        return self.ssh_manager and self.ssh_manager.is_connected()

    def connect(self) -> bool:
        """Connect to remote machine (uses current ssh_manager config)"""
        if self.ssh_manager and not self.ssh_manager.is_connected():
            return self.ssh_manager.connect()
        return True

# ========== SFTP TRANSFER TRACKING (Phase 2.5) - delegate to TransferState ==========
    def start_transfer(self, transfer_id: str, progress_dict: dict) -> None:
        """Register a new SFTP transfer"""
        web_server = self.web_server if hasattr(self, 'web_server') else None
        self._transfer_state.start_transfer(transfer_id, progress_dict, web_server)

    def update_transfer_progress(self, transfer_id: str, progress_dict: dict) -> None:
        """Update progress for an active transfer"""
        web_server = self.web_server if hasattr(self, 'web_server') else None
        self._transfer_state.update_transfer_progress(transfer_id, progress_dict, web_server)

    def complete_transfer(self, transfer_id: str, result: dict) -> None:
        """Mark a transfer as complete"""
        web_server = self.web_server if hasattr(self, 'web_server') else None
        self._transfer_state.complete_transfer(transfer_id, result, web_server)

    def get_active_transfers(self) -> dict:
        """Get all active transfers"""
        return self._transfer_state.get_active_transfers()

    @property
    def active_transfers(self):
        """Get active transfers dict"""
        return self._transfer_state.active_transfers


def monitor_command(command_id: str):
    """
    Background thread to monitor command completion

    Args:
        command_id: Command ID to monitor
    """
    _monitor_command(command_id, _shared_state)


# Global shared state
_shared_state = SharedTerminalState()

def get_shared_state() -> SharedTerminalState:
    """Get the global shared state instance"""
    return _shared_state
