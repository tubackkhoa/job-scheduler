import React, { useEffect, useState, useRef } from 'react';
import { Box, Typography, Paper } from '@mui/material';

// Map log levels to MUI color palette or CSS colors
const levelColors = {
  ERROR: '#f44336', // Red
  WARN: '#ff9800', // Orange
  INFO: '#2196f3', // Blue
  DEBUG: '#9e9e9e', // Grey
  TRACE: '#757575' // Dark Grey
};

export default function LogViewer({ url, jobInstanceId }) {
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
      setLogs((prevLogs) => [...prevLogs, data]);
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

  return (
    <Paper
      elevation={3}
      sx={{
        mt: 2,
        padding: 2,
        fontFamily: 'monospace',
        backgroundColor: '#000',
        height: 400,
        overflowY: 'auto',
        border: '1px solid #444'
      }}
    >
      {logs.length === 0 ? (
        <Typography></Typography>
      ) : (
        logs.map((log, idx) => {
          const color = levelColors[log.level] || '#d4d4d4';
          return (
            <Box key={idx} sx={{ color, mb: 0.5 }}>
              <Typography
                variant="body2"
                component="span"
                sx={{ fontWeight: 'bold' }}
              >
                {log.level}:
              </Typography>{' '}
              <Typography variant="body2" component="span">
                {log.message}
              </Typography>
            </Box>
          );
        })
      )}
    </Paper>
  );
}
