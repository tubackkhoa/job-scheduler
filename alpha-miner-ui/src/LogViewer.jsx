import { useEffect, useState, useRef } from 'react';
import { Box, Typography, Paper, Button } from '@mui/material';

// Map log levels to MUI color palette or CSS colors
const LEVEL_STYLES = {
  INFO: { color: '#4fc3f7', bg: 'rgba(79, 195, 247, 0.15)' },
  ERROR: { color: '#ef5350', bg: 'rgba(239, 83, 80, 0.15)' },
  WARN: { color: '#ffb74d', bg: 'rgba(255, 183, 77, 0.15)' },
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

export default function LogViewer({ url, jobInstanceId, maxMessages = 500 }) {
  const [logs, setLogs] = useState([]);
  const ws = useRef(null);
  const jobIdRef = useRef(jobInstanceId);

  useEffect(() => {
    jobIdRef.current = jobInstanceId;
    setLogs([]);
  }, [jobInstanceId]);

  useEffect(() => {
    if (!url) return;
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // Always use latest jobInstanceId
      if (data.job_id !== jobIdRef.current) return;
      setLogs((prevLogs) => {
        const next = [...prevLogs, data];
        if (next.length > maxMessages) {
          return next.slice(next.length - maxMessages);
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
      }
    };
  }, [url]);

  const handleClearLogs = () => {
    setLogs([]);
  };

  return (
    <Paper
      elevation={3}
      sx={{
        mt: 2,
        height: 400,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#000',
        border: '1px solid #444',
        borderRadius: 2,
        overflow: 'hidden'
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 2,
          py: 1,
          borderBottom: '1px solid #333',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <Typography variant="subtitle2" sx={{ color: '#aaa' }}>
          Job Execution Logs
        </Typography>
        <Button
          size="small"
          variant="outlined"
          onClick={handleClearLogs}
          disabled={logs.length === 0}
          sx={{
            fontSize: '0.75rem',
            textTransform: 'none',
            borderColor: '#555',
            color: '#ccc',
            '&:hover': {
              borderColor: '#888',
              backgroundColor: 'rgba(255,255,255,0.08)'
            }
          }}
        >
          Clear
        </Button>
      </Box>

      {/* Scrollable Log Area */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          px: 2,
          py: 1,
          fontFamily: 'monospace',
          fontSize: '0.85rem'
        }}
      >
        {logs.map((log, idx) => {
          const style = LEVEL_STYLES[log.level] || DEFAULT_STYLE;

          return (
            <Box
              key={idx}
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 1.5,
                py: 0.4,
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.03)'
                }
              }}
            >
              {/* Level Badge */}
              <Box
                sx={{
                  minWidth: 60,
                  textAlign: 'center',
                  px: 1,
                  py: 0.3,
                  borderRadius: 1,
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: style.color,
                  backgroundColor: style.bg,
                  flexShrink: 0
                }}
              >
                {log.level}
              </Box>

              {/* Timestamp - fixed width + monospace */}
              <Typography
                variant="caption"
                sx={{
                  minWidth: 135,
                  color: '#9e9e9e',
                  fontFamily: 'monospace',
                  flexShrink: 0
                }}
              >
                {log.time}
              </Typography>

              {/* Message - takes remaining space */}
              <Typography
                variant="body2"
                component="div"
                sx={{
                  color: '#e0e0e0',
                  wordBreak: 'break-word',
                  whiteSpace: 'pre-wrap',
                  flex: 1,
                  lineHeight: 1.4
                }}
              >
                {formatMessage(log.message)}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}
