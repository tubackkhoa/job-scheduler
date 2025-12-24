import {
  Box,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Typography,
  IconButton,
  Tooltip,
  Avatar,
} from "@mui/material";
import { Refresh, Person } from "@mui/icons-material";

export function ContextPanel({
  users,
  plugins,
  userId,
  pluginId,
  onUserChange,
  onPluginChange,
  onReloadPlugin,
  isLoading,
}) {
  return (
    <Card
      sx={{
        bgcolor: 'background.paper',
        backgroundImage: 'linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(236, 72, 153, 0.05) 100%)',
      }}
    >
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 3 }}>
          <Avatar
            sx={{
              bgcolor: 'primary.main',
              width: 44,
              height: 44,
            }}
          >
            <Person />
          </Avatar>
          <Box>
            <Typography variant="h6" fontWeight={600}>
              Context
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Choose user and plugin
            </Typography>
          </Box>
        </Stack>

        <Stack spacing={2.5}>
          <FormControl fullWidth>
            <InputLabel>User</InputLabel>
            <Select
              value={userId}
              onChange={(e) => onUserChange(Number(e.target.value))}
              label="User"
            >
              {users.map((user) => (
                <MenuItem key={user.id} value={user.id}>
                  {user.fullName}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Stack direction="row" spacing={1} alignItems="flex-start">
            <FormControl fullWidth>
              <InputLabel>Plugin</InputLabel>
              <Select
                value={pluginId}
                onChange={(e) => onPluginChange(Number(e.target.value))}
                label="Plugin"
              >
                <MenuItem value={0}>
                  <em>Select a plugin...</em>
                </MenuItem>
                {plugins.map((plugin) => (
                  <MenuItem key={plugin.id} value={plugin.id}>
                    <Stack>
                      <Typography variant="body2">
                        {plugin.package}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        interval {plugin.interval}s
                      </Typography>
                    </Stack>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {pluginId > 0 && (
              <Tooltip title="Reload plugin (development)">
                <IconButton
                  onClick={onReloadPlugin}
                  disabled={isLoading}
                  color="warning"
                  sx={{
                    mt: 0.5,
                    bgcolor: 'rgba(245, 158, 11, 0.1)',
                    '&:hover': { bgcolor: 'rgba(245, 158, 11, 0.2)' },
                  }}
                >
                  <Refresh
                    sx={{
                      animation: isLoading ? 'spin 1s linear infinite' : 'none',
                      '@keyframes spin': {
                        '0%': { transform: 'rotate(0deg)' },
                        '100%': { transform: 'rotate(360deg)' },
                      },
                    }}
                  />
                </IconButton>
              </Tooltip>
            )}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
}

