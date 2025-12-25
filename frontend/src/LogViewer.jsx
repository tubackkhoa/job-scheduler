import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import {
  Box,
  Stack,
  Typography,
  IconButton,
  Paper,
  Tooltip,
  TextField,
  Button,
  ButtonGroup,
  CircularProgress,
  Slider,
} from '@mui/material';
import { Terminal, Delete, Search, Refresh } from '@mui/icons-material';
import { API_BASE_URL } from './api';
import { formatMessage, getLevelColor } from './utils';

export default function LogViewer({
  jobInstanceId,
  maxMessages = 500,
  description,
}) {
  const [searchText, setSearchText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [totalLogs, setTotalLogs] = useState(0);
  const [sliderOffset, setSliderOffset] = useState(0); // Offset from latest (0 = latest, 100 = latest-100)
  const [scrollToOffset, setScrollToOffset] = useState(null); // Offset to scroll to
  const [logsUpdateTrigger, setLogsUpdateTrigger] = useState(0); // Trigger for re-rendering merged logs

  const ws = useRef(null);
  const logIdRef = useRef(0);
  const maxMessagesRef = useRef(maxMessages);
  const historicalLogsRef = useRef([]);
  const liveLogsRef = useRef([]);
  const logContainerRef = useRef(null);
  const logElementRefs = useRef(new Map());

  const handleClearLogs = useCallback(() => {
    logIdRef.current = 0;
    historicalLogsRef.current = [];
    liveLogsRef.current = [];
    setTotalLogs(0);
    setSliderOffset(0);
  }, []);

  // Fetch historical logs from API
  const fetchHistoricalLogs = useCallback(
    async (offset = null, search = null, limit = 100) => {
      if (!jobInstanceId) return null;
      const logJobId = jobInstanceId.split('/').join('_');
      setIsLoading(true);
      try {
        const params = new URLSearchParams();
        if (search) params.append('search', search);
        if (offset) params.append('offset', offset.toString());
        params.append('limit', limit.toString());

        const response = await fetch(
          `${API_BASE_URL}/api/logs/${logJobId}?${params.toString()}`
        );
        if (!response.ok) {
          throw new Error('Failed to fetch logs');
        }
        const data = await response.json();

        // Convert API log format to component format
        const formattedLogs = data.logs.map((log) => ({
          id: log.offset,
          time: log.timestamp,
          level: log.level,
          message: log.message,
          offset: log.offset,
          isHistorical: true,
        }));

        setTotalLogs(data.total);

        return {
          logs: formattedLogs,
          total: data.total,
          filtered: data.filtered,
          currentOffset: data.current_offset,
        };
      } catch (error) {
        console.error('Error fetching logs:', error);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [jobInstanceId]
  );

  const mergedLogs = useMemo(() => {
    const allLogs = [...historicalLogsRef.current, ...liveLogsRef.current];

    let filteredLogs = allLogs;
    if (searchText.trim()) {
      const searchLower = searchText.toLowerCase();
      filteredLogs = allLogs.filter(
        (log) =>
          log.message.toLowerCase().includes(searchLower) ||
          log.level.toLowerCase().includes(searchLower)
      );
    }

    filteredLogs.sort((a, b) => {
      if (a.isHistorical && b.isHistorical) {
        return (a.offset || 0) - (b.offset || 0);
      }
      if (a.isHistorical) return -1;
      if (b.isHistorical) return 1;
      return (a.id || 0) - (b.id || 0);
    });

    return filteredLogs;
    // logsUpdateTrigger is needed to trigger recalculation when logs in refs change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText, logsUpdateTrigger]);

  // Load logs based on view mode
  const loadLogs = useCallback(async () => {
    if (!jobInstanceId) return;

    const searchParam = searchText.trim() || null;
    let offset = null;
    let limit = 100;

    if (totalLogs > 0) {
      offset = Math.max(0, totalLogs - sliderOffset - limit);
      if (offset < 0) {
        limit = totalLogs - sliderOffset;
        offset = 0;
      }
    } else {
      // First get total
      const totalResult = await fetchHistoricalLogs(null, searchParam, 1);
      if (totalResult && totalResult.total > 0) {
        setTotalLogs(totalResult.total);
        offset = Math.max(0, totalResult.total - sliderOffset - limit);
        if (offset < 0) {
          limit = totalResult.total - sliderOffset;
          offset = 0;
        }
      }
    }
    const result = await fetchHistoricalLogs(offset, searchParam, limit);
    if (result) {
      historicalLogsRef.current = result.logs;
      setTotalLogs(result.total);
      // Trigger re-render of merged logs
      setLogsUpdateTrigger((prev) => prev + 1);
    }
  }, [jobInstanceId, searchText, sliderOffset, totalLogs, fetchHistoricalLogs]);

  useEffect(() => {
    maxMessagesRef.current = maxMessages;
  }, [maxMessages]);

  useEffect(() => {
    if (jobInstanceId) {
      loadLogs();
    }
  }, [jobInstanceId, loadLogs]);

  useEffect(() => {
    if (!jobInstanceId) return;

    const timeoutId = setTimeout(() => {
      loadLogs();
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
  }, [searchText, jobInstanceId, loadLogs]);

  // Load logs when slider changes (only in slider mode)
  useEffect(() => {
    if (jobInstanceId) {
      loadLogs().then(() => {
        // After logs are loaded, scroll to the target position if needed
        if (scrollToOffset !== null) {
          setTimeout(() => {
            const targetElement = logElementRefs.current.get(scrollToOffset);
            if (targetElement) {
              targetElement.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
              });
              setScrollToOffset(null);
            }
          }, 100);
        }
      });
    }
  }, [sliderOffset, jobInstanceId, loadLogs, scrollToOffset]);

  // Scroll to specific offset when scrollToOffset changes
  useEffect(() => {
    if (scrollToOffset === null || !logContainerRef.current) return;

    // Wait a bit for logs to render, then scroll
    const timeoutId = setTimeout(() => {
      const targetElement = logElementRefs.current.get(scrollToOffset);
      if (targetElement) {
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setScrollToOffset(null);
      } else {
        // If element not found, try again after a short delay
        const retryTimeout = setTimeout(() => {
          const retryElement = logElementRefs.current.get(scrollToOffset);
          if (retryElement) {
            retryElement.scrollIntoView({
              behavior: 'smooth',
              block: 'center',
            });
            setScrollToOffset(null);
          }
        }, 200);
        return () => clearTimeout(retryTimeout);
      }
    }, 100);

    return () => clearTimeout(timeoutId);
  }, [scrollToOffset, mergedLogs]);

  useEffect(() => {
    if (!jobInstanceId) return;
    const url = `${API_BASE_URL.replace(
      /^http/,
      'ws'
    )}/ws/logs/${jobInstanceId}`;
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const items = Array.isArray(data) ? data : [data];
      // 🔑 Assign stable, monotonic indices
      const withIdx = items.map((item) => ({
        ...item,
        id: logIdRef.current++,
        isHistorical: false,
        offset: null,
      }));
      // Add to live logs
      liveLogsRef.current = [...liveLogsRef.current, ...withIdx];
      // Keep only last maxMessages live logs
      if (liveLogsRef.current.length > maxMessagesRef.current) {
        liveLogsRef.current = liveLogsRef.current.slice(
          liveLogsRef.current.length - maxMessagesRef.current
        );
      }
      // Trigger re-render of merged logs
      setLogsUpdateTrigger((prev) => prev + 1);
    };

    ws.current.onclose = () => {
      console.log('WebSocket disconnected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => {
      if (ws.current) {
        ws.current.close();
        handleClearLogs();
      }
    };
  }, [jobInstanceId, handleClearLogs]);

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" alignItems="center" spacing={1}>
          <Terminal fontSize="small" color="action" />
          <Typography variant="body2" color="text.secondary">
            Logs for {description}
          </Typography>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Tooltip title="Refresh logs">
            <IconButton onClick={loadLogs} size="small" disabled={isLoading}>
              <Refresh fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Clear logs">
            <IconButton onClick={handleClearLogs} size="small">
              <Delete fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Stack>

      {/* Search and View Mode Controls */}
      <Stack spacing={2}>
        <Stack direction="row" spacing={2} alignItems="center">
          <TextField
            size="small"
            placeholder="Search logs..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            InputProps={{
              startAdornment: (
                <Search
                  fontSize="small"
                  sx={{ mr: 1, color: 'text.secondary' }}
                />
              ),
            }}
            sx={{ flexGrow: 1 }}
          />
        </Stack>

        {/* Slider for offset selection */}
        <Stack spacing={1}>
          <Stack direction="row" spacing={2} alignItems="center">
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ minWidth: '80px' }}
            >
              Offset: {sliderOffset}
            </Typography>
            <Slider
              value={sliderOffset}
              onChange={(e, newValue) => {
                setSliderOffset(newValue);
              }}
              onChangeCommitted={(e, newValue) => {
                // When user releases slider, calculate target offset and scroll
                // The target offset is the first log in the loaded range
                const targetOffset = Math.max(0, totalLogs - newValue - 100);
                setScrollToOffset(targetOffset);
              }}
              min={0}
              max={Math.max(0, totalLogs - 1)}
              step={1}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => `Latest-${value}`}
              sx={{ flexGrow: 1 }}
            />
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ minWidth: '100px' }}
            >
              Showing: Latest-{sliderOffset}
            </Typography>
          </Stack>
        </Stack>
      </Stack>

      {totalLogs > 0 && (
        <Typography variant="caption" color="text.secondary">
          Showing {mergedLogs.length} of {totalLogs} total logs
          {searchText && ` (filtered from ${totalLogs})`}
        </Typography>
      )}

      <Paper
        ref={logContainerRef}
        variant="outlined"
        sx={{
          p: 2,
          height: 300,
          overflow: 'auto',
          bgcolor: 'rgba(0, 0, 0, 0.4)',
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.85rem',
          borderRadius: 2,
          position: 'relative',
        }}
      >
        {isLoading ? (
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <CircularProgress size={24} />
          </Box>
        ) : mergedLogs.length === 0 ? (
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              {searchText ? 'No logs match your search' : 'No logs available'}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={0.5}>
            {mergedLogs.map((log) => {
              // Highlight search text in message
              const highlightMessage = (text, search) => {
                if (!search || !text) return text;
                const parts = text.split(
                  new RegExp(
                    `(${search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`,
                    'gi'
                  )
                );
                return parts.map((part, i) =>
                  part.toLowerCase() === search.toLowerCase() ? (
                    <span
                      key={i}
                      style={{ backgroundColor: 'rgba(255, 255, 0, 0.3)' }}
                    >
                      {part}
                    </span>
                  ) : (
                    part
                  )
                );
              };

              const logKey = log.id || log.offset || `log-${Math.random()}`;
              const logOffset = log.offset || log.id;

              return (
                <Stack
                  key={logKey}
                  ref={(el) => {
                    if (el && logOffset !== null && logOffset !== undefined) {
                      logElementRefs.current.set(logOffset, el);
                    }
                  }}
                  direction="row"
                  spacing={2}
                  sx={{
                    scrollMargin: '50px', // Add margin for scrollIntoView
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{
                      fontFamily: 'inherit',
                      flexShrink: 0,
                      minWidth: '140px',
                    }}
                  >
                    {log.time || log.timestamp || ''}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: 'inherit',
                      color: getLevelColor(log.level),
                      textTransform: 'uppercase',
                      fontWeight: 600,
                      flexShrink: 0,
                      minWidth: '80px',
                    }}
                  >
                    [{log.level}]
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: 'inherit',
                      color: 'text.primary',
                      opacity: 0.9,
                    }}
                  >
                    {highlightMessage(formatMessage(log.message), searchText)}
                  </Typography>
                </Stack>
              );
            })}
          </Stack>
        )}
      </Paper>
    </Stack>
  );
}
