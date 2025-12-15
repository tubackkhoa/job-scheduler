const API_BASE_URL = 'http://localhost:8000';

export default {
  async fetchSchema(pluginName: string) {
    const res = await fetch(`${API_BASE_URL}/schema/${pluginName}`);

    if (!res.ok) {
      throw new Error(`Schema not found for ${pluginName}`);
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
  async updateConfig(pluginName: string, payload: Object) {
    const res = await fetch(`${API_BASE_URL}/config/${pluginName}`, {
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
  }
};
