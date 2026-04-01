/**
 * Grid Module - Tabulator-based interactive data grid
 */

const Grid = {
  table: null,
  _data: [],

  init() {
    this.table = new Tabulator('#metadata-grid', {
      height: '100%',
      layout: 'fitColumns',
      responsiveLayout: false,
      pagination: true,
      paginationSize: 50,
      paginationSizeSelector: [25, 50, 100, 200],
      initialSort: [
        { column: 'name', dir: 'asc' }
      ],
      movableColumns: true,
      selectable: true,
      selectableRangeMode: 'click',
      selectableRows: true,
      selectableRowsRangeMode: 'click',
      selectableRowsPersistence: false,
      clipboard: true,
      tooltips: true,
      data: [],
      placeholder: '<div class="empty-state"><i class="fas fa-database"></i><h3>Nenhum dado</h3><p>Conecte-se a um modelo Power BI para visualizar os metadados</p></div>',
      rowFormatter: (row) => {
        const data = row.getData();
        if (data._hasPending) {
          row.getElement().classList.add('has-pending');
        }
        if (data.hidden) {
          row.getElement().style.opacity = '0.65';
        }
      },
      columns: [
        {
          title: '',
          field: '_check',
          formatter: 'rowSelection',
          titleFormatter: 'rowSelection',
          hozAlign: 'center',
          headerHozAlign: 'center',
          width: 40,
          minWidth: 40,
          resizable: false,
          headerSort: false,
          cellClick: (e, cell) => {
            cell.getRow().toggleSelect();
          }
        },
        {
          title: 'Tipo',
          field: 'objectType',
          width: 100,
          minWidth: 80,
          resizable: true,
          sorter: 'string',
          headerFilter: 'list',
          headerFilterParams: {
            values: { column: 'Coluna', measure: 'Medida', hierarchy: 'Hierarquia' },
            clearable: true
          },
          formatter: (cell) => {
            const val = cell.getValue();
            const map = {
              column: `<span class="badge-type badge-column"><i class="fas fa-columns"></i> Coluna</span>`,
              measure: `<span class="badge-type badge-measure"><i class="fas fa-calculator"></i> Medida</span>`,
              hierarchy: `<span class="badge-type badge-hierarchy"><i class="fas fa-sitemap"></i> Hierarquia</span>`,
              table: `<span class="badge-type badge-table"><i class="fas fa-table"></i> Tabela</span>`
            };
            return map[val] || val;
          }
        },
        {
          title: 'Tabela',
          field: 'tableName',
          width: 120,
          minWidth: 90,
          sorter: 'string',
          resizable: true,
          formatter: (cell) => {
            return `<code style="font-size:11px;">${escapeHtml(cell.getValue() || '')}</code>`;
          }
        },
        {
          title: 'Nome',
          field: 'name',
          minWidth: 140,
          sorter: 'string',
          resizable: true,
          formatter: (cell) => {
            const row = cell.getRow().getData();
            let icon = '';
            if (row.objectType === 'column') icon = '<i class="fas fa-columns" style="color:#4fc3f7;margin-right:5px;font-size:11px;"></i>';
            else if (row.objectType === 'measure') icon = '<i class="fas fa-calculator" style="color:#ffb74d;margin-right:5px;font-size:11px;"></i>';
            else if (row.objectType === 'hierarchy') icon = '<i class="fas fa-sitemap" style="color:#5cb85c;margin-right:5px;font-size:11px;"></i>';
            return `${icon}${escapeHtml(cell.getValue() || '')}`;
          }
        },
        {
          title: 'Descricao',
          field: 'description',
          minWidth: 180,
          sorter: 'string',
          resizable: true,
          editor: 'textarea',
          editorParams: {
            verticalNavigation: 'editor'
          },
          cellEdited: (cell) => {
            handleCellEdit(cell, 'description');
          },
          formatter: (cell) => {
            const val = cell.getValue();
            if (!val) return `<span style="color:var(--text-muted);font-style:italic;font-size:12px;">Sem descricao</span>`;
            return `<span title="${escapeHtml(val)}">${escapeHtml(val)}</span>`;
          }
        },
        {
          title: 'Oculto',
          field: 'hidden',
          width: 80,
          minWidth: 70,
          hozAlign: 'center',
          sorter: 'boolean',
          resizable: true,
          formatter: (cell) => {
            const val = cell.getValue();
            if (val) {
              return `<span class="badge-hidden"><i class="fas fa-eye-slash"></i> Sim</span>`;
            }
            return `<span class="badge-visible"><i class="fas fa-eye"></i> Nao</span>`;
          },
          cellClick: (e, cell) => {
            const row = cell.getRow().getData();
            toggleHidden(row, cell);
          },
          headerFilter: 'list',
          headerFilterParams: {
            values: { true: 'Oculto', false: 'Visivel' },
            clearable: true
          },
          headerFilterFunc: (headerValue, rowValue) => {
            if (headerValue === null || headerValue === undefined || headerValue === '') {
              return true;
            }
            if (headerValue === true || headerValue === 'true') {
              return rowValue === true;
            }
            if (headerValue === false || headerValue === 'false') {
              return rowValue === false;
            }
            return true;
          }
        },
        {
          title: 'Tipo Dado',
          field: 'dataType',
          width: 100,
          minWidth: 80,
          sorter: 'string',
          resizable: true,
          formatter: (cell) => {
            const val = cell.getValue();
            if (!val) return '';
            const colors = {
              'Int64': '#4fc3f7', 'Decimal': '#4fc3f7', 'Double': '#4fc3f7', 'Currency': '#4fc3f7',
              'String': '#dcdcaa', 'Boolean': '#ffb74d', 'DateTime': '#ce9178'
            };
            const color = colors[val] || 'var(--text-muted)';
            return `<span style="color:${color};font-size:11px;">${escapeHtml(val)}</span>`;
          }
        },
        {
          title: 'Formato',
          field: 'formatString',
          width: 120,
          minWidth: 80,
          sorter: 'string',
          resizable: true,
          editor: 'input',
          cellEdited: (cell) => {
            handleCellEdit(cell, 'formatString');
          },
          formatter: (cell) => {
            const val = cell.getValue();
            if (!val) return `<span style="color:var(--text-muted);font-size:11px;">-</span>`;
            return `<code style="font-size:11px;background:transparent;padding:0;">${escapeHtml(val)}</code>`;
          }
        },
        {
          title: 'Pasta',
          field: 'displayFolder',
          minWidth: 120,
          sorter: 'string',
          resizable: true,
          editor: 'input',
          cellEdited: (cell) => {
            handleCellEdit(cell, 'displayFolder');
          },
          formatter: (cell) => {
            const val = cell.getValue();
            if (!val) return `<span style="color:var(--text-muted);font-size:11px;">-</span>`;
            return `<span style="font-size:11px;color:var(--text-accent);"><i class="fas fa-folder" style="margin-right:4px;font-size:10px;"></i>${escapeHtml(val)}</span>`;
          }
        },
        {
          title: 'Expressao',
          field: 'expression',
          width: 60,
          minWidth: 50,
          hozAlign: 'center',
          headerSort: false,
          resizable: false,
          formatter: (cell) => {
            const val = cell.getValue();
            if (!val) return '';
            return `<i class="fas fa-code" style="color:#dcdcaa;cursor:pointer;" title="${escapeHtml(val.substring(0,100))}"></i>`;
          },
          cellClick: (e, cell) => {
            const row = cell.getRow().getData();
            if (row.expression) {
              showDAXModal(row.name, row.expression);
            }
          }
        }
      ],
      rowClick: (e, row) => {
        const data = row.getData();
        showDetailPanel(data);
        Grid.highlightRow(row);
      },
      rowSelectionChanged: (data, rows) => {
        updateBatchBar(data, rows);
      },
      dataFiltered: (filters, rows) => {
        const count = rows.length;
        document.getElementById('obj-count').textContent = `${count} objetos`;
      }
    });
  },

  setData(data) {
    this._data = data;
    if (this.table) {
      this.table.setData(data);
    }
  },

  clear() {
    this._data = [];
    if (this.table) {
      this.table.clearData();
    }
  },

  getSelectedRows() {
    if (!this.table) return [];
    return this.table.getSelectedData();
  },

  clearSelection() {
    if (this.table) {
      this.table.deselectRow();
    }
  },

  highlightRow(row) {
    // Just let Tabulator handle selection styling
  },

  updateRow(objectId, field, value) {
    if (!this.table) return;
    const rows = this.table.getRows();
    rows.forEach(row => {
      const data = row.getData();
      if (data.id === objectId) {
        row.update({ [field]: value, _hasPending: true });
      }
    });
  }
};

// ---- Cell Edit Handler ----
async function handleCellEdit(cell, field) {
  const row = cell.getRow().getData();
  const newValue = cell.getValue();
  const oldValue = cell.getOldValue();

  if (newValue === oldValue) return;

  try {
    await API.updateObject(row.objectType, row.id, row.tableId, field, newValue);
    AppState.pendingChanges.add(row.id);
    cell.getRow().update({ _hasPending: true });
    Toast.success(`${field} atualizado`);
    await refreshPending();
  } catch (err) {
    // Revert
    cell.restoreOldValue();
    Toast.error(`Erro ao atualizar ${field}: ${err.message}`);
  }
}

// ---- Toggle Hidden ----
async function toggleHidden(row, cell) {
  const newVal = !row.hidden;
  try {
    await API.updateObject(row.objectType, row.id, row.tableId, 'hidden', newVal);
    AppState.pendingChanges.add(row.id);
    cell.getRow().update({ hidden: newVal, _hasPending: true });
    Toast.success(`Objeto ${newVal ? 'ocultado' : 'exibido'}`);
    await refreshPending();

    // Update detail panel if showing this object
    if (AppState.selectedObject && AppState.selectedObject.id === row.id) {
      AppState.selectedObject.hidden = newVal;
      renderDetailContent(AppState.selectedObject);
    }
  } catch (err) {
    Toast.error(`Erro: ${err.message}`);
  }
}

// ---- Batch Bar ----
function updateBatchBar(selectedData, rows) {
  const bar = document.getElementById('batch-bar');
  const countEl = document.getElementById('batch-count');

  if (selectedData.length > 0) {
    bar.classList.remove('hidden');
    countEl.textContent = `${selectedData.length} selecionado(s)`;
  } else {
    bar.classList.add('hidden');
  }
}

// ---- Initialize grid when DOM ready ----
document.addEventListener('DOMContentLoaded', () => {
  // Wait for Tabulator to load
  const initGrid = () => {
    if (typeof Tabulator !== 'undefined') {
      Grid.init();
    } else {
      setTimeout(initGrid, 100);
    }
  };
  initGrid();
});
