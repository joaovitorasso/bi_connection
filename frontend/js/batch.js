/**
 * Batch Operations Module
 */

const Batch = {
  // Collect currently selected items from grid
  getSelectedItems() {
    return Grid.getSelectedRows();
  },

  // Group selected items by table for batch API calls
  groupByTable(items) {
    const groups = {};
    items.forEach(item => {
      const key = `${item.tableId}__${item.objectType}`;
      if (!groups[key]) {
        groups[key] = { tableId: item.tableId, objectType: item.objectType, ids: [] };
      }
      groups[key].ids.push(item.id);
    });
    return Object.values(groups);
  },

  getAvailableFolders() {
    const folders = new Set();
    const tables = (AppState.metadata && AppState.metadata.tables) || [];

    tables.forEach(table => {
      const all = []
        .concat(table.columns || [])
        .concat(table.measures || [])
        .concat(table.hierarchies || []);

      all.forEach(obj => {
        const folder = (obj.displayFolder || '').trim();
        if (folder) folders.add(folder);
      });
    });

    return Array.from(folders).sort((a, b) => a.localeCompare(b, 'pt-BR'));
  },

  populateFolderSuggestions() {
    const datalist = document.getElementById('batch-folder-suggestions');
    if (!datalist) return;

    const folders = this.getAvailableFolders();
    datalist.innerHTML = folders.map(folder => `<option value="${escapeHtml(folder)}"></option>`).join('');
  },

  // Show batch modal
  showModal() {
    const items = this.getSelectedItems();
    if (items.length === 0) {
      Toast.warning('Selecione pelo menos um objeto');
      return;
    }

    // Update modal info
    document.getElementById('batch-modal-count').textContent = items.length;

    // Show type breakdown
    const typeCounts = items.reduce((acc, item) => {
      acc[item.objectType] = (acc[item.objectType] || 0) + 1;
      return acc;
    }, {});

    const breakdown = Object.entries(typeCounts).map(([type, count]) => {
      const labels = { column: 'Coluna(s)', measure: 'Medida(s)', hierarchy: 'Hierarquia(s)' };
      return `${count} ${labels[type] || type}`;
    }).join(', ');

    document.getElementById('batch-breakdown').textContent = breakdown;

    // Reset form
    document.getElementById('batch-action').value = 'hide';
    document.getElementById('batch-folder-row').style.display = 'none';
    document.getElementById('batch-desc-row').style.display = 'none';
    document.getElementById('batch-folder-value').value = '';
    document.getElementById('batch-desc-value').value = '';
    this.populateFolderSuggestions();

    const modal = new bootstrap.Modal(document.getElementById('batchModal'));
    modal.show();
  },

  // Handle action select change
  onActionChange(value) {
    document.getElementById('batch-folder-row').style.display = value === 'folder' ? '' : 'none';
    document.getElementById('batch-desc-row').style.display = value === 'description' ? '' : 'none';
  },

  // Execute batch operation
  async execute() {
    const items = this.getSelectedItems();
    if (items.length === 0) return;

    const action = document.getElementById('batch-action').value;
    const folderValue = document.getElementById('batch-folder-value').value;
    const descValue = document.getElementById('batch-desc-value').value;

    // Validation
    if (action === 'folder' && !folderValue.trim()) {
      Toast.warning('Informe o nome da pasta');
      return;
    }

    // Close modal
    bootstrap.Modal.getInstance(document.getElementById('batchModal'))?.hide();

    Loader.show();
    let totalSuccess = 0;
    let totalFailed = 0;

    try {
      const groups = this.groupByTable(items);

      for (const group of groups) {
        try {
          let result;
          switch (action) {
            case 'hide':
              result = await API.batchHide(group.ids, group.tableId, group.objectType);
              break;
            case 'show':
              result = await API.batchShow(group.ids, group.tableId, group.objectType);
              break;
            case 'folder':
              result = await API.batchSetFolder(group.ids, group.tableId, group.objectType, folderValue.trim());
              break;
            case 'clearFolder':
              result = await API.batchSetFolder(group.ids, group.tableId, group.objectType, '');
              break;
            case 'description':
              result = await API.batchSetDescription(group.ids, group.tableId, group.objectType, descValue.trim());
              break;
            default:
              throw new Error('Acao desconhecida: ' + action);
          }

          totalSuccess += result.success || 0;
          totalFailed += result.failed || 0;

          // Mark as pending
          group.ids.forEach(id => AppState.pendingChanges.add(id));

        } catch (err) {
          totalFailed += group.ids.length;
          Toast.error(`Erro no grupo ${group.tableId}: ${err.message}`);
        }
      }

      if (totalSuccess > 0) {
        const actionLabels = {
          hide: 'ocultados',
          show: 'exibidos',
          folder: 'pasta atualizada',
          clearFolder: 'pasta removida',
          description: 'descricao atualizada'
        };
        Toast.success(`${totalSuccess} objeto(s) ${actionLabels[action] || 'atualizados'}`);
        await refreshPending();
        Grid.clearSelection();
        await loadAndRenderObjects();
      }

      if (totalFailed > 0) {
        Toast.warning(`${totalFailed} objeto(s) com falha`);
      }

    } finally {
      Loader.hide();
    }
  },

  // Quick hide selected from batch bar
  async quickHide() {
    const items = this.getSelectedItems();
    if (items.length === 0) {
      Toast.warning('Selecione objetos na grade para ocultar');
      return;
    }

    const ok = await showConfirm(
      'Ocultar Objetos',
      `Ocultar <strong>${items.length}</strong> objeto(s) selecionado(s)?`,
      'Ocultar',
      'warning'
    );
    if (!ok) return;

    Loader.show();
    try {
      const groups = this.groupByTable(items);
      let total = 0;
      for (const group of groups) {
        const result = await API.batchHide(group.ids, group.tableId, group.objectType);
        total += result.success || 0;
        group.ids.forEach(id => AppState.pendingChanges.add(id));
      }
      Toast.success(`${total} objeto(s) ocultados`);
      await refreshPending();
      Grid.clearSelection();
      await loadAndRenderObjects();
    } catch (err) {
      Toast.error('Erro: ' + err.message);
    } finally {
      Loader.hide();
    }
  },

  // Quick show selected from batch bar
  async quickShow() {
    const items = this.getSelectedItems();
    if (items.length === 0) {
      Toast.warning('Selecione objetos na grade para mostrar');
      return;
    }

    const ok = await showConfirm(
      'Exibir Objetos',
      `Exibir <strong>${items.length}</strong> objeto(s) oculto(s)?`,
      'Exibir',
      'success'
    );
    if (!ok) return;

    Loader.show();
    try {
      const groups = this.groupByTable(items);
      let total = 0;
      for (const group of groups) {
        const result = await API.batchShow(group.ids, group.tableId, group.objectType);
        total += result.success || 0;
        group.ids.forEach(id => AppState.pendingChanges.add(id));
      }
      Toast.success(`${total} objeto(s) exibidos`);
      await refreshPending();
      Grid.clearSelection();
      await loadAndRenderObjects();
    } catch (err) {
      Toast.error('Erro: ' + err.message);
    } finally {
      Loader.hide();
    }
  },

  // Quick set folder from batch bar
  async quickSetFolder() {
    const items = this.getSelectedItems();
    if (items.length === 0) {
      Toast.warning('Selecione objetos na grade para mover de pasta');
      return;
    }

    // Simple prompt using the batch modal
    document.getElementById('batch-action').value = 'folder';
    this.onActionChange('folder');
    document.getElementById('batch-folder-row').style.display = '';
    document.getElementById('batch-desc-row').style.display = 'none';
    document.getElementById('batch-modal-count').textContent = items.length;
    this.populateFolderSuggestions();

    const typeCounts = items.reduce((acc, item) => {
      acc[item.objectType] = (acc[item.objectType] || 0) + 1;
      return acc;
    }, {});
    const breakdown = Object.entries(typeCounts).map(([t, c]) => `${c} ${t}`).join(', ');
    document.getElementById('batch-breakdown').textContent = breakdown;

    const modal = new bootstrap.Modal(document.getElementById('batchModal'));
    modal.show();
    setTimeout(() => document.getElementById('batch-folder-value')?.focus(), 150);
  }
};

// ---- Wire up event listeners ----
document.addEventListener('DOMContentLoaded', () => {
  // Batch bar buttons
  document.getElementById('btn-batch-hide')?.addEventListener('click', () => Batch.quickHide());
  document.getElementById('btn-batch-show')?.addEventListener('click', () => Batch.quickShow());
  document.getElementById('btn-batch-folder')?.addEventListener('click', () => Batch.quickSetFolder());
  document.getElementById('btn-batch-more')?.addEventListener('click', () => Batch.showModal());

  // Main toolbar shortcuts
  document.getElementById('btn-mass-hide')?.addEventListener('click', () => Batch.quickHide());
  document.getElementById('btn-mass-show')?.addEventListener('click', () => Batch.quickShow());
  document.getElementById('btn-mass-folder')?.addEventListener('click', () => Batch.quickSetFolder());

  // Batch modal action change
  document.getElementById('batch-action')?.addEventListener('change', (e) => Batch.onActionChange(e.target.value));

  // Batch modal execute
  document.getElementById('btn-batch-execute')?.addEventListener('click', () => Batch.execute());
});
