"""
Web Terminal UI Page Generation
NiceGUI-based terminal interface with xterm.js
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def create_terminal_page(ui, web_terminal_server):
    """
    Create the main terminal UI page

    Args:
        ui: NiceGUI ui module
        web_terminal_server: WebTerminalServer instance
    """

    def _read_fragment(name: str) -> str:
        """Read HTML fragment from static/fragments"""
        # static is in src/static, go up one level from web/ directory
        base = Path(__file__).parent.parent / 'static' / 'fragments'
        return (base / name).read_text(encoding='utf-8')

    @ui.page('/')
    def index():
        """Main page with xterm.js terminal"""

        connection_info = web_terminal_server.get_connection_display()

        # Header
        with ui.header().classes('items-center justify-between'):
            connection_label = ui.label(
                f'Remote Terminal | Connected to: {connection_info}'
            ).classes('text-h6')

        # Load xterm.js libraries and CSS
        ui.add_head_html(_read_fragment('head.html'))

        # Terminal container
        ui.html(_read_fragment('terminal_container.html'), sanitize=False)

        # SFTP panel
        ui.html(_read_fragment('transfer_panel.html'), sanitize=False)

        # Load WebSocket-enabled terminal.js
        ui.run_javascript('''
            const script1 = document.createElement('script');
            script1.src = '/static/terminal.js';
            document.body.appendChild(script1);

            const script2 = document.createElement('script');
            script2.src = '/static/transfer-panel.js';
            document.body.appendChild(script2);
        ''', timeout=1.0)

        # Connection label is updated via WebSocket events - no polling timer needed
