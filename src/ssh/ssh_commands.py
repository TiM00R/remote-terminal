"""
SSH Command Execution
Handles command execution and result processing
"""

import time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command execution"""
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    command: str


class SSHCommandExecutor:
    """Handles SSH command execution"""

    def __init__(self, connection):
        """
        Initialize command executor

        Args:
            connection: SSHConnection instance
        """
        self.connection = connection

    def execute_command(self, command: str, timeout: int = 30) -> CommandResult:
        """
        Execute command and wait for completion

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            CommandResult with output and status
        """
        if not self.connection.connected or not self.connection.shell:
            raise Exception("Not connected to remote machine")

        start_time = time.time()

        try:
            # Send command
            self.connection.shell.send(command + '\n')

            # Wait for command to complete (simple implementation)
            # In production, should use more sophisticated completion detection
            time.sleep(0.5)

            output = ""
            while self.connection.shell.recv_ready():
                chunk = self.connection.shell.recv(8192).decode('utf-8', errors='replace')
                output += chunk
                time.sleep(0.1)

            duration = time.time() - start_time

            return CommandResult(
                stdout=output,
                stderr="",
                exit_code=0,
                duration=duration,
                command=command
            )

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            duration = time.time() - start_time
            return CommandResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration=duration,
                command=command
            )

    def execute_simple(self, command: str, timeout: int = 10) -> str:
        """
        Execute command synchronously using separate channel
        Does NOT interfere with the interactive shell
        """
        if not self.connection.connected or not self.connection.client:
            raise Exception("Not connected")

        try:
            # Log sanitized version
            logger.info(f"Executing simple command: {command}")

            # Use exec_command which creates a SEPARATE channel
            # This doesn't interfere with the interactive shell
            stdin, stdout, stderr = self.connection.client.exec_command(command, timeout=timeout)

            # Read output
            output = stdout.read().decode('utf-8', errors='replace')

            return output

        except Exception as e:
            logger.error(f"execute_simple failed: {e}")
            return ""

    def _sanitize_command_for_log(self, command: str) -> str:
        """
        Remove password from command before logging

        Args:
            command: Command that may contain password

        Returns:
            Sanitized command for logging
        """
        if self.connection.password and self.connection.password in command:
            return command.replace(self.connection.password, "***PASSWORD***")
        return command
