"""
Conversation state management for shared terminal state
Phase 1 Enhanced: Conversation workflow automation
"""

import logging
import re
import time
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class ConversationState:
    """Manages conversation state and server tracking"""

    def __init__(self):
        """Initialize conversation state"""
        # Phase 1 Enhancement: Server-scoped conversation tracking

        self.active_conversations: Dict[str, int] = {}  # machine_id -> conversation_id
        self.current_machine_id: Optional[str] = None  # Track current machine
        # NEW: Track user's conversation mode choice per server
        # Modes: "in-conversation" (use active conversation), "no-conversation" (standalone), None (not chosen yet)
        self.conversation_modes: Dict[str, Optional[str]] = {}  # machine_id -> mode

        # NEW: Track sudo preauth timestamps per server
        self.sudo_preauth_timestamps: Dict[str, float] = {}  # machine_id -> timestamp

        self.machine_id_cache: Dict[str, str] = {}           # "host:port:user" -> "machine_id"

    def set_current_server(self, machine_id: str) -> None:
        """
        Set the current server ID

        Args:
            machine_id: Database server ID
        """
        self.current_machine_id = machine_id
        logger.debug(f"Current machine set to: {machine_id}")

    def pause_conversation(self, machine_id: str, database) -> None:
        """
        Pause active conversation for a machine

        Args:
            machine_id: Machine ID
            database: DatabaseManager instance
        """
        if machine_id in self.active_conversations:
            conversation_id = self.active_conversations[machine_id]
            if database:
                database.pause_conversation(conversation_id)
            del self.active_conversations[machine_id]
            logger.info(f"Paused conversation {conversation_id} for machine {machine_id}")

    def resume_conversation(self, machine_id: str, conversation_id: int, database) -> None:
        """
        Resume a paused conversation

        Args:
            machine_id: Machine ID
            conversation_id: Conversation ID to resume
            database: DatabaseManager instance
        """
        self.active_conversations[machine_id] = conversation_id
        if database:
            database.resume_conversation(conversation_id)
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
