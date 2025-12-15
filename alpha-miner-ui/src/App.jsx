import { useEffect, useState } from 'react';
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import api from './api';

export default function App() {
  const [plugins, setPlugins] = useState([]);
  const [pluginName, setPluginName] = useState('');
  const [schema, setSchema] = useState(null);
  const [formData, setFormData] = useState({});
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Load plugin list
  useEffect(() => {
    api
      .fetchPlugins()
      .then(setPlugins)
      .catch((err) => setError(err.message));
  }, []);

  const loadSchema = async (pluginName) => {
    if (!pluginName) return;
    setPluginName(pluginName);
    setLoading(true);
    setError(null);
    setSchema(null);
    setFormData({});
    setResult(null);

    try {
      const { schema, data } = await api.fetchSchema(pluginName);
      setSchema(schema);
      setFormData(data ?? {});
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async ({ formData }) => {
    console.log(pluginName, formData);
    if (!pluginName) return;

    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.updateConfig(pluginName, formData);
      setResult(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Alpha Miner – Plugin Config</h1>

      <select
        value={pluginName}
        onChange={(e) => {
          loadSchema(e.target.value);
        }}
        style={{ width: 360, marginRight: 8 }}
      >
        <option value="">-- Select a plugin --</option>
        {plugins.map((plugin) => (
          <option key={plugin} value={plugin}>
            {plugin}
          </option>
        ))}
      </select>

      {loading && <p>Loading schema...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {schema && (
        <div style={{ marginTop: 24 }}>
          <Form
            schema={schema}
            formData={formData}
            validator={validator}
            onChange={(e) => setFormData(e.formData)}
            onSubmit={handleSubmit}
          >
            <button type="submit" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit'}
            </button>
          </Form>
        </div>
      )}

      {result && (
        <pre
          style={{
            marginTop: 24,
            background: '#111',
            color: '#0f0',
            padding: 16,
            borderRadius: 6,
            maxHeight: 400,
            overflow: 'auto'
          }}
        >
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}
