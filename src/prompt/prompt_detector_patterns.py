"""
Prompt Pattern Classes
Pattern definitions and substitution logic
"""

import re
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptPattern:
    """Represents a prompt pattern with substitution variables"""
    pattern: str
    description: str

    def substitute(self, user: str, host: str) -> str:
        """
        Substitute variables in pattern

        Args:
            user: Username
            host: Hostname (can be IP or hostname)

        Returns:
            Pattern with variables substituted

        FIXED: Uses flexible pattern that matches any hostname/IP
        """
        result = self.pattern.replace("{user}", user)
        # Replace {host} with flexible pattern that matches hostname OR IP
        result = result.replace("{host}", r"[a-zA-Z0-9\-\.]+")
        return result


@dataclass
class PromptChangingCommand:
    """Command that changes the shell prompt"""
    command: str
    new_pattern: str
    description: str


class PromptPatternManager:
    """Manages prompt patterns and pattern-related operations"""

    def __init__(self, config: dict):
        """
        Initialize pattern manager

        Args:
            config: Configuration dictionary with prompt_detection section
        """
        self.config = config

        # Load prompt patterns
        patterns_config = config.get("prompt_detection", {}).get("patterns", [])
        self.patterns = [
            PromptPattern(pattern=p, description=f"Pattern: {p}")
            for p in patterns_config
        ]

        # Load prompt-changing commands
        pcc_config = config.get("prompt_detection", {}).get("prompt_changing_commands", [])
        self.prompt_changing_commands = [
            PromptChangingCommand(
                command=pcc["command"],
                new_pattern=pcc["new_pattern"],
                description=pcc.get("description", "")
            )
            for pcc in pcc_config
        ]

        # Settings
        self.background_pattern = config.get("prompt_detection", {}).get("background_command_pattern", r"&\s*$")

        self.user = None
        self.host = None

    def set_credentials(self, user: str, host: str):
        """Set user and host for pattern substitution"""
        self.user = user
        self.host = host

    def get_prompt_patterns(self) -> List[str]:
        """
        Get list of prompt patterns with substituted variables

        Returns:
            List of regex pattern strings
        """
        if not self.user or not self.host:
            logger.warning("User/host not set for prompt detection")
            return []

        return [
            pattern.substitute(self.user, self.host)
            for pattern in self.patterns
        ]

    def detect_prompt_in_line(self, line: str, prompt_pattern: str) -> Tuple[bool, str]:
        """
        Detect if line contains prompt pattern

        Args:
            line: Line to check
            prompt_pattern: Regex pattern to match

        Returns:
            (detected, reason) tuple
            - detected: True if prompt found, "verify" if suspicious, False otherwise
            - reason: Description of detection result
        """
        try:
            if not re.search(prompt_pattern, line):
                return False, "not_found"
        except re.error as e:
            logger.error(f"Invalid regex pattern '{prompt_pattern}': {e}")
            return False, "invalid_pattern"

        # CASE 1: Clean prompt (line is just the prompt)
        # Example: "user@host:~$"
        if line.strip() == prompt_pattern.strip() or re.fullmatch(prompt_pattern, line.strip()):
            return True, "clean_prompt"

        # Extract prompt match
        match = re.search(prompt_pattern, line)
        if not match:
            return False, "not_found"

        before = line[:match.start()]
        after = line[match.end():]

        # CASE 2: Prompt at start of line, nothing after
        # Example: "user@host:~$  \n"
        if not before and not after.strip():
            return True, "start_of_line"

        # CASE 3: Prompt at end of line, nothing after
        # Example: "some outputuser@host:~$"
        if not after.strip():
            # Check if there's non-whitespace before prompt
            if before and before.strip():
                return "verify", "suspicious_text_before"
            else:
                return True, "end_of_line"

        # CASE 4: Text after prompt - suspicious
        # Example: "user@host:~$ is the prompt"
        if after.strip():
            return "verify", "suspicious_text_after"

        return False, "unknown"

    def detect_prompt_changing_command(self, command: str) -> Optional[str]:
        """
        Check if command changes the prompt

        Args:
            command: Command to check

        Returns:
            New prompt pattern if command changes prompt, None otherwise
        """
        cmd_stripped = command.strip()

        for pcc in self.prompt_changing_commands:
            if cmd_stripped.startswith(pcc.command):
                # Substitute variables
                if self.user and self.host:
                    new_pattern = pcc.new_pattern.replace("{user}", self.user)
                    new_pattern = new_pattern.replace("{host}", r"[a-zA-Z0-9\-\.]+")
                    return new_pattern
                else:
                    return pcc.new_pattern

        return None

    def is_background_command(self, command: str) -> bool:
        """
        Check if command is backgrounded with &

        Args:
            command: Command to check

        Returns:
            True if command ends with &
        """
        return bool(re.search(self.background_pattern, command.strip()))

    def get_current_prompt(self) -> str:
        """
        Get the most likely current prompt pattern

        Returns:
            Regex pattern for current prompt
        """
        patterns = self.get_prompt_patterns()
        if patterns:
            # Return first (most common) pattern
            return patterns[0]
        else:
            # Fallback - flexible pattern that matches any user@host:path$
            return r"[a-zA-Z0-9_]+@[a-zA-Z0-9\-\.]+:.*[$#]\s*$"
