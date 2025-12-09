"""
Shared terminal state management
Singleton state shared between MCP server and Web UI
Version 3.2 - Phase 1 Enhanced: Conversation workflow automation
CLEANED: Removed unused HistoryManager
"""

import asyncio
import os
import re
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)
from config import Config
from ssh_manager import SSHManager
from output_buffer import FilteredBuffer
from output_filter import SmartOutputFilter
from utils import strip_ansi_codes
from command_state import CommandState, generate_command_id, CommandRegistry
from prompt_detector import PromptDetector
from database_manager import DatabaseManager


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
        
        # Phase 1 Enhancement: Server-scoped conversation tracking
        
        self.active_conversations: Dict[str, int] = {}  # machine_id -> conversation_id
        self.current_machine_id: Optional[str] = None  # Track current machine
        # NEW: Track user's conversation mode choice per server
        # Modes: "in-conversation" (use active conversation), "no-conversation" (standalone), None (not chosen yet)
        self.conversation_modes: Dict[str, Optional[str]] = {}  # machine_id -> mode
        
        self.web_server_running = False
        self.output_queue = []
        self.output_lock = threading.Lock()
        # NEW: Track sudo preauth timestamps per server
        self.sudo_preauth_timestamps: Dict[str, float] = {}  # machine_id -> timestamp
        
        self.machine_id_cache: Dict[str, str] = {}           # "host:port:user" -> "machine_id"
        self._initialized = True
        # SFTP Transfer tracking (Phase 2.5)
        self.active_transfers: Dict[str, Dict] = {}  # transfer_id -> progress_dict
        self._transfer_lock = threading.Lock()
            
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
        
        
    # Phase 1 Enhancement: Conversation state management

    def set_current_server(self, machine_id: str) -> None:
        """
        Set the current server ID
        
        Args:
            machine_id: Database server ID
        """
        self.current_machine_id = machine_id
        logger.debug(f"Current machine set to: {machine_id}")

    def pause_conversation(self, machine_id: str) -> None:
        """
        Pause active conversation for a machine

        Args:
            machine_id: Machine ID
        """
        if machine_id in self.active_conversations:
            conversation_id = self.active_conversations[machine_id]
            if self.database:
                self.database.pause_conversation(conversation_id)
            del self.active_conversations[machine_id]
            logger.info(f"Paused conversation {conversation_id} for machine {machine_id}")

    def resume_conversation(self, machine_id: str, conversation_id: int) -> None:
        """
        Resume a paused conversation
        
        Args:
            machine_id: Machine ID
            conversation_id: Conversation ID to resume
        """
        self.active_conversations[machine_id] = conversation_id
        if self.database:
            self.database.resume_conversation(conversation_id)
        logger.info(f"Resumed conversation {conversation_id} for machine {machine_id}")

    def get_active_conversation_for_server(self, machine_id: str) -> Optional[int]:
        """
        Get active conversation ID for a server
        
        Args:
            machine_id: Machine ID
            
        Returns:
            Conversation ID or None
        """
        return self.active_conversations.get(machine_id)

    def set_active_conversation(self, machine_id: str, conversation_id: int) -> None:
        """
        Set active conversation for a server
        
        Args:
            machine_id: Machine ID
            conversation_id: Conversation ID
        """
        self.active_conversations[machine_id] = conversation_id
        self.conversation_modes[machine_id] = "in-conversation"
        logger.debug(f"Set active conversation {conversation_id} for machine {machine_id}")

    def clear_active_conversation(self, machine_id: str) -> None:
        """
        Clear active conversation for a server
        
        Args:
            machine_id: Machine ID
        """
        if machine_id in self.active_conversations:
            del self.active_conversations[machine_id]
        self.conversation_modes[machine_id] = "no-conversation"
        logger.debug(f"Cleared active conversation for machine {machine_id}")
    
    # NEW: Conversation mode management
    
    def get_current_conversation_mode(self) -> Optional[str]:
        """
        Get conversation mode for current server
        
        Returns:
            "in-conversation", "no-conversation", or None if not chosen yet
        """
        if not self.current_machine_id:
            return None
        return self.conversation_modes.get(self.current_machine_id)

    def set_conversation_mode(self, mode: str) -> None:
        """
        Set conversation mode for current server
        
        Args:
            mode: "in-conversation" or "no-conversation"
        """
        if self.current_machine_id:
            self.conversation_modes[self.current_machine_id] = mode
            logger.debug(f"Set conversation mode to '{mode}' for machine {self.current_machine_id}")

    def clear_conversation_mode(self) -> None:
        """Clear conversation mode for current machine (requires re-asking user)"""
        if self.current_machine_id and self.current_machine_id in self.conversation_modes:
            del self.conversation_modes[self.current_machine_id]
            logger.debug(f"Cleared conversation mode for machine {self.current_machine_id}")


    # ========== ADD THESE TWO NEW METHODS HERE ==========
    def should_preauth_sudo(self, validity_seconds: int = 300) -> bool:
        """
        Check if sudo preauth is needed
        
        Args:
            validity_seconds: How long preauth is valid (default 300 = 5 minutes)
            
        Returns:
            True if preauth needed, False if still valid
        """
        if not self.current_machine_id:
            return True  # No machine context, preauth needed

        last_preauth = self.sudo_preauth_timestamps.get(self.current_machine_id)
        if not last_preauth:
            return True  # Never preauthenticated
        
        elapsed = time.time() - last_preauth
        return elapsed >= validity_seconds

    def mark_sudo_preauth(self) -> None:
        """Mark that sudo preauth was successful for current machine"""
        if self.current_machine_id:
            self.sudo_preauth_timestamps[self.current_machine_id] = time.time()
            logger.debug(f"Marked sudo preauth for machine {self.current_machine_id}")
    # ========== END NEW METHODS ==========


    def get_cached_machine_id(self, host: str, port: int, user: str) -> Optional[str]:
        """Get cached machine_id for connection"""
        cache_key = f"{host}:{port}:{user}"
        return self.machine_id_cache.get(cache_key)

    def cache_machine_id(self, host: str, port: int, user: str, machine_id: str) -> None:
        """Cache machine_id for connection (only if valid)"""
        # Only cache valid machine IDs
        if not self.is_valid_machine_id(machine_id):
            logger.warning(f"Refusing to cache invalid machine_id: {machine_id}")
            return
            
        cache_key = f"{host}:{port}:{user}"
        self.machine_id_cache[cache_key] = machine_id
        logger.debug(f"Cached machine_id for {cache_key}: {machine_id[:16]}...")

    def clear_machine_id_cache(self, host: str = None, port: int = None, user: str = None) -> None:
        """Clear machine_id cache (all or specific connection)"""
        if host is None:
            self.machine_id_cache.clear()
            logger.debug("Cleared all machine_id cache")
        else:
            cache_key = f"{host}:{port}:{user}"
            if cache_key in self.machine_id_cache:
                del self.machine_id_cache[cache_key]
                logger.debug(f"Cleared machine_id cache for {cache_key}")

    def get_auto_conversation_id(self) -> Optional[int]:
        """
        Get conversation_id to auto-inject based on current mode
        
        Returns:
            Conversation ID if in "in-conversation" mode, None otherwise
        """
        if not self.current_machine_id:
            return None

        mode = self.conversation_modes.get(self.current_machine_id)
        if mode == "in-conversation":
            return self.active_conversations.get(self.current_machine_id)

        return None
    
    @staticmethod
    def is_valid_machine_id(machine_id: str) -> bool:
        """
        Validate that a machine_id is legitimate, not a fallback or random string
        
        Args:
            machine_id: The machine_id to validate
            
        Returns:
            True if valid, False if fallback/invalid
        """
        if not machine_id:
            return False
        
        # Check if it's a fallback ID
        if machine_id.startswith(('unknown-', 'error-')):
            logger.debug(f"Invalid machine_id: starts with fallback prefix")
            return False
        
        # Valid machine-id is exactly 32 hex characters
        if not re.match(r'^[a-f0-9]{32}$', machine_id):
            logger.debug(f"Invalid machine_id: not 32 hex chars")
            return False
        
        # Additional checks: machine-id shouldn't be all zeros or all f's
        if machine_id == '0' * 32 or machine_id == 'f' * 32:
            logger.debug(f"Invalid machine_id: suspicious pattern (all zeros or f's)")
            return False
        
        return True
    
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

# ========== SFTP TRANSFER TRACKING (Phase 2.5) ==========
    def start_transfer(self, transfer_id: str, progress_dict: Dict) -> None:
        """Register a new SFTP transfer"""
        with self._transfer_lock:
            self.active_transfers[transfer_id] = progress_dict
        
        logger.info(f"Started tracking transfer {transfer_id}")
        
        # Broadcast to web terminal if available
        if hasattr(self, 'web_server') and self.web_server:
            try:
                import asyncio
                asyncio.create_task(
                    self.web_server.broadcast_transfer_update(transfer_id, progress_dict)
                )
            except Exception as e:
                logger.error(f"Failed to broadcast transfer start: {e}")

    def update_transfer_progress(self, transfer_id: str, progress_dict: Dict) -> None:
        """Update progress for an active transfer"""
        with self._transfer_lock:
            if transfer_id in self.active_transfers:
                self.active_transfers[transfer_id].update(progress_dict)
            else:
                self.active_transfers[transfer_id] = progress_dict
        
        # Broadcast to web terminal if available
        if hasattr(self, 'web_server') and self.web_server:
            try:
                import asyncio
                asyncio.create_task(
                    self.web_server.broadcast_transfer_update(transfer_id, progress_dict)
                )
            except Exception as e:
                logger.debug(f"Could not broadcast transfer update: {e}")

    def complete_transfer(self, transfer_id: str, result: Dict) -> None:
        """Mark a transfer as complete"""
        with self._transfer_lock:
            if transfer_id in self.active_transfers:
                self.active_transfers[transfer_id].update({
                    'status': result.get('status', 'completed'),
                    'completed_at': time.time(),
                    'result': result
                })
        
        logger.info(f"Transfer {transfer_id} completed")
        
        # Broadcast final update
        if hasattr(self, 'web_server') and self.web_server:
            try:
                import asyncio
                asyncio.create_task(
                    self.web_server.broadcast_transfer_update(
                        transfer_id, 
                        self.active_transfers.get(transfer_id, {})
                    )
                )
            except Exception as e:
                logger.error(f"Failed to broadcast transfer completion: {e}")
        
        # Schedule cleanup after 10 seconds
        def cleanup():
            time.sleep(10)
            with self._transfer_lock:
                if transfer_id in self.active_transfers:
                    del self.active_transfers[transfer_id]
        
        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()

    def get_active_transfers(self) -> Dict[str, Dict]:
        """Get all active transfers"""
        with self._transfer_lock:
            return self.active_transfers.copy()


def monitor_command(command_id: str):
    """
    Background thread to monitor command completion
    
    CRITICAL: Continues monitoring even after timeout until:
    - Prompt detected (completed/cancelled)
    - cancel_command() called (killed)
    - Max monitoring time reached (1 hour)
    
    Detects Ctrl+C (^C in output) and marks as cancelled vs completed
    
    Args:
        command_id: Command ID to monitor
    """
    state = _shared_state.command_registry.get(command_id)
    if not state:
        logger.error(f"Command {command_id} not found in registry")
        return
    
    check_interval = _shared_state.config.command_execution.check_interval
    prompt_pattern = state.expected_prompt
    max_monitoring_time = _shared_state.config.command_execution.max_timeout
    
    logger.debug(f"Monitoring command {command_id}: {state.command[:50]}...")
    
    # CRITICAL: Continue monitoring while is_running() returns True
    # This includes both "running" and "timeout_still_running" states
    
    # Add this BEFORE the while loop starts
    last_sudo_response_line_count = 0  # Track buffer size when we last responded to sudo

    while state.is_running():
        time.sleep(check_interval)
        
        # NEW CODE - Check for sudo password prompt
        if _shared_state.prompt_detector.is_sudo_prompt(_shared_state.buffer.buffer):
            current_line_count = len(_shared_state.buffer.buffer.lines)
            
            # Only respond if buffer has grown since last response (new prompt, not same one)
            if current_line_count > last_sudo_response_line_count:
                if _shared_state.ssh_manager.password:
                    logger.info(f"Auto-responding to sudo password prompt, current_line_count={current_line_count}, last_sudo_response_line_count={last_sudo_response_line_count} ")
                    _shared_state.ssh_manager.shell.send(_shared_state.ssh_manager.password + '\n')
                    last_sudo_response_line_count = current_line_count  # Remember this line count
                    time.sleep(0.5)  # Wait for password to be processed
                    continue  # Skip to next iteration
        # END NEW CODE
            
        # Check for max monitoring time (1 hour default)
        if state.duration() >= max_monitoring_time:
            buffer_end_line = len(_shared_state.buffer.buffer.lines)
            state.mark_max_timeout(buffer_end_line)
            logger.warning(f"Command {command_id} exceeded max monitoring time ({max_monitoring_time}s)")
            break
        
        # Check for prompt in buffer
        try:
            # Run async check in sync context
            loop = asyncio.new_event_loop()
            completed, reason = loop.run_until_complete(
                _shared_state.prompt_detector.check_completion(
                    _shared_state.buffer,
                    prompt_pattern
                )
            )
            loop.close()
            
            if completed:
                # Prompt detected! Check if it was due to Ctrl+C
                buffer_end_line = len(_shared_state.buffer.buffer.lines)
                
                # Check recent output for ^C (Ctrl+C character)
                # Get last few lines before prompt
                recent_output = _shared_state.buffer.buffer.get_text(
                    start=max(0, buffer_end_line - 5),
                    end=buffer_end_line
                )
                
                # Also check current_output (partial line with prompt)
                if hasattr(_shared_state.buffer.buffer, 'current_output'):
                    recent_output += _shared_state.buffer.buffer.current_output
                
                # Detect Ctrl+C in output
                if '^C' in recent_output:
                    # Command was interrupted with Ctrl+C
                    state.mark_cancelled(buffer_end_line)
                    logger.info(f"Command {command_id} cancelled (Ctrl+C detected) after {state.duration():.1f}s")
                else:
                    # Command completed naturally
                    state.mark_completed(buffer_end_line)
                    logger.info(f"Command {command_id} completed ({reason}) after {state.duration():.1f}s")
                break
                
        except Exception as e:
            logger.error(f"Error monitoring command {command_id}: {e}")
            break
    
    logger.debug(f"Stopped monitoring command {command_id} (status: {state.status})")
    

# Global shared state
_shared_state = SharedTerminalState()

def get_shared_state() -> SharedTerminalState:
    """Get the global shared state instance"""
    return _shared_state
