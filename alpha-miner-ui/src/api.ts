export const API_BASE_URL = 'http://localhost:8000';

export default {
  async fetchSchema(pluginId: number) {
    const res = await fetch(`${API_BASE_URL}/schema/${pluginId}`);

    if (!res.ok) {
      throw new Error(`Schema not found for ${pluginId}`);
    }

    return res.json();
  },

  async fetchPlugins() {
    const res = await fetch(`${API_BASE_URL}/plugins`);

    if (!res.ok) {
      throw new Error('Failed to load plugins');
    }

    return res.json();
  },
  async updateConfig(jobId: number, payload: Object) {
    const res = await fetch(`${API_BASE_URL}/config/${jobId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || 'Plugin execution failed');
    }

    return res.json();
  },
  async activateJob(jobId: number, activation: boolean) {
    const res = await fetch(`${API_BASE_URL}/activate/${jobId}/${activation}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || 'Plugin activation failed');
    }

    return res.json();
  }
};
