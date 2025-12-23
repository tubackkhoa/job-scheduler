import { useEffect, useState, useRef } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Container,
  FormControl,
  Grid,
  IconButton,
  Input,
  InputLabel,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  Switch,
  Tab,
  Tabs,
  Tooltip,
  Typography
} from '@mui/material';
import { Pause, PlayArrow, Refresh, Add, ContentCopy } from '@mui/icons-material';

import Form from '@rjsf/mui';
import validator from '@rjsf/validator-ajv8';
import api from './api';
import LogViewer from './LogViewer';
import { MLThresholdsTableField, MultiSelectField } from './fields';
import { extractUiSchema, getSystemTheme } from './utils';

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
  const [mode, setMode] = useState(getSystemTheme());
  const [plugins, setPlugins] = useState([]);
  const [pluginId, setPluginId] = useState(0);
  const [jobId, setJobId] = useState(0);
  const [jobDesc, setJobDesc] = useState('');
  const [newJobDraft, setNewJobDraft] = useState(null);
  const [configVersions, setConfigVersions] = useState([]);
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [userId, setUserId] = useState(users[0].id);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('config');
  const [copiedJson, setCopiedJson] = useState(false);
  const formRef = useRef(null);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    // Event handler for changes
    const handleChange = (event) => {
      setMode(event.matches ? 'dark' : 'light');
    };

    // Listen for changes
    mediaQuery.addEventListener('change', handleChange);

    // Cleanup listener on unmount
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Create theme based on current mode
  const theme = createTheme({
    palette: {
      mode
    }
  });

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
      const templateConfig =
        configs.find((c) => c.id === 0)?.config ?? configs[0]?.config ?? '{}';
      setNewJobDraft({
        id: 0,
        description: '',
        active: 0,
        config: templateConfig
      });
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

  const handleJobActivation = async (activation, targetJobId = jobId) => {
    setError(null);
    if (!targetJobId) return;
    try {
      const response = await api.activateJob(targetJobId, activation);
      if (response.success) {
        // update the config at local to sync with server
        const newConfigVersions = [...configVersions];
        for (const version of newConfigVersions) {
          if (version.id === targetJobId) {
            version.active = activation ? 1 : 0;
          } else {
            version.active = 0;
          }
        }
        setConfigVersions(newConfigVersions);
        setJobId(targetJobId);
      }
      handleSetResult(response);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleChangeJob = (newJobId, configs) => {
    setJobId(newJobId);
    const collection = configs ?? configVersions;
    const found = collection.find((version) => version.id === newJobId);
    setJobDesc(found?.description ?? '');
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

  const reloadPlugins = async () => {
    if (!pluginId) return;

    setSubmitting(true);
    setError(null);

    try {
      const pkg = plugins.find((p) => p.id === pluginId).package;
      const response = await api.reloadPlugin(pkg);
      handleSetResult(response);
      // update schema
      loadSchema(pluginId, userId, jobId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const currentConfig = configVersions.find((version) => version.id === jobId);
  const displayedConfig = jobId === 0 ? newJobDraft : currentConfig;
  const pluginInfo = plugins.find((p) => p.id === pluginId);
  const formData = displayedConfig
    ? JSON.parse(displayedConfig.config ?? '{}')
    : null;
  const isActive = (currentConfig?.active ?? 0) === 1;

  const handleCopyJson = async () => {
    if (!formData) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(formData, null, 2));
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 1500);
    } catch (err) {
      console.error('Copy failed', err);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <Container sx={{ minHeight: '100vh', pb: 4 }}>
        <Box sx={{ py: 2 }}>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Job Scheduler Dashboard
          </Typography>
          <Typography variant="subtitle1" sx={{ color: '#9da3af' }}>
            Manage plugins, jobs, configurations, and live logs in one view.
          </Typography>
        </Box>

        {(loading || submitting) && <LinearProgress sx={{ mb: 2 }} />}
        {error && (
          <Box
            sx={{
              p: 2,
              mb: 2,
              borderRadius: 2,
              border: '1px solid #b71c1c',
              background: 'rgba(183,28,28,0.1)',
              color: '#ffcdd2'
            }}
          >
            {error}
          </Box>
        )}

        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <Card
              sx={{
                mb: 2,
                border: '1px solid #1f2937',
                backgroundColor: '#0f1117'
              }}
            >
              <CardHeader
                title="Context"
                subheader="Choose user and plugin"
                subheaderTypographyProps={{ sx: { color: '#9da3af' } }}
              />
              <CardContent>
                <Stack spacing={2}>
                  <FormControl size="small">
                    <InputLabel id="user-select-label">User</InputLabel>
                    <Select
                      labelId="user-select-label"
                      value={userId}
                      label="User"
                      onChange={(e) => handleChangeUser(e.target.value)}
                    >
                      {users.map((user) => (
                        <MenuItem key={user.id} value={user.id}>
                          {user.fullName}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <Stack direction="row" spacing={1} alignItems="center">
                    <FormControl size="small" fullWidth>
                      <InputLabel id="plugin-select-label">Plugin</InputLabel>
                      <Select
                        labelId="plugin-select-label"
                        value={pluginId}
                        label="Plugin"
                        onChange={(e) => loadSchema(Number(e.target.value))}
                      >
                        {plugins.map((plugin) => (
                          <MenuItem
                            key={plugin.id}
                            value={plugin.id}
                            title={plugin.description}
                          >
                            {plugin.package} (interval {plugin.interval}s)
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>

                    {!!pluginId && (
                      <IconButton
                        color="warning"
                        onClick={reloadPlugins}
                        title="Reload plugin (development)"
                      >
                        <Refresh />
                      </IconButton>
                    )}
                  </Stack>
                </Stack>
              </CardContent>
            </Card>

            <Card
              sx={{
                border: '1px solid #1f2937',
                backgroundColor: '#0f1117'
              }}
            >
              <CardHeader
                title="Jobs"
                subheader="Select, start, pause, or add a job"
                subheaderTypographyProps={{ sx: { color: '#9da3af' } }}
                action={
                  <Button
                    size="small"
                    startIcon={<Add />}
                    variant="contained"
                    disabled={!schema}
                    onClick={() => {
                      setJobId(0);
                      setJobDesc('');
                      setActiveTab('config');
                    }}
                  >
                    New
                  </Button>
                }
              />
              <CardContent sx={{ maxHeight: 520, overflowY: 'auto', pt: 0 }}>
                <List dense>
                  {configVersions.map((version) => (
                    <ListItemButton
                      key={version.id}
                      selected={jobId === version.id}
                      onClick={() => {
                        handleChangeJob(version.id);
                        setActiveTab('config');
                      }}
                      sx={{
                        mb: 1,
                        borderRadius: 1,
                        border: '1px solid #1f2937',
                        backgroundColor:
                          jobId === version.id ? '#161a23' : 'transparent'
                      }}
                    >
                      <ListItemText
                        primary={
                          <Stack
                            direction="row"
                            alignItems="center"
                            spacing={1}
                          >
                            <Typography variant="body1">
                              {version.description || 'Untitled job'}
                            </Typography>
                            {version.active ? (
                              <Chip
                                label="Active"
                                color="success"
                                size="small"
                              />
                            ) : (
                              <Chip
                                label="Paused"
                                color="default"
                                size="small"
                              />
                            )}
                          </Stack>
                        }
                        secondary={
                          <Typography variant="caption" sx={{ color: '#9da3af' }}>
                            #{version.id} • {pluginInfo?.package || 'Plugin'}
                          </Typography>
                        }
                      />
                      <Switch
                        edge="end"
                        checked={!!version.active}
                        onChange={(e) =>
                          handleJobActivation(e.target.checked, version.id)
                        }
                      />
                    </ListItemButton>
                  ))}
                  {!configVersions.length && (
                    <Typography variant="body2" sx={{ color: '#9da3af' }}>
                      No jobs yet. Pick a plugin to load defaults.
                    </Typography>
                  )}
                </List>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={8}>
            <Card
              sx={{
                border: '1px solid #1f2937',
                backgroundColor: '#0f1117'
              }}
            >
              <CardHeader
                title="Job Details"
                subheader={
                  pluginInfo
                    ? `${pluginInfo.package} • every ${pluginInfo.interval}s`
                    : 'Select a plugin to begin'
                }
                subheaderTypographyProps={{ sx: { color: '#9da3af' } }}
                action={
                  !!currentConfig && (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip
                        size="small"
                        label={isActive ? 'Active' : 'Paused'}
                        color={isActive ? 'success' : 'default'}
                        variant={isActive ? 'filled' : 'outlined'}
                        sx={{ mr: 1 }}
                      />
                      <Button
                        size="small"
                        variant={isActive ? 'outlined' : 'contained'}
                        color={isActive ? 'warning' : 'success'}
                        startIcon={isActive ? <Pause /> : <PlayArrow />}
                        disabled={!pluginId || submitting}
                        onClick={() => handleJobActivation(!isActive)}
                      >
                        {isActive ? 'Pause' : 'Start'}
                      </Button>
                    </Stack>
                  )
                }
              />
              <CardContent>
                {schema && displayedConfig && (
                  <Stack spacing={2}>
                    <FormControl fullWidth>
                      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                        Description
                      </Typography>
                      <Input
                        value={jobDesc}
                        onChange={(e) => setJobDesc(e.target.value)}
                        placeholder="Short note for this job"
                      />
                    </FormControl>

                    <Tabs
                      value={activeTab}
                      onChange={(_, v) => setActiveTab(v)}
                      textColor="secondary"
                      indicatorColor="secondary"
                      sx={{ borderBottom: '1px solid #1f2937' }}
                    >
                      <Tab label="Config Form" value="config" />
                      <Tab label="Config JSON" value="json" />
                      <Tab label="Live Logs" value="logs" />
                    </Tabs>

                    {activeTab === 'config' && (
                      <Form
                        schema={schema}
                        uiSchema={uiSchema}
                        ref={formRef}
                        fields={{
                          MLThresholdsTable: MLThresholdsTableField,
                          MultiSelect: MultiSelectField
                        }}
                        formData={formData}
                        validator={validator}
                        onSubmit={handleSubmit}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            flexWrap: 'wrap',
                            gap: 2,
                            mt: 1
                          }}
                        >
                          <Stack direction="row" spacing={1}>
                            <Button
                              variant="contained"
                              type="submit"
                              disabled={submitting || !pluginId}
                            >
                              {submitting ? 'Saving…' : 'Save'}
                            </Button>
                            <Button
                              variant="outlined"
                              disabled={submitting || !pluginId}
                              onClick={() => {
                                handleSubmit({
                                  formData: formRef.current.state.formData,
                                  saveNew: true
                                });
                              }}
                            >
                              Save as new
                            </Button>
                          </Stack>

                          {jobId !== 0 && (
                            <Button
                              variant="outlined"
                              color="error"
                              disabled={submitting}
                              onClick={handleDeleteJob}
                            >
                              Delete
                            </Button>
                          )}
                        </Box>
                      </Form>
                    )}

                    {activeTab === 'json' && (
                      <Box
                        sx={{
                          p: 2,
                          borderRadius: 2,
                          backgroundColor: '#0b0d13',
                          border: '1px solid #1f2937',
                          fontFamily: 'monospace',
                          fontSize: '0.9rem',
                          whiteSpace: 'pre-wrap',
                          position: 'relative'
                        }}
                      >
                        <Tooltip title={copiedJson ? 'Copied!' : 'Copy JSON'}>
                          <IconButton
                            size="small"
                            onClick={handleCopyJson}
                            sx={{ position: 'absolute', top: 8, right: 8 }}
                          >
                            <ContentCopy fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {JSON.stringify(formData, null, 2)}
                      </Box>
                    )}

                    {activeTab === 'logs' && (
                      <LogViewer jobInstanceId={`${pluginId}/${userId}`} />
                    )}
                  </Stack>
                )}

                {!schema && (
                  <Typography variant="body2" sx={{ color: '#9da3af' }}>
                    Pick a plugin to load its schema and jobs.
                  </Typography>
                )}
              </CardContent>
            </Card>

            {result && (
              <Card
                sx={{
                  mt: 2,
                  border: '1px solid #1f2937',
                  backgroundColor: '#0b0d13'
                }}
              >
                <CardHeader title="Server response" />
                <CardContent>
                  <pre
                    style={{
                      margin: 0,
                      background: '#000',
                      color: '#0f0',
                      padding: 16,
                      borderRadius: 6,
                      maxHeight: 320,
                      overflow: 'auto'
                    }}
                  >
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
          </Grid>
        </Grid>
      </Container>
    </ThemeProvider>
  );
}
