/**
 * App Controller - Main application state and UI management
 */

// ---- Application State ----
const AppState = {
  connected: false,
  isDemo: false,
  currentTableId: null,
  currentObjectType: 'all',
  currentHiddenFilter: 'all',
  searchQuery: '',
  metadata: null,
  pendingCount: 0,
  selectedObject: null,
  contextTableId: null,
  pendingChanges: new Set(), // objectIds with pending changes
  detailDirty: false,
  detailEdits: {}
};

// ---- Toast Notifications ----
const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
  },

  show(message, type = 'info', duration = 4000) {
    const icons = {
      success: 'fa-check-circle',
      error: 'fa-times-circle',
      warning: 'fa-exclamation-triangle',
      info: 'fa-info-circle'
    };

    const item = document.createElement('div');
    item.className = `toast-item toast-${type}`;
    item.innerHTML = `
      <i class="fas ${icons[type] || icons.info} toast-icon"></i>
      <span class="toast-msg">${message}</span>
    `;

    this.container.appendChild(item);

    setTimeout(() => {
      item.classList.add('removing');
      setTimeout(() => item.remove(), 350);
    }, duration);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg) { this.show(msg, 'error', 6000); },
  warning(msg) { this.show(msg, 'warning'); },
  info(msg) { this.show(msg, 'info'); }
};

// ---- Loading Spinner ----
const Loader = {
  show() { document.getElementById('grid-spinner').classList.remove('hidden'); },
  hide() { document.getElementById('grid-spinner').classList.add('hidden'); }
};

// ---- Confirm Modal ----
async function showConfirm(title, message, confirmText = 'Confirmar', type = 'primary') {
  return new Promise((resolve) => {
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').innerHTML = message;
    const btn = document.getElementById('confirm-ok-btn');
    btn.textContent = confirmText;
    btn.className = `btn btn-${type}`;

    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    modal.show();

    const onOk = () => {
      modal.hide();
      btn.removeEventListener('click', onOk);
      resolve(true);
    };
    const onHide = () => {
      document.getElementById('confirmModal').removeEventListener('hidden.bs.modal', onHide);
      resolve(false);
    };

    btn.addEventListener('click', onOk);
    document.getElementById('confirmModal').addEventListener('hidden.bs.modal', onHide, { once: true });
  });
}

// ---- Connection Status ----
function updateConnectionUI(status) {
  const badge = document.getElementById('connection-badge');
  const badgeText = document.getElementById('connection-text');
  const dot = badge.querySelector('.connection-dot');

  AppState.connected = status.connected || false;
  AppState.isDemo = status.demo || false;

  if (!status.connected) {
    badge.className = 'connection-badge disconnected';
    badgeText.textContent = 'Desconectado';
    dot.classList.remove('pulse');
    document.getElementById('btn-save').disabled = true;
    document.getElementById('btn-discard').disabled = true;
  } else if (status.demo) {
    badge.className = 'connection-badge demo';
    badgeText.textContent = `Demo: ${status.modelName || status.databaseName || 'ContosoRetail'}`;
    dot.classList.add('pulse');
    document.getElementById('btn-save').disabled = false;
    document.getElementById('btn-discard').disabled = false;
  } else {
    badge.className = 'connection-badge connected';
    badgeText.textContent = status.modelName || status.databaseName || 'Conectado';
    dot.classList.add('pulse');
    document.getElementById('btn-save').disabled = false;
    document.getElementById('btn-discard').disabled = false;
  }
}

function updatePendingBadge(count) {
  AppState.pendingCount = count;
  const badge = document.getElementById('pending-badge');
  const countEl = document.getElementById('pending-count');

  if (count > 0) {
    badge.classList.remove('hidden');
    countEl.textContent = count;
  } else {
    badge.classList.add('hidden');
  }

  document.getElementById('btn-save').disabled = count === 0;
  document.getElementById('btn-discard').disabled = count === 0;
}

// ---- Sidebar ----
function renderSidebar(metadata) {
  const list = document.getElementById('sidebar-list');
  list.innerHTML = '';

  if (!metadata || !metadata.tables) return;

  // Stats
  document.getElementById('sidebar-stats').textContent =
    `${metadata.totalTables}T / ${metadata.totalColumns}C / ${metadata.totalMeasures}M`;

  // "All tables" item
  const allItem = createSidebarItem(
    'all',
    'Todas as Tabelas',
    'fa-database',
    null,
    metadata.tables.reduce((s, t) => s + t.columns.length + t.measures.length + t.hierarchies.length, 0)
  );
  list.appendChild(allItem);

  // Divider
  const sep = document.createElement('div');
  sep.className = 'sidebar-section-header';
  sep.textContent = 'Tabelas';
  list.appendChild(sep);

  // Table items
  const sortedTables = [...metadata.tables].sort((a, b) =>
    (a.name || '').localeCompare((b.name || ''), 'pt-BR', { sensitivity: 'base' })
  );

  sortedTables.forEach(table => {
    const count = table.columns.length + table.measures.length + table.hierarchies.length;
    const item = createSidebarItem(table.id, table.name, 'fa-table', table, count);
    list.appendChild(item);
  });

  // Relationships link
  const relSep = document.createElement('div');
  relSep.className = 'sidebar-section-header';
  relSep.style.marginTop = '8px';
  relSep.textContent = 'Relacionamentos';
  list.appendChild(relSep);

  const relItem = createSidebarItem('_relationships', 'Relacionamentos', 'fa-project-diagram', null, metadata.relationships ? metadata.relationships.length : 0);
  list.appendChild(relItem);
}

function createSidebarItem(id, name, iconClass, table, count) {
  const item = document.createElement('div');
  item.className = 'sidebar-item' + (AppState.currentTableId === id ? ' active' : '');
  item.dataset.tableId = id;

  let extra = '';
  if (table && table.isDateTable) {
    extra = `<span class="date-table-badge">DT</span>`;
  }
  if (table && table.hidden) {
    extra += `<i class="fas fa-eye-slash" style="color:var(--text-muted);font-size:10px;"></i>`;
  }

  item.innerHTML = `
    <i class="fas ${iconClass} sidebar-item-icon"></i>
    <span class="sidebar-item-text">${escapeHtml(name)}</span>
    ${extra}
    <span class="sidebar-item-count">${count}</span>
  `;

  item.addEventListener('click', () => selectTable(id));
  if (table) {
    item.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showSidebarContextMenu(e, table);
    });
  }
  return item;
}

function getTableById(tableId) {
  const tables = (AppState.metadata && AppState.metadata.tables) || [];
  return tables.find(t => t.id === tableId) || null;
}

function hideSidebarContextMenu() {
  const menu = document.getElementById('sidebar-context-menu');
  if (!menu) return;
  menu.classList.add('hidden');
  AppState.contextTableId = null;
}

function showSidebarContextMenu(event, table) {
  const menu = document.getElementById('sidebar-context-menu');
  const toggleBtn = document.getElementById('ctx-toggle-hide-table');
  if (!menu || !toggleBtn) return;

  AppState.contextTableId = table.id;

  if (table.hidden) {
    toggleBtn.innerHTML = '<i class="fas fa-eye"></i> Mostrar Tabela';
  } else {
    toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i> Ocultar Tabela';
  }

  menu.classList.remove('hidden');

  const menuWidth = 190;
  const menuHeight = 140;
  const maxX = window.innerWidth - menuWidth - 8;
  const maxY = window.innerHeight - menuHeight - 8;

  const left = Math.max(8, Math.min(event.clientX, maxX));
  const top = Math.max(8, Math.min(event.clientY, maxY));

  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
}

async function handleRenameTableContext() {
  const tableId = AppState.contextTableId;
  hideSidebarContextMenu();
  if (!tableId) return;

  const table = getTableById(tableId);
  if (!table) return;

  const newNameRaw = window.prompt('Novo nome da tabela:', table.name || '');
  if (newNameRaw === null) return;

  const newName = newNameRaw.trim();
  if (!newName) {
    Toast.warning('Nome da tabela nao pode ser vazio');
    return;
  }
  if (newName === table.name) return;

  Loader.show();
  try {
    await API.renameTable(tableId, newName);
    Toast.success(`Tabela renomeada para "${newName}" (pendente)`);
    await refreshPending();
    await loadMetadata(false);
  } catch (err) {
    Toast.error('Erro ao renomear tabela: ' + err.message);
  } finally {
    Loader.hide();
  }
}

async function handleToggleTableContext() {
  const tableId = AppState.contextTableId;
  hideSidebarContextMenu();
  if (!tableId) return;

  const table = getTableById(tableId);
  if (!table) return;

  const hideAll = !table.hidden;
  const label = hideAll ? 'Ocultar' : 'Mostrar';
  const ok = await showConfirm(
    `${label} Tabela`,
    `${label} a tabela <strong>${escapeHtml(table.name)}</strong> e todos os objetos dela?`,
    label,
    hideAll ? 'warning' : 'success'
  );
  if (!ok) return;

  Loader.show();
  try {
    const result = await API.setTableHidden(tableId, hideAll);
    Toast.success(`${table.name}: ${hideAll ? 'ocultada' : 'visivel'} (${result.affectedObjects || 0} objetos)`);
    await refreshPending();
    await loadMetadata(false);
  } catch (err) {
    Toast.error(`Erro ao ${hideAll ? 'ocultar' : 'mostrar'} tabela: ${err.message}`);
  } finally {
    Loader.hide();
  }
}

async function handleDeleteTableContext() {
  const tableId = AppState.contextTableId;
  hideSidebarContextMenu();
  if (!tableId) return;

  const table = getTableById(tableId);
  if (!table) return;

  const ok = await showConfirm(
    'Excluir Tabela',
    `Excluir a tabela <strong>${escapeHtml(table.name)}</strong>?<br><br>Isso tambem removera relacionamentos ligados a ela.`,
    'Excluir',
    'danger'
  );
  if (!ok) return;

  Loader.show();
  try {
    await API.deleteTable(tableId);
    Toast.warning(`Tabela ${table.name} marcada para exclusao (pendente)`);
    await refreshPending();
    await loadMetadata(false);
  } catch (err) {
    Toast.error('Erro ao excluir tabela: ' + err.message);
  } finally {
    Loader.hide();
  }
}

async function selectTable(tableId) {
  AppState.currentTableId = tableId;

  // Update sidebar active state
  document.querySelectorAll('.sidebar-item').forEach(el => {
    el.classList.toggle('active', el.dataset.tableId === tableId);
  });

  if (tableId === '_relationships') {
    showRelationships();
    return;
  }

  // Update toolbar title
  updateToolbarTitle(tableId);

  // Load objects
  await loadAndRenderObjects();
}

function updateToolbarTitle(tableId) {
  const title = document.getElementById('toolbar-title');
  if (!tableId || tableId === 'all') {
    title.innerHTML = `<i class="fas fa-database"></i> Todos os Objetos`;
  } else if (tableId === '_relationships') {
    title.innerHTML = `<i class="fas fa-project-diagram"></i> Relacionamentos`;
  } else {
    const meta = AppState.metadata;
    const table = meta && meta.tables ? meta.tables.find(t => t.id === tableId) : null;
    title.innerHTML = `<i class="fas fa-table"></i> ${escapeHtml(table ? table.name : tableId)}`;
  }
}

function ensureGridContainer() {
  const container = document.getElementById('grid-container');
  if (!container) return;

  if (!container.querySelector('#metadata-grid')) {
    container.innerHTML = `
      <div id="metadata-grid"></div>
      <div class="spinner-overlay hidden" id="grid-spinner">
        <div class="spinner"></div>
      </div>
    `;
    if (typeof Grid !== 'undefined') {
      Grid.init();
    }
  }
}

function restoreObjectsView() {
  ensureGridContainer();

  const container = document.getElementById('grid-container');
  const relView = container?.querySelector('.relationships-view');
  if (relView) relView.remove();

  const grid = document.getElementById('metadata-grid');
  if (grid) grid.style.display = '';
}

// ---- Object Loading ----
async function loadAndRenderObjects() {
  if (!AppState.connected) return;

  restoreObjectsView();
  Loader.show();
  try {
    const tableId = AppState.currentTableId;
    const type = AppState.currentObjectType === 'all' ? null : AppState.currentObjectType;
    const search = AppState.searchQuery || null;
    const hidden = AppState.currentHiddenFilter === 'hidden'
      ? true
      : AppState.currentHiddenFilter === 'visible'
        ? false
        : null;

    const resp = await API.getObjects(
      tableId === 'all' || !tableId ? null : tableId,
      type,
      search,
      hidden
    );

    // Mark pending changes
    const objects = (resp.objects || []).map(obj => ({
      ...obj,
      _hasPending: AppState.pendingChanges.has(obj.id)
    }));

    Grid.setData(objects);
    document.getElementById('obj-count').textContent = `${objects.length} objetos`;

    // Clear detail if current object not in result
    if (AppState.selectedObject) {
      const stillExists = objects.find(o => o.id === AppState.selectedObject.id);
      if (!stillExists) clearDetailPanel();
    }
  } catch (err) {
    Toast.error('Erro ao carregar objetos: ' + err.message);
  } finally {
    Loader.hide();
  }
}

// ---- Relationships View ----
async function showRelationships() {
  const meta = AppState.metadata;
  if (!meta) return;

  ensureGridContainer();

  document.getElementById('toolbar-title').innerHTML = `<i class="fas fa-project-diagram"></i> Relacionamentos`;
  document.getElementById('obj-count').textContent = `${(meta.relationships || []).length} relacionamentos`;

  // Render relationships without destroying the grid container
  const container = document.getElementById('grid-container');
  const grid = container.querySelector('#metadata-grid');
  if (grid) grid.style.display = 'none';

  const spinner = container.querySelector('#grid-spinner');
  if (spinner) spinner.classList.add('hidden');

  let relView = container.querySelector('.relationships-view');
  if (!relView) {
    relView = document.createElement('div');
    relView.className = 'relationships-view';
    container.appendChild(relView);
  }

  relView.innerHTML = `
    <table class="rel-table">
      <thead>
        <tr>
          <th>De (Tabela)</th>
          <th>De (Coluna)</th>
          <th>Para (Tabela)</th>
          <th>Para (Coluna)</th>
          <th>Cardinalidade</th>
          <th>Filtro Cruzado</th>
          <th>Ativo</th>
        </tr>
      </thead>
      <tbody>
        ${(meta.relationships || []).map(r => `
          <tr>
            <td><code>${escapeHtml(r.fromTable)}</code></td>
            <td>${escapeHtml(r.fromColumn)}</td>
            <td><code>${escapeHtml(r.toTable)}</code></td>
            <td>${escapeHtml(r.toColumn)}</td>
            <td><span class="badge-type badge-column" style="font-size:10px;">${escapeHtml(r.cardinality)}</span></td>
            <td style="font-size:11px;color:var(--text-muted);">${escapeHtml(r.crossFilteringBehavior)}</td>
            <td>${r.active ? '<span class="rel-active"><i class="fas fa-check-circle"></i> Ativo</span>' : '<span class="rel-inactive"><i class="fas fa-times-circle"></i> Inativo</span>'}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

// ---- Detail Panel ----
function showDetailPanel(obj) {
  AppState.selectedObject = obj;
  AppState.detailDirty = false;
  AppState.detailEdits = {};

  const panel = document.getElementById('detail-panel');
  panel.classList.remove('collapsed');

  const title = document.getElementById('detail-title');
  const badges = {
    column: '<span class="badge-type badge-column"><i class="fas fa-columns"></i> Coluna</span>',
    measure: '<span class="badge-type badge-measure"><i class="fas fa-calculator"></i> Medida</span>',
    hierarchy: '<span class="badge-type badge-hierarchy"><i class="fas fa-sitemap"></i> Hierarquia</span>',
    table: '<span class="badge-type badge-table"><i class="fas fa-table"></i> Tabela</span>'
  };
  title.innerHTML = `${badges[obj.objectType] || ''} ${escapeHtml(obj.name)}`;

  renderDetailContent(obj);
}

function renderDetailContent(obj) {
  const content = document.getElementById('detail-content');

  const isEditable = AppState.connected;

  let html = `
    <div class="prop-group">
      <div class="prop-group-title">Identificacao</div>
      <div class="prop-row">
        <span class="prop-label">Nome</span>
        <div class="prop-value">${escapeHtml(obj.name)}</div>
      </div>
      <div class="prop-row">
        <span class="prop-label">Tabela</span>
        <div class="prop-value">${escapeHtml(obj.tableName || '')}</div>
      </div>
      <div class="prop-row">
        <span class="prop-label">Tipo</span>
        <div class="prop-value">${escapeHtml(obj.objectType || '')}</div>
      </div>
    </div>

    <div class="prop-group">
      <div class="prop-group-title">Metadados Editaveis</div>
      <div class="prop-row">
        <span class="prop-label">Descricao</span>
        <textarea class="prop-input" id="det-description" rows="3" ${isEditable ? '' : 'readonly'}>${escapeHtml(obj.description || '')}</textarea>
      </div>
      <div class="prop-row">
        <span class="prop-label">Pasta de Exibicao</span>
        <input type="text" class="prop-input" id="det-displayFolder" value="${escapeHtml(obj.displayFolder || '')}" ${isEditable ? '' : 'readonly'}>
      </div>
  `;

  if (obj.objectType !== 'hierarchy') {
    html += `
      <div class="prop-row">
        <span class="prop-label">Formato</span>
        <input type="text" class="prop-input" id="det-formatString" value="${escapeHtml(obj.formatString || '')}" ${isEditable ? '' : 'readonly'}>
      </div>
    `;
  }

  html += `
      <div class="prop-row">
        <span class="prop-label">Oculto</span>
        <div class="prop-toggle">
          <label class="toggle-switch" id="det-hidden-label">
            <input type="checkbox" id="det-hidden" ${obj.hidden ? 'checked' : ''} ${isEditable ? '' : 'disabled'}>
            <div class="toggle-track"></div>
            <div class="toggle-thumb"></div>
          </label>
          <span style="font-size:12px;color:var(--text-muted);">${obj.hidden ? 'Oculto' : 'Visivel'}</span>
        </div>
      </div>
    </div>
  `;

  // Type-specific properties
  if (obj.objectType === 'column') {
    html += `
      <div class="prop-group">
        <div class="prop-group-title">Propriedades da Coluna</div>
        <div class="prop-row">
          <span class="prop-label">Tipo de Dado</span>
          <div class="prop-value">${escapeHtml(obj.dataType || '-')}</div>
        </div>
        <div class="prop-row">
          <span class="prop-label">Resumir Por</span>
          <div class="prop-value">${escapeHtml(obj.summarizeBy || '-')}</div>
        </div>
        ${obj.sortByColumn ? `<div class="prop-row"><span class="prop-label">Ordenar por</span><div class="prop-value">${escapeHtml(obj.sortByColumn)}</div></div>` : ''}
        ${obj.expression ? `
          <div class="prop-row">
            <span class="prop-label">Expressao (Coluna Calculada)</span>
            <div class="dax-preview">${escapeHtml(obj.expression)}</div>
            <button class="btn-view-dax" onclick="showDAXModal('${escapeHtml(obj.name)}', \`${escapeJs(obj.expression)}\`)">
              <i class="fas fa-expand"></i> Ver DAX completo
            </button>
          </div>
        ` : ''}
      </div>
    `;
  } else if (obj.objectType === 'measure') {
    html += `
      <div class="prop-group">
        <div class="prop-group-title">Expressao DAX</div>
        <div class="prop-row">
          <div class="dax-preview">${escapeHtml(obj.expression || '(sem expressao)')}</div>
          ${obj.expression ? `<button class="btn-view-dax" onclick="showDAXModal('${escapeHtml(obj.name)}', \`${escapeJs(obj.expression)}\`)">
            <i class="fas fa-expand"></i> Ver DAX completo
          </button>` : ''}
        </div>
      </div>
    `;
  } else if (obj.objectType === 'hierarchy') {
    html += `
      <div class="prop-group">
        <div class="prop-group-title">Niveis</div>
        ${(obj.levels || []).map((lv, i) => `
          <div class="prop-row">
            <span class="prop-label">Nivel ${i + 1}</span>
            <div class="prop-value">${escapeHtml(lv)}</div>
          </div>
        `).join('')}
      </div>
    `;
  }

  content.innerHTML = html;

  // Attach change listeners
  if (isEditable) {
    const fields = ['description', 'displayFolder', 'formatString', 'hidden'];
    fields.forEach(field => {
      const el = document.getElementById(`det-${field}`);
      if (!el) return;
      el.addEventListener('change', () => {
        AppState.detailDirty = true;
        const val = el.type === 'checkbox' ? el.checked : el.value;
        AppState.detailEdits[field] = val;
        document.getElementById('btn-detail-save').disabled = false;
      });
      el.addEventListener('input', () => {
        AppState.detailDirty = true;
        const val = el.type === 'checkbox' ? el.checked : el.value;
        AppState.detailEdits[field] = val;
        document.getElementById('btn-detail-save').disabled = false;
      });
    });

    document.getElementById('btn-detail-save').disabled = true;
  }
}

function clearDetailPanel() {
  AppState.selectedObject = null;
  AppState.detailDirty = false;
  AppState.detailEdits = {};
  document.getElementById('detail-content').innerHTML = `
    <div class="detail-empty">
      <i class="fas fa-mouse-pointer"></i>
      <span>Selecione um objeto para ver detalhes</span>
    </div>
  `;
  document.getElementById('detail-title').innerHTML = 'Detalhes';
  document.getElementById('btn-detail-save').disabled = true;
}

async function saveDetailEdits() {
  if (!AppState.selectedObject || !AppState.detailDirty) return;

  const obj = AppState.selectedObject;
  const edits = AppState.detailEdits;

  if (Object.keys(edits).length === 0) return;

  Loader.show();
  let successCount = 0;
  let errorCount = 0;

  for (const [field, value] of Object.entries(edits)) {
    try {
      await API.updateObject(obj.objectType, obj.id, obj.tableId, field, value);
      obj[field] = value; // Update local state
      AppState.pendingChanges.add(obj.id);
      successCount++;
    } catch (err) {
      Toast.error(`Erro ao salvar ${field}: ${err.message}`);
      errorCount++;
    }
  }

  Loader.hide();

  if (successCount > 0) {
    Toast.success(`${successCount} campo(s) atualizados com sucesso`);
    AppState.detailDirty = false;
    AppState.detailEdits = {};
    document.getElementById('btn-detail-save').disabled = true;

    // Refresh pending count
    await refreshPending();
    // Refresh grid
    await loadAndRenderObjects();
  }
}

// ---- DAX Modal ----
function showDAXModal(name, expression) {
  document.getElementById('dax-modal-title').textContent = `DAX: ${name}`;
  document.getElementById('dax-content').textContent = expression;
  const modal = new bootstrap.Modal(document.getElementById('daxModal'));
  modal.show();
}

// ---- Connection Modal ----
function showConnectModal() {
  const modal = new bootstrap.Modal(document.getElementById('connectModal'));
  modal.show();
}

async function handleConnect() {
  const mode = document.querySelector('input[name="conn-mode"]:checked')?.value || 'local';

  Loader.show();
  try {
    let result;
    if (mode === 'local') {
      result = await API.connectLocal();
    } else {
      const workspace = document.getElementById('remote-workspace').value.trim();
      const model = document.getElementById('remote-model').value.trim();
      const username = document.getElementById('remote-user').value.trim();
      const password = document.getElementById('remote-pass').value;

      if (!workspace) {
        Toast.warning('Informe o nome do workspace');
        Loader.hide();
        return;
      }

      result = await API.connectRemote(workspace, model, username, password);
    }

    updateConnectionUI(result);

    if (result.demo) {
      Toast.warning(result.message || 'Conectado em modo demonstracao');
    } else {
      Toast.success('Conexao estabelecida com sucesso');
    }

    // Close modal
    bootstrap.Modal.getInstance(document.getElementById('connectModal'))?.hide();

    // Load metadata
    await loadMetadata();

  } catch (err) {
    Toast.error('Falha na conexao: ' + err.message);
  } finally {
    Loader.hide();
  }
}

async function handleDisconnect() {
  const ok = await showConfirm(
    'Desconectar',
    'Deseja desconectar do modelo atual? Alteracoes nao salvas serao perdidas.',
    'Desconectar',
    'danger'
  );
  if (!ok) return;

  try {
    await API.disconnect();
    updateConnectionUI({ connected: false });
    AppState.metadata = null;
    AppState.pendingChanges.clear();
    updatePendingBadge(0);
    renderSidebar(null);
    Grid.clear();
    clearDetailPanel();
    Toast.info('Desconectado');
  } catch (err) {
    Toast.error('Erro ao desconectar: ' + err.message);
  }
}

// ---- Metadata Loading ----
async function loadMetadata(forceReload = false) {
  Loader.show();
  try {
    const previousTableId = AppState.currentTableId;
    const meta = await API.getMetadata(forceReload);
    AppState.metadata = meta;
    renderSidebar(meta);

    // Restaura selecao anterior quando possivel
    if (meta.tables && meta.tables.length > 0) {
      if (previousTableId === '_relationships') {
        await selectTable('_relationships');
      } else if (previousTableId && meta.tables.some(t => t.id === previousTableId)) {
        await selectTable(previousTableId);
      } else {
        await selectTable('all');
      }
    }

    // Check pending
    await refreshPending();

    if (meta.demo) {
      const demoBar = document.getElementById('demo-banner');
      if (demoBar) demoBar.style.display = 'flex';
    }
  } catch (err) {
    Toast.error('Erro ao carregar metadados: ' + err.message);
  } finally {
    Loader.hide();
  }
}

async function refreshPending() {
  try {
    const resp = await API.getPending();
    updatePendingBadge(resp.count || 0);
  } catch (_) { /* ignore */ }
}

// ---- Save / Discard ----
async function handleSave() {
  if (AppState.pendingCount === 0) return;

  const ok = await showConfirm(
    'Salvar Alteracoes',
    `Voce tem <strong>${AppState.pendingCount}</strong> alteracao(oes) pendente(s).<br><br>
     ${AppState.isDemo ? '<div class="alert-info-dark"><i class="fas fa-info-circle"></i> Modo demonstracao: as alteracoes serao simuladas mas nao persistidas.</div>' : 'As alteracoes serao aplicadas ao modelo Power BI.'}`,
    'Salvar',
    'primary'
  );
  if (!ok) return;

  Loader.show();
  try {
    const result = await API.commitChanges();
    const durationInfo = typeof result.durationMs === 'number'
      ? ` em ${(result.durationMs / 1000).toFixed(2)}s`
      : '';
    const compactInfo = (
      typeof result.requestedChanges === 'number'
      && typeof result.effectiveChanges === 'number'
      && result.effectiveChanges < result.requestedChanges
    )
      ? ` (${result.effectiveChanges}/${result.requestedChanges} efetivas)`
      : '';

    if (result.failed === 0) {
      Toast.success(`${result.success} alteracao(oes) salvas com sucesso${compactInfo}${durationInfo}`);
      AppState.pendingChanges.clear();
      updatePendingBadge(0);
      await loadAndRenderObjects();
    } else {
      Toast.warning(`${result.success} sucesso, ${result.failed} falhas${compactInfo}${durationInfo}`);
      if (result.errors && result.errors.length > 0) {
        result.errors.forEach(e => Toast.error(e));
      }
      await refreshPending();
    }
  } catch (err) {
    Toast.error('Erro ao salvar: ' + err.message);
  } finally {
    Loader.hide();
  }
}

async function handleDiscard() {
  if (AppState.pendingCount === 0) return;

  const ok = await showConfirm(
    'Descartar Alteracoes',
    `Todas as <strong>${AppState.pendingCount}</strong> alteracao(oes) pendentes serao descartadas. Esta acao nao pode ser desfeita.`,
    'Descartar',
    'danger'
  );
  if (!ok) return;

  Loader.show();
  try {
    await API.discardChanges();
    AppState.pendingChanges.clear();
    updatePendingBadge(0);
    Toast.info('Alteracoes descartadas');
    await loadMetadata(false);
  } catch (err) {
    Toast.error('Erro ao descartar: ' + err.message);
  } finally {
    Loader.hide();
  }
}

// ---- Export Backup ----
async function handleExport() {
  try {
    const data = await API.exportBackup();
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `metadata_backup_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
    Toast.success('Backup exportado com sucesso');
  } catch (err) {
    Toast.error('Erro ao exportar: ' + err.message);
  }
}

// ---- Filter Handling ----
function handleTypeFilter(type) {
  AppState.currentObjectType = type;

  // Update pill styles
  document.querySelectorAll('.type-pill').forEach(p => {
    const pType = p.dataset.type;
    p.className = 'type-pill';
    if (pType === type) {
      const classMap = {
        all: 'active-all',
        column: 'active-column',
        measure: 'active-measure',
        hierarchy: 'active-hierarchy'
      };
      p.classList.add(classMap[type] || 'active-all');
    }
  });

  loadAndRenderObjects();
}

function handleHiddenFilter(filterMode) {
  AppState.currentHiddenFilter = filterMode;

  document.querySelectorAll('.hidden-pill').forEach(pill => {
    const thisMode = pill.dataset.hidden;
    pill.className = 'hidden-pill';
    if (thisMode === filterMode) {
      const classMap = {
        all: 'active-hidden-all',
        visible: 'active-hidden-visible',
        hidden: 'active-hidden-hidden'
      };
      pill.classList.add(classMap[filterMode] || 'active-hidden-all');
    }
  });

  loadAndRenderObjects();
}

let searchTimeout = null;
function handleSearch(value) {
  AppState.searchQuery = value;
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => loadAndRenderObjects(), 300);
}

// ---- Sidebar Search ----
function handleSidebarSearch(value) {
  const query = value.toLowerCase();
  document.querySelectorAll('.sidebar-item').forEach(item => {
    const text = item.querySelector('.sidebar-item-text')?.textContent?.toLowerCase() || '';
    item.style.display = text.includes(query) ? '' : 'none';
  });
}

// ---- Utility ----
function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeJs(str) {
  if (str == null) return '';
  return String(str).replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

// ---- Initialization ----
async function initApp() {
  Toast.init();

  // Check existing connection
  try {
    const status = await API.getStatus();
    if (status.connected) {
      updateConnectionUI(status);
      await loadMetadata();
    } else {
      updateConnectionUI({ connected: false });
    }
  } catch (err) {
    updateConnectionUI({ connected: false });
    // Auto-connect in dev mode (no server error)
    try {
      const result = await API.connectLocal();
      updateConnectionUI(result);
      await loadMetadata();
    } catch (_) { /* ignore */ }
  }

  // Event: connection badge click
  document.getElementById('connection-badge').addEventListener('click', () => {
    if (AppState.connected) {
      handleDisconnect();
    } else {
      showConnectModal();
    }
  });

  // Event: connect button in navbar
  document.getElementById('btn-connect').addEventListener('click', showConnectModal);

  // Event: save
  document.getElementById('btn-save').addEventListener('click', handleSave);

  // Event: discard
  document.getElementById('btn-discard').addEventListener('click', handleDiscard);

  // Event: export
  document.getElementById('btn-export').addEventListener('click', handleExport);

  // Event: connect modal submit
  document.getElementById('btn-do-connect').addEventListener('click', handleConnect);

  // Event: detail save
  document.getElementById('btn-detail-save').addEventListener('click', saveDetailEdits);

  // Event: close detail panel
  document.getElementById('btn-close-detail').addEventListener('click', () => {
    document.getElementById('detail-panel').classList.add('collapsed');
    AppState.selectedObject = null;
  });

  // Event: type filter pills
  document.querySelectorAll('.type-pill').forEach(pill => {
    pill.addEventListener('click', () => handleTypeFilter(pill.dataset.type));
  });

  // Event: hidden filter pills
  document.querySelectorAll('.hidden-pill').forEach(pill => {
    pill.addEventListener('click', () => handleHiddenFilter(pill.dataset.hidden));
  });

  // Event: search
  document.getElementById('search-input').addEventListener('input', (e) => handleSearch(e.target.value));

  // Event: sidebar search
  document.getElementById('sidebar-search-input').addEventListener('input', (e) => handleSidebarSearch(e.target.value));

  // Event: sidebar context menu actions
  document.getElementById('ctx-rename-table').addEventListener('click', handleRenameTableContext);
  document.getElementById('ctx-toggle-hide-table').addEventListener('click', handleToggleTableContext);
  document.getElementById('ctx-delete-table').addEventListener('click', handleDeleteTableContext);

  document.addEventListener('click', (e) => {
    if (!e.target.closest('#sidebar-context-menu')) {
      hideSidebarContextMenu();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideSidebarContextMenu();
  });
  document.getElementById('sidebar-list').addEventListener('scroll', hideSidebarContextMenu);
  window.addEventListener('resize', hideSidebarContextMenu);

  // Event: reload metadata
  document.getElementById('btn-reload').addEventListener('click', async () => {
    if (!AppState.connected) return;
    await loadMetadata(true);
    Toast.info('Metadados recarregados');
  });

  // Event: DAX copy
  document.getElementById('btn-copy-dax').addEventListener('click', () => {
    const content = document.getElementById('dax-content').textContent;
    navigator.clipboard.writeText(content).then(() => Toast.success('DAX copiado!'));
  });
}

// Start the app when DOM is ready
document.addEventListener('DOMContentLoaded', initApp);
