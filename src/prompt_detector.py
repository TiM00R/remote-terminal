"""
Prompt Detection Module
Intelligent detection of command completion by finding shell prompts in output
Handles edge cases like prompts in output, prompt changes, background commands
"""

import re
import logging
from typing import Optional, Tuple, List
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


class PromptDetector:
    """
    Detects command completion by finding shell prompt in output
    
    Features:
    - Pattern matching with variable substitution
    - Context analysis (clean vs suspicious prompts)
    - Active verification (send Enter to confirm)
    - Prompt-changing command detection
    - Background command detection
    """
    
    def __init__(self, config: dict, ssh_manager=None):
        """
        Initialize prompt detector
        
        Args:
            config: Configuration dictionary with prompt_detection section
            ssh_manager: SSH manager for active verification (optional)
        """
        self.config = config
        self.ssh_manager = ssh_manager
        
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
        self.verification_enabled = config.get("prompt_detection", {}).get("verification_enabled", True)
        self.verification_delay = config.get("prompt_detection", {}).get("verification_delay", 0.3)
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
    
    async def verify_prompt(self, buffer, prompt_pattern: str) -> Tuple[bool, str]:
        """
        Actively verify suspicious prompt by sending Enter
        
        Args:
            buffer: Output buffer to check
            prompt_pattern: Pattern to look for
            
        Returns:
            (verified, reason) tuple
        """
        if not self.verification_enabled or not self.ssh_manager:
            return False, "verification_disabled"
        
        # Get current buffer state
        lines_before = len(buffer.buffer.lines)
        
        # Send Enter
        logger.info("Sending Enter to verify prompt")
        self.ssh_manager.send_input('\n')
        
        # Wait for response
        import asyncio
        await asyncio.sleep(self.verification_delay)
        
        # Check if new prompt appeared
        lines_after = len(buffer.buffer.lines)
        if lines_after > lines_before:
            # Check last few lines for prompt
            recent_lines = buffer.get_last_n(3)
            for line in recent_lines:
                detected, reason = self.detect_prompt_in_line(line.text, prompt_pattern)
                if detected is True:
                    return True, "verified_by_enter"
        
        return False, "verification_failed"
    
    async def check_completion(self, buffer, prompt_pattern: str) -> Tuple[bool, str]:
        """
        Check completion with clear priority order:
        1. Password prompts (HIGHEST priority - handled by is_sudo_prompt)
        2. Pager detection (quit if found)
        3. Normal prompt detection
        CRITICAL FIX: Only checks lines AFTER command_start_line to avoid
        detecting the old prompt that was in the buffer before command started.
        
        Args:
            buffer: FilteredBuffer to check
            prompt_pattern: Pattern to look for
            
        Returns:
            (completed, reason) tuple
        """
        # DIAGNOSTIC: Log what we're checking
        logger.info(f"[PROMPT CHECK] Looking for pattern: {prompt_pattern}")
        logger.info(f"[PROMPT CHECK] command_start_line: {buffer.command_start_line}")
        logger.info(f"[PROMPT CHECK] total_lines in buffer: {len(buffer.buffer.lines)}")
        
        # ========== INSERT HERE - RIGHT AFTER THE 3 LOGGER LINES ==========
        # PRIORITY CHECK: Detect and quit pagers before checking for prompts
        pager_detected, pager_type, pager_action = self.detect_pager(buffer)
        if pager_detected and pager_type not in ["password_prompt_excluded", "shell_prompt_excluded"]:
            
            if pager_action == "continue":
                # Still more output to show - send Space to continue
                logger.info(f"Pager detected ({pager_type}), sending Space to continue")
                if self.ssh_manager and self.ssh_manager.shell:
                    self.ssh_manager.shell.send(' ')  # Space bar to continue
                    import asyncio
                    await asyncio.sleep(0.2)
                    return False, f"pager_continue_{pager_type}"
            
            elif pager_action == "quit":
                # At end - send 'q' to quit and return to prompt
                logger.info(f"Pager at end ({pager_type}), sending 'q' to quit")
                if self.ssh_manager and self.ssh_manager.shell:
                    self.ssh_manager.shell.send('q')
                    import asyncio
                    await asyncio.sleep(0.2)
                    return False, f"pager_quit_{pager_type}"  
            else:
                logger.warning("Pager detected but no ssh_manager to send response.")          
        # ================================================================
            
        # CRITICAL FIX: Check the partial line first (where NEW prompt lives!)
        # The NEW completion prompt doesn't have a newline, so it stays in current_output
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output
            logger.info(f"[PROMPT CHECK] current_output: {repr(current)}")
            
            if current:
                detected, reason = self.detect_prompt_in_line(current, prompt_pattern)
                
                logger.info(f"[PROMPT CHECK] Partial line check: detected={detected}, reason={reason}")
                
                if detected is True:
                    # Clean prompt found in partial line!
                    logger.info(f"PROMPT DETECTED in partial line: {reason}")
                    return True, f"partial_line_{reason}"
                
                elif detected == "verify":
                    # Suspicious prompt in partial line - verify it
                    logger.info(f"? Suspicious prompt in partial line: {reason}, verifying...")
                    verified, verify_reason = await self.verify_prompt(buffer, prompt_pattern)
                    if verified:
                        logger.info(f"PROMPT VERIFIED: {verify_reason}")
                        return True, verify_reason
                    else:
                        logger.info(f"Verification failed: {verify_reason}")
        else:
            logger.warning("[PROMPT CHECK] Buffer doesn't have current_output attribute!")
        
        # CRITICAL FIX: Check completed lines AFTER command_start_line ONLY
        # command_start_line contains the command echo (with old prompt)
        # We want to check lines starting from command_start_line + 1
        total_lines = len(buffer.buffer.lines)
        start_checking_from = buffer.command_start_line + 1  # Skip command echo line
        
        if start_checking_from >= total_lines:
            logger.info(f"[PROMPT CHECK] No completed output lines yet (start={start_checking_from}, total={total_lines})")
            return False, "no_output_yet"
        
        # Get lines AFTER command echo
        all_lines = list(buffer.buffer.lines)
        command_output_lines = all_lines[start_checking_from:]
        
        # Check last 5 lines from command output only
        recent_lines = command_output_lines[-5:] if len(command_output_lines) > 5 else command_output_lines
        logger.info(f"[PROMPT CHECK] Checking {len(recent_lines)} recent lines from command output")
        
        for i, line in enumerate(recent_lines):
            logger.info(f"[PROMPT CHECK] Line {i}: {repr(line.text)}")
            detected, reason = self.detect_prompt_in_line(line.text, prompt_pattern)
            
            if detected is True:
                # Clean prompt found
                logger.info(f"PROMPT DETECTED in output line {i}: {reason}")
                return True, reason
            
            elif detected == "verify":
                # Suspicious prompt - verify it
                logger.info(f"? Suspicious prompt in output line {i}: {reason}, verifying...")
                verified, verify_reason = await self.verify_prompt(buffer, prompt_pattern)
                if verified:
                    logger.info(f"PROMPT VERIFIED: {verify_reason}")
                    return True, verify_reason
                else:
                    logger.info(f"Verification failed: {verify_reason}")
        
        logger.info("[PROMPT CHECK] No prompt found in command output")
        return False, "no_prompt_found"
    
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
    
    def detect_pager_old(self, buffer) -> Tuple[bool, str]:
        """
        Check if output contains pager indicators
        
        CRITICAL: Patterns designed to NOT match:
        - Shell prompts (user@host:~$)
        - Password prompts ([sudo] password:)
        
        Returns:
            (detected, pager_type) tuple
        """
        # Very specific pager patterns that WON'T match prompts/passwords
        pager_patterns = [
            # Systemctl/nmcli style: "lines 1-29" or "lines 1-29/50"
            (r'lines\s+\d+-\d+', 'systemctl_pager'),
            
            # Less at end: "(END)" with optional whitespace
            (r'\(END\)\s*$', 'less_end'),
            
            # Traditional more: "--More--" often followed by percentage
            (r'--More--', 'more_pager'),
            
            # Less prompt: ONLY if it's literally just ":" and whitespace
            # NOT "password:" or "path:"
            (r'^:\s*$', 'less_prompt'),  # Must be START of line, ONLY colon
        ]
        
        # Check current_output (partial line)
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output.strip()  # Strip for cleaner matching
            
            # SAFETY: Skip if it looks like a password prompt
            if 'password' in current.lower():
                return False, "password_prompt_excluded"
            
            # SAFETY: Skip if it looks like a shell prompt (has @ symbol)
            if '@' in current:
                return False, "shell_prompt_excluded"
            
            for pattern, pager_type in pager_patterns:
                if re.search(pattern, current, re.IGNORECASE):
                    logger.info(f"PAGER DETECTED in partial line: {pager_type} - '{current}'")
                    return True, pager_type
        
        # Check last completed line
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'lines'):
            lines_list = list(buffer.buffer.lines)
            if lines_list:
                last_line = lines_list[-1]
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_stripped = line_text.strip()
                
                # SAFETY: Skip if it looks like a password prompt
                if 'password' in line_stripped.lower():
                    return False, "password_prompt_excluded"
                
                # SAFETY: Skip if it looks like a shell prompt
                if '@' in line_stripped:
                    return False, "shell_prompt_excluded"
                
                for pattern, pager_type in pager_patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        logger.info(f"PAGER DETECTED in last line: {pager_type} - '{line_stripped}'")
                        return True, pager_type
        
        return False, "none"
    
    def detect_pager_old1(self, buffer) -> Tuple[bool, str, str]:
        """
        Check if output contains pager indicators
        
        Returns:
            (detected, pager_type, action) tuple
            - detected: True if pager found
            - pager_type: Type of pager
            - action: "continue" (send Space), "quit" (send q), "none"
        """
        pager_patterns = [
            # Pattern, pager_type, action
            (r'lines\s+\d+-\d+', 'systemctl_pager', 'continue'),  # Still more lines
            (r'\(END\)\s*$', 'less_end', 'quit'),                 # At end, quit
            (r'--More--', 'more_pager', 'continue'),              # More to show
            (r'^:\s*$', 'less_prompt', 'continue'),               # Less waiting for input
        ]
        
        # Check current_output (partial line)
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output.strip()
            
            # SAFETY: Skip if password prompt
            if 'password' in current.lower():
                return False, "password_prompt_excluded", "none"
            
            # SAFETY: Skip if shell prompt
            if '@' in current:
                return False, "shell_prompt_excluded", "none"
            
            for pattern, pager_type, action in pager_patterns:
                if re.search(pattern, current, re.IGNORECASE):
                    logger.info(f"PAGER DETECTED in partial line: {pager_type} - action={action} - '{current}'")
                    return True, pager_type, action
        
        # Check last completed line
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'lines'):
            lines_list = list(buffer.buffer.lines)
            if lines_list:
                last_line = lines_list[-1]
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_stripped = line_text.strip()
                
                # SAFETY: Skip if password prompt
                if 'password' in line_stripped.lower():
                    return False, "password_prompt_excluded", "none"
                
                # SAFETY: Skip if shell prompt
                if '@' in line_stripped:
                    return False, "shell_prompt_excluded", "none"
                
                for pattern, pager_type, action in pager_patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        logger.info(f"PAGER DETECTED in last line: {pager_type} - action={action} - '{line_stripped}'")
                        return True, pager_type, action
        
        return False, "none", "none"    
    
    
    def detect_pager(self, buffer) -> Tuple[bool, str, str]:
        """
        Check if output contains pager indicators
        
        Returns:
            (detected, pager_type, action) tuple
            - action: "continue" (send Space), "quit" (send q), "none"
        """
        # Check current_output (partial line)
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output.strip()
            
            # SAFETY: Skip if password prompt
            if 'password' in current.lower():
                return False, "password_prompt_excluded", "none"
            
            # SAFETY: Skip if shell prompt
            if '@' in current:
                return False, "shell_prompt_excluded", "none"
            
            # PRIORITY 1: Check for (END) FIRST - even if combined with lines X-Y
            if re.search(r'\(END\)', current):
                logger.info(f"PAGER at END in partial line: '{current}'")
                return True, 'less_end', 'quit'
            
            # PRIORITY 2: Check for continuation patterns
            if re.search(r'lines\s+\d+-\d+', current, re.IGNORECASE):
                logger.info(f"PAGER CONTINUE in partial line: '{current}'")
                return True, 'systemctl_pager', 'continue'
            
            if re.search(r'--More--', current):
                logger.info(f"PAGER CONTINUE (more) in partial line: '{current}'")
                return True, 'more_pager', 'continue'
            
            if re.search(r'^:\s*$', current):
                logger.info(f"PAGER CONTINUE (less prompt) in partial line: '{current}'")
                return True, 'less_prompt', 'continue'
        
        # Check last completed line
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'lines'):
            lines_list = list(buffer.buffer.lines)
            if lines_list:
                last_line = lines_list[-1]
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_stripped = line_text.strip()
                
                # SAFETY: Skip if password prompt
                if 'password' in line_stripped.lower():
                    return False, "password_prompt_excluded", "none"
                
                # SAFETY: Skip if shell prompt
                if '@' in line_stripped:
                    return False, "shell_prompt_excluded", "none"
                
                # PRIORITY 1: Check for (END) FIRST
                if re.search(r'\(END\)', line_stripped):
                    logger.info(f"PAGER at END in last line: '{line_stripped}'")
                    return True, 'less_end', 'quit'
                
                # PRIORITY 2: Check for continuation patterns
                if re.search(r'lines\s+\d+-\d+', line_stripped, re.IGNORECASE):
                    logger.info(f"PAGER CONTINUE in last line: '{line_stripped}'")
                    return True, 'systemctl_pager', 'continue'
                
                if re.search(r'--More--', line_stripped):
                    logger.info(f"PAGER CONTINUE (more) in last line: '{line_stripped}'")
                    return True, 'more_pager', 'continue'
                
                if re.search(r'^:\s*$', line_stripped):
                    logger.info(f"PAGER CONTINUE (less prompt) in last line: '{line_stripped}'")
                    return True, 'less_prompt', 'continue'
        
        return False, "none", "none" 
        
            
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

    def is_sudo_prompt(self, buffer) -> bool:
        """
        Check if current output contains sudo password prompt
        
        Args:
            buffer: FilteredBuffer to check
            
        Returns:
            True if sudo prompt detected
        """
        
        # Check partial line (current prompt area)
        if hasattr(buffer, 'current_output'):
            current = buffer.current_output.lower()
            if '[sudo] password' in current or 'password:' in current:
                logger.info(f"Sudo prompt detected in current_output: {current}")
                return True
                
        # Check ONLY the last line
        if hasattr(buffer, 'lines') and buffer.lines:
            lines_list = list(buffer.lines)        
            if lines_list:
                last_line = lines_list[-1]  # Only check the most recent line
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_lower = line_text.lower()
                if '[sudo] password' in line_lower:
                    logger.info(f"Sudo prompt detected in last line: {line_text}")
                    return True
                
        return False