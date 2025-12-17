import { useEffect, useState, useRef } from 'react';
import { Box, Typography, Paper, Button } from '@mui/material';

// Map log levels to MUI color palette or CSS colors
const levelColors = {
  ERROR: {
    color: '#ff6b6b',
    bg: 'rgba(255, 107, 107, 0.15)'
  },
  WARN: {
    color: '#ffb74d',
    bg: 'rgba(255, 183, 77, 0.15)'
  },
  INFO: {
    color: '#64b5f6',
    bg: 'rgba(100, 181, 246, 0.15)'
  },
  DEBUG: {
    color: '#b0bec5',
    bg: 'rgba(176, 190, 197, 0.15)'
  },
  TRACE: {
    color: '#9e9e9e',
    bg: 'rgba(158, 158, 158, 0.12)'
  }
};

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
        padding: 2,
        fontFamily: 'monospace',
        backgroundColor: '#000',
        height: 400,
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #444'
      }}
    >
      {/* Header / Actions */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          mb: 1
        }}
      >
        <Button
          size="small"
          variant="outlined"
          onClick={() => setLogs([])}
          disabled={logs.length === 0}
          sx={{
            fontSize: '0.75rem',
            textTransform: 'none',
            borderColor: '#555',
            color: '#ccc',
            '&:hover': {
              borderColor: '#888',
              backgroundColor: 'rgba(255,255,255,0.05)'
            }
          }}
        >
          Clear
        </Button>
      </Box>

      {/* Log list */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto'
        }}
      >
        {logs.map((log, idx) => {
          const levelStyle = levelColors[log.level] || {
            color: '#d4d4d4',
            bg: 'transparent'
          };

          return (
            <Box
              key={idx}
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 1,
                mb: 0.75
              }}
            >
              {/* Level badge */}
              <Box
                sx={{
                  minWidth: 60,
                  textAlign: 'center',
                  px: 1,
                  py: 0.25,
                  borderRadius: 1,
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: levelStyle.color,
                  backgroundColor: levelStyle.bg
                }}
              >
                {log.level}
              </Box>

              {/* Message */}
              <Typography
                variant="body2"
                sx={{
                  color: '#e0e0e0',
                  wordBreak: 'break-word'
                }}
              >
                {log.message}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}
