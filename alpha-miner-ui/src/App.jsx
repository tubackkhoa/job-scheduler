import { useEffect, useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Container
} from '@mui/material';
import Form from '@rjsf/mui';
import validator from '@rjsf/validator-ajv8';
import api from './api';

const theme = createTheme({
  palette: {
    mode: 'dark', // or "light"
    primary: {
      main: '#7C4DFF' // Deep purple
    },
    secondary: {
      main: '#00E5FF' // Cyan accent
    },
    background: {
      default: '#0F1117',
      paper: '#161A23'
    }
  },
  shape: {
    borderRadius: 10
  },
  typography: {
    fontFamily: 'Inter, Roboto, sans-serif',
    h6: {
      fontWeight: 600
    }
  }
});

export default function App() {
  const [plugins, setPlugins] = useState([]);
  const [pluginId, setPluginId] = useState(0);
  const [activeVersion, setActiveVersion] = useState('');
  const [configVersions, setConfigVersions] = useState([]);
  const [schema, setSchema] = useState(null);
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

  const loadSchema = async (pluginId) => {
    setPluginId(pluginId);
    setLoading(true);
    setError(null);
    setSchema(null);
    setResult(null);

    try {
      const { schema, configs } = await api.fetchSchema(pluginId);
      setSchema(schema);
      setConfigVersions(configs);
      setActiveVersion(configs[0].id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async ({ formData }) => {
    if (!pluginId) return;

    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.updateConfig(activeVersion, formData);
      configVersions.find((version) => version.id === activeVersion).config =
        JSON.stringify(response);
      setConfigVersions(configVersions);
      setResult(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <Container sx={{ minHeight: '100vh' }}>
        <h1>Alpha Miner – Plugin Config</h1>
        <Box
          sx={{
            display: 'flex',
            gap: 2, // space between items (8px * 2 = 16px)
            alignItems: 'center', // vertically align inputs
            flexWrap: 'wrap' // allow wrapping on small screens
          }}
        >
          <FormControl size="small" sx={{ minWidth: 360 }}>
            <InputLabel id="plugin-select-label">
              -- Select a plugin --
            </InputLabel>
            <Select
              labelId="plugin-select-label"
              value={pluginId}
              label="-- Select a plugin --"
              onChange={(e) => loadSchema(Number(e.target.value))}
            >
              {plugins.map((plugin) => (
                <MenuItem key={plugin.id} value={plugin.id}>
                  {plugin.package}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 360 }}>
            <InputLabel id="config-version-select-label">
              -- Select a config version --
            </InputLabel>
            <Select
              labelId="config-version-select-label"
              value={activeVersion}
              label="-- Select a config version --"
              onChange={(e) => setActiveVersion(e.target.value)}
            >
              {configVersions.map((version) => (
                <MenuItem key={version.id} value={version.id}>
                  {version.description}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {loading && <p>Loading schema...</p>}
        {error && <p style={{ color: 'red' }}>{error}</p>}

        {schema && (
          <div style={{ marginTop: 24 }}>
            <Form
              schema={schema}
              formData={JSON.parse(
                configVersions.find((version) => version.id === activeVersion)
                  .config
              )}
              validator={validator}
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
      </Container>
    </ThemeProvider>
  );
}
