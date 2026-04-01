/**
 * API Module - Communication layer with the FastAPI backend
 */
const API = {
  BASE: 'http://localhost:8000',
  token: localStorage.getItem('pbix_token'),

  async request(method, path, body = null, params = null) {
    const url = new URL(this.BASE + path);
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== null && v !== undefined) url.searchParams.append(k, v);
      });
    }

    const headers = { 'Content-Type': 'application/json' };
    if (this.token) {
      headers['Authorization'] = 'Bearer ' + this.token;
    }

    const opts = { method, headers };
    if (body !== null) {
      opts.body = JSON.stringify(body);
    }

    const resp = await fetch(url.toString(), opts);

    if (resp.status === 401) {
      this.token = null;
      localStorage.removeItem('pbix_token');
      throw new Error('Nao autenticado. Faca login novamente.');
    }

    if (!resp.ok) {
      let errMsg = `HTTP ${resp.status}`;
      try {
        const errData = await resp.json();
        errMsg = errData.detail || errData.message || errMsg;
      } catch (_) { /* ignore parse error */ }
      throw new Error(errMsg);
    }

    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      return await resp.json();
    }
    return await resp.text();
  },

  async get(path, params = null) {
    return this.request('GET', path, null, params);
  },

  async post(path, body = null, params = null) {
    return this.request('POST', path, body, params);
  },

  // ---- Auth ----
  async login(username, password) {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);

    const resp = await fetch(this.BASE + '/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString()
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Credenciais invalidas');
    }

    const data = await resp.json();
    this.token = data.access_token;
    localStorage.setItem('pbix_token', this.token);
    return data;
  },

  async logout() {
    this.token = null;
    localStorage.removeItem('pbix_token');
  },

  // ---- Connections ----
  async getStatus() {
    return this.get('/api/connections/status');
  },

  async connectLocal() {
    return this.post('/api/connections/connect', { mode: 'LOCAL' });
  },

  async connectRemote(workspace, model, username, password) {
    return this.post('/api/connections/connect', {
      mode: 'REMOTE',
      workspaceName: workspace,
      modelName: model,
      username: username || null,
      password: password || null
    });
  },

  async disconnect() {
    return this.post('/api/connections/disconnect');
  },

  async getDatabases() {
    return this.get('/api/connections/databases');
  },

  // ---- Metadata ----
  async getMetadata(forceReload = false) {
    return this.get('/api/metadata/', { force_reload: forceReload || null });
  },

  async getTables() {
    return this.get('/api/metadata/tables');
  },

  async getTable(tableId) {
    return this.get(`/api/metadata/tables/${encodeURIComponent(tableId)}`);
  },

  async renameTable(tableId, newName) {
    return this.post(`/api/metadata/tables/${encodeURIComponent(tableId)}/rename`, null, { new_name: newName });
  },

  async setTableHidden(tableId, hidden) {
    return this.post(`/api/metadata/tables/${encodeURIComponent(tableId)}/hidden`, null, { hidden });
  },

  async deleteTable(tableId) {
    return this.post(`/api/metadata/tables/${encodeURIComponent(tableId)}/delete`);
  },

  async getRelationships() {
    return this.get('/api/metadata/relationships');
  },

  async getObjects(tableId = null, objectType = null, search = null, hidden = null) {
    const params = {};
    if (tableId) params.table_id = tableId;
    if (objectType && objectType !== 'all') params.object_type = objectType;
    if (search) params.search = search;
    if (hidden !== null) params.hidden = hidden;
    return this.get('/api/metadata/objects', params);
  },

  async updateObject(objectType, objectId, tableId, field, value) {
    return this.post('/api/metadata/update', {
      objectType,
      objectId,
      tableId,
      field,
      value
    });
  },

  // ---- Pending Changes ----
  async getPending() {
    return this.get('/api/metadata/pending');
  },

  async discardChanges() {
    return this.post('/api/metadata/discard');
  },

  async commitChanges() {
    return this.post('/api/metadata/commit');
  },

  async exportBackup() {
    return this.get('/api/metadata/backup');
  },

  async getAuditLog(limit = 100) {
    return this.get('/api/metadata/audit', { limit });
  },

  // ---- Batch ----
  async batchUpdate(updates, applyImmediately = false) {
    return this.post('/api/batch/update', { updates, applyImmediately });
  },

  async batchHide(ids, tableId, objectType) {
    const params = { table_id: tableId, object_type: objectType };
    return this.request('POST', '/api/batch/hide', ids, params);
  },

  async batchShow(ids, tableId, objectType) {
    const params = { table_id: tableId, object_type: objectType };
    return this.request('POST', '/api/batch/show', ids, params);
  },

  async batchSetFolder(ids, tableId, objectType, folder) {
    const params = { table_id: tableId, object_type: objectType, folder };
    return this.request('POST', '/api/batch/set-display-folder', ids, params);
  },

  async batchSetDescription(ids, tableId, objectType, description) {
    const params = { table_id: tableId, object_type: objectType, description };
    return this.request('POST', '/api/batch/set-description', ids, params);
  }
};
