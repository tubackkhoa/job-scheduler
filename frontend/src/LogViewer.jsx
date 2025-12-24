import { useEffect, useState, useRef } from 'react';
import {
  Box,
  Stack,
  Typography,
  IconButton,
  Paper,
  Tooltip,
} from '@mui/material';
import { Terminal, Delete } from '@mui/icons-material';
import { API_BASE_URL } from './api';

// Map log levels to MUI color palette or CSS colors
const LEVEL_STYLES = {
  INFO: { color: '#4fc3f7', bg: 'rgba(79, 195, 247, 0.15)' },
  ERROR: { color: '#ef5350', bg: 'rgba(239, 83, 80, 0.15)' },
  WARNING: { color: '#ffb74d', bg: 'rgba(255, 183, 77, 0.15)' },
  DEBUG: { color: '#ba68c8', bg: 'rgba(186, 104, 200, 0.15)' }
};

const DEFAULT_STYLE = { color: '#d4d4d4', bg: 'transparent' };

/**
 * Formats ugly Python datetime repr strings like:
 * "datetime.datetime(2025, 12, 18, 10, 57, 15, 461066, tzinfo=...)"
 * → "12/18/2025, 10:57:15 AM"
 */
function formatMessage(message) {
  if (typeof message !== 'string') return message;

  return message.replace(
    /\[?datetime\.datetime\(([^)]+)\)/g,
    (match, dtStr) => {
      try {
        const parts = dtStr.split(', ').map(Number);
        const [year, month, day, hour, minute, second] = parts;
        const date = new Date(year, month - 1, day, hour, minute, second || 0);
        return date.toLocaleString(undefined, {
          year: 'numeric',
          month: 'numeric',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true
        });
      } catch {
        return match; // fallback if parsing fails
      }
    }
  );
}

export default function LogViewer({ jobInstanceId, maxMessages = 500 }) {
  const [logs, setLogs] = useState([]);
  const ws = useRef(null);
  const logIdRef = useRef(0);
  const maxMessagesRef = useRef(maxMessages);

  const handleClearLogs = () => {
    setLogs([]);
    logIdRef.current = 0;
  };

  const getLevelColor = (level) => {
    switch (level) {
      case 'ERROR':
        return 'error.main';
      case 'WARNING':
        return 'warning.main';
      default:
        return 'primary.main';
    }
  };

  useEffect(() => {
    maxMessagesRef.current = maxMessages;
  }, [maxMessages]);

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
        id: logIdRef.current++
      }));
      // Always use latest jobInstanceId
      setLogs((prevLogs) => {
        const next = [...prevLogs, ...withIdx];
        if (next.length > maxMessagesRef.current) {
          return next.slice(next.length - maxMessagesRef.current);
        }
        return next;
      });
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
  }, [jobInstanceId]);

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" alignItems="center" spacing={1}>
          <Terminal fontSize="small" color="action" />
          <Typography variant="body2" color="text.secondary">
            Live logs for {jobInstanceId}
          </Typography>
        </Stack>
        <Tooltip title="Clear logs">
          <IconButton onClick={handleClearLogs} size="small">
            <Delete fontSize="small" />
          </IconButton>
        </Tooltip>
      </Stack>

    <Paper
          variant="outlined"
        sx={{
          p: 2,
          height: 300,
          overflow: 'auto',
          bgcolor: 'rgba(0, 0, 0, 0.4)',
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.85rem',
          borderRadius: 2,
        }}
      >
        {logs.length === 0 ? (
              <Box
                sx={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No logs available
            </Typography>
              </Box>
        ) : (
          <Stack spacing={0.5}>
            {logs.map((log) => (
                <Stack key={log.id} direction="row" spacing={2}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontFamily: 'inherit', flexShrink: 0 }}
                  >
                    {log.time}
                  </Typography>
              <Typography
                variant="caption"
                sx={{
                      fontFamily: 'inherit',
                      color: getLevelColor(log.level),
                      textTransform: 'uppercase',
                      fontWeight: 600,
                      flexShrink: 0,
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
                {formatMessage(log.message)}
              </Typography>
                </Stack>
            ))}
          </Stack>
        )}
    </Paper>
    </Stack>
  );
}
