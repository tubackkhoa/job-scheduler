import { useEffect, useState, useRef } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Input,
  Checkbox,
  Box,
  Container,
  Typography
} from '@mui/material';
import Form from '@rjsf/mui';
import validator from '@rjsf/validator-ajv8';
import api, { API_BASE_URL } from './api';
import LogViewer from './LogViewer';

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

const users = [
  {
    id: 1,
    fullName: 'Chung Dao'
  },
  {
    id: 2,
    fullName: 'Ngoc Diep'
  }
];

export default function App() {
  const [plugins, setPlugins] = useState([]);
  const [pluginId, setPluginId] = useState(0);
  const [jobId, setJobId] = useState(0);
  const [jobDesc, setJobDesc] = useState('');
  const [configVersions, setConfigVersions] = useState([]);
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [userId, setUserId] = useState(users[0].id);
  const [error, setError] = useState(null);
  const formRef = useRef(null);

  // Load plugin list
  useEffect(() => {
    api
      .fetchPlugins()
      .then(setPlugins)
      .catch((err) => setError(err.message));
  }, []);

  const handleSetResult = (ret) => {
    setResult(ret);
    setTimeout(() => setResult(null), 3000);
  };

  const loadSchema = async (currentPluginId, currentUserId, currentJobId) => {
    if (!currentPluginId) return;
    setPluginId(currentPluginId);
    setLoading(true);
    setError(null);
    setSchema(null);

    try {
      const { schema, configs } = await api.fetchSchema(
        currentUserId ?? userId,
        currentPluginId
      );
      setSchema(schema);
      setConfigVersions(configs);
      const newJobId = currentJobId ?? configs[0].id;
      handleChangeJob(newJobId, configs);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async ({ formData, saveNew = false }) => {
    if (!pluginId) return;

    setSubmitting(true);
    setError(null);

    try {
      const jobItem = {
        config: formData,
        description: jobDesc
      };
      let response;
      if (!jobId || saveNew) {
        // add new job
        response = await api.updateConfig(0, { ...jobItem, userId, pluginId });
      } else {
        response = await api.updateConfig(jobId, jobItem);
      }

      handleSetResult(response);
      await loadSchema(pluginId, userId, jobId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleJobActivation = async (activation) => {
    setError(null);
    try {
      const response = await api.activateJob(jobId, activation);
      if (response.success) {
        // update the config at local to sync with server
        const newConfigVersions = [...configVersions];
        for (const version of newConfigVersions) {
          if (version.id === jobId) {
            version.active = activation ? 1 : 0;
          } else {
            version.active = 0;
          }
        }
        setConfigVersions(newConfigVersions);
      }
      handleSetResult(response);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleChangeJob = (newJobId, configs) => {
    setJobId(newJobId);
    setJobDesc(
      (configs ?? configVersions).find((version) => version.id === newJobId)
        ?.description ?? ''
    );
  };

  const handleChangeUser = async (currentUserId) => {
    setUserId(currentUserId);
    // reload schema
    await loadSchema(pluginId, currentUserId);
  };

  const handleDeleteJob = async () => {
    if (!pluginId) return;

    setSubmitting(true);
    setError(null);

    try {
      const response = await api.deleteJob(jobId);
      handleSetResult(response);
      await loadSchema(pluginId, userId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const currentConfig = configVersions.find((version) => version.id === jobId);
  const currentPlugin = plugins.find((p) => p.id === pluginId);

  return (
    <ThemeProvider theme={theme}>
      <Container sx={{ minHeight: '100vh', padding: 10 }}>
        <h1>Alpha Miner – Plugin Config</h1>
        <Box
          sx={{
            display: 'flex',
            gap: 2, // space between items (8px * 2 = 16px)
            alignItems: 'center', // vertically align inputs
            flexWrap: 'wrap' // allow wrapping on small screens
          }}
        >
          <FormControl size="small">
            <InputLabel id="config-version-select-label">
              -- Select user --
            </InputLabel>
            <Select
              labelId="config-version-select-label"
              value={userId}
              onChange={(e) => {
                handleChangeUser(e.target.value);
              }}
            >
              {users.map((user) => (
                <MenuItem key={user.id} value={user.id}>
                  {user.fullName}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

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
                <MenuItem
                  key={plugin.id}
                  value={plugin.id}
                  title={plugin.description}
                >
                  {plugin.package} (interval {plugin.interval} seconds)
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 360 }}>
            <InputLabel id="config-version-select-label">
              -- Select a job --
            </InputLabel>
            <Select
              labelId="config-version-select-label"
              value={jobId}
              label="-- Select a job --"
              onChange={(e) => {
                handleChangeJob(e.target.value);
              }}
            >
              {configVersions.map((version) => (
                <MenuItem key={version.id} value={version.id}>
                  {version.description} {version.active ? ' (active)' : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {currentPlugin && userId && (
          <LogViewer
            url={API_BASE_URL.replace(/^http/, 'ws') + '/ws/logs'}
            maxMessages={300}
            jobInstanceId={`${currentPlugin.package}/${userId}`}
          />
        )}

        {loading && <p>Loading schema...</p>}
        {error && <p style={{ color: 'red' }}>{error}</p>}
        {schema && (
          <FormControl sx={{ my: 2 }} fullWidth>
            <Typography variant="h5">Description</Typography>
            <Input
              value={jobDesc}
              onChange={(e) => setJobDesc(e.target.value)}
            />
          </FormControl>
        )}
        {schema && currentConfig && (
          <Form
            schema={schema}
            ref={formRef}
            formData={JSON.parse(currentConfig.config)}
            validator={validator}
            onSubmit={handleSubmit}
          >
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between'
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  gap: 2
                }}
              >
                <Button variant="contained" type="submit" disabled={submitting}>
                  {submitting ? 'Saving…' : 'Save'}
                </Button>
                <InputLabel>
                  <Checkbox
                    checked={currentConfig.active}
                    onChange={(e) => handleJobActivation(e.target.checked)}
                  />
                  Activate
                </InputLabel>
              </Box>

              {jobId !== 0 && (
                <Box
                  sx={{
                    display: 'flex',
                    gap: 2
                  }}
                >
                  <Button
                    variant="contained"
                    color="secondary"
                    disabled={submitting}
                    onClick={() => {
                      handleSubmit({
                        formData: formRef.current.state.formData,
                        saveNew: true
                      });
                    }}
                  >
                    Save as new
                  </Button>

                  <Button
                    variant="contained"
                    color="error"
                    disabled={submitting}
                    onClick={handleDeleteJob}
                  >
                    Delete
                  </Button>
                </Box>
              )}
            </Box>
          </Form>
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
