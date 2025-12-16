import { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Typography,
  Paper
} from '@mui/material';

import { API_BASE_URL } from './api';

export default function ScheduleManager() {
  const [jobs, setJobs] = useState([]);
  const [logs, setLogs] = useState([]);
  const [view, setView] = useState('jobs');

  // Load jobs
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/schedule`);

        if (!res.ok) throw new Error('Failed to load jobs');
        const data = await res.json();
        setJobs(data.jobs || []);
      } catch (ex) {
        console.error(ex);
      } finally {
        setTimeout(fetchJobs, 3000);
      }
    };

    fetchJobs();
  }, []);

  const fetchLogs = () => {
    fetch(`${API_BASE_URL}/schedule/logs`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load logs');
        return res.json();
      })
      .then((data) => setLogs(data.events || []))
      .catch(console.error);
  };

  const toggleJob = async (jobId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/schedule/toggle/${jobId}`, {
        method: 'POST'
      });

      if (!res.ok) {
        throw new Error('Failed to toggle job');
      }

      const data = await res.json();
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId ? { ...j, paused: data.state === 'paused' } : j
        )
      );
    } catch (err) {
      console.error(err);
      alert('Failed to toggle job');
    }
  };

  return (
    <Box sx={{ p: 4 }}>
      <Card>
        <CardContent>
          {/* Header */}
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="center"
          >
            <Tabs
              value={view}
              onChange={(_, v) => {
                setView(v);
                if (v === 'logs') fetchLogs();
              }}
            >
              <Tab label="Jobs" value="jobs" />
              <Tab label="Logs" value="logs" />
            </Tabs>
          </Box>

          {/* JOBS */}
          {view === 'jobs' && (
            <TableContainer component={Paper} sx={{ mt: 3 }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Job Name</TableCell>
                    <TableCell>Last Execution</TableCell>
                    <TableCell>Next Execution</TableCell>
                    <TableCell align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell>{job.name}</TableCell>
                      <TableCell>{job.last_execution || '—'}</TableCell>
                      <TableCell>
                        {job.next_run_time || 'Not scheduled'}
                      </TableCell>
                      <TableCell align="center">
                        <Button
                          variant="contained"
                          color={job.paused ? 'success' : 'error'}
                          onClick={() => toggleJob(job.id)}
                        >
                          {job.paused ? 'Activate' : 'Deactivate'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {/* LOGS */}
          {view === 'logs' && (
            <TableContainer component={Paper} sx={{ mt: 3 }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Job</TableCell>
                    <TableCell>Event</TableCell>
                    <TableCell>Timestamp</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {logs.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell>{e.job_name}</TableCell>
                      <TableCell>
                        <Typography fontWeight={500}>{e.event_type}</Typography>
                        {e.info && (
                          <Typography variant="body2" color="text.secondary">
                            {e.info}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>{e.timestamp}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
