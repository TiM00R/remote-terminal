// SFTP Transfer Panel (standalone)
(() => {
  // Wait for DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    const transferPanel = document.getElementById('transfer-panel');
    const transferHeader = document.getElementById('transfer-header');
    const transferList = document.getElementById('transfer-list');
    const collapseIcon = document.getElementById('transfer-collapse-icon');

    if (!transferPanel || !transferHeader || !transferList || !collapseIcon) return;

    let isCollapsed = false;

    // Toggle collapse on header click
    transferHeader.addEventListener('click', () => {
      isCollapsed = !isCollapsed;
      transferList.style.display = isCollapsed ? 'none' : 'block';
      collapseIcon.classList.toggle('collapsed', isCollapsed);
    });

    // Utilities
    function formatBytes(bytes) {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function formatDuration(seconds) {
      if (seconds < 60) return Math.round(seconds) + 's';
      const mins = Math.floor(seconds / 60);
      const secs = Math.round(seconds % 60);
      return mins + 'm ' + secs + 's';
    }

    // Render list
    function renderTransfers(transfers) {
      const transferIds = Object.keys(transfers);

      // Hide panel if no active transfers
      if (transferIds.length === 0) {
        transferPanel.classList.remove('visible');
        return;
      }

      transferPanel.classList.add('visible');
      transferList.innerHTML = '';

      transferIds.forEach(transferId => {
        const transfer = transfers[transferId];

        const item = document.createElement('div');
        item.className = 'transfer-item';

        const typeIcon = transfer.transfer_type === 'upload' ? '↑' : '↓';
        const method = transfer.method === 'compressed' ? '📦' : '📄';

        const percentComplete = transfer.percent_complete || 0;
        const completedFiles = transfer.completed_files || 0;
        const totalFiles = transfer.total_files || 0;
        const currentSpeed = transfer.current_speed || 0;
        const eta = transfer.eta || 0;

        const phase = transfer.current_phase || transfer.status || 'in_progress';

        const showFileCount = (phase === 'transferring' || phase === 'completed');
        const filesDisplay = showFileCount ? `${completedFiles} / ${totalFiles}` : '--';

        item.innerHTML = `
          <div class="transfer-info">
            <span class="transfer-value">${typeIcon} ${method} ${transfer.source}</span>
            <span class="transfer-status ${phase}">${phase.toUpperCase()}</span>
          </div>
          <div class="transfer-progress-bar">
            <div class="transfer-progress-fill" style="width: ${percentComplete}%"></div>
          </div>
          <div class="transfer-details">
            <div class="transfer-detail-item">
              <span>Progress:</span>
              <span>${Math.round(percentComplete)}%</span>
            </div>
            <div class="transfer-detail-item">
              <span>Files:</span>
              <span>${filesDisplay}</span>
            </div>
            <div class="transfer-detail-item" style="grid-column: 1 / -1;">
              <span>Current:</span>
              <span style="font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                ${transfer.current_file ? transfer.current_file.split('/').pop().split('\\\\').pop() : '--'}
              </span>
            </div>
            <div class="transfer-detail-item">
              <span>Speed:</span>
              <span>${currentSpeed > 0 ? formatBytes(currentSpeed * 1024 * 1024) + '/s' : '--'}</span>
            </div>
            <div class="transfer-detail-item">
              <span>ETA:</span>
              <span>${eta > 0 ? formatDuration(eta) : '--'}</span>
            </div>
          </div>
        `;

        transferList.appendChild(item);
      });
    }

    // Poll server
    async function pollTransfers() {
      while (true) {
        try {
          const res = await fetch('/api/active_transfers');
          const data = await res.json();
          renderTransfers(data.transfers || {});
        } catch (e) {
          console.error('Transfer poll error:', e);
        }
        await new Promise(r => setTimeout(r, 500));
      }
    }

    pollTransfers();
  }
})();
