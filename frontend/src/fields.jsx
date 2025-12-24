import React from 'react';

import {
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Checkbox,
  Grid,
  Typography,
  Divider,
  TextField,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  ListItemText,
  OutlinedInput
} from '@mui/material';

export function MLThresholdsTableField(props) {
  const { schema, formData = {}, onChange, fieldPathId } = props;

  // Extract model rows from schema
  const modelSchemas = schema.properties ?? {};

  // Extract column names from ModelMLThresholds schema
  const firstModelKey = Object.keys(modelSchemas)[0];
  const thresholdSchema = modelSchemas[firstModelKey]?.properties ?? {};

  const thresholdKeys = Object.keys(thresholdSchema);

  const updateCell = (modelKey, thresholdKey, patch) => {
    onChange(
      {
        ...formData,
        [modelKey]: {
          ...formData[modelKey],
          [thresholdKey]: {
            ...formData[modelKey][thresholdKey],
            ...patch
          }
        }
      },
      fieldPathId.path
    );
  };

  return (
    <Grid>
      <Typography variant="h5">{schema.title}</Typography>
      <Divider />
      <Typography
        variant="subtitle2"
        sx={{ my: 1 }}
      >{`Configure filtering rules for each model separately (Rule 1: |μ| ≥ threshold, Rule 2: min < |μ/σ| < max, Rule 3: σ < threshold)`}</Typography>
      <Table size="small">
        <TableHead>
          <TableRow
            sx={(theme) => ({
              backgroundColor: theme.palette.background.default
            })}
          >
            <TableCell>Model</TableCell>
            <TableCell>Model Key</TableCell>

            {thresholdKeys.map((key) => (
              <React.Fragment key={key}>
                <TableCell>{thresholdSchema[key].title}</TableCell>
                <TableCell>Disable</TableCell>
              </React.Fragment>
            ))}
          </TableRow>
        </TableHead>

        <TableBody>
          {Object.entries(formData).map(([modelKey, row]) => (
            <TableRow key={modelKey}>
              <TableCell>{modelSchemas[modelKey]?.title}</TableCell>
              <TableCell>{modelKey}</TableCell>

              {thresholdKeys.map((thKey) => {
                const cell = row[thKey];
                return (
                  <React.Fragment key={`${modelKey}-${thKey}`}>
                    <TableCell>
                      <TextField
                        variant="standard"
                        sx={{
                          minWidth: '6ch' // 👈 fits ~5 digits comfortably
                        }}
                        slotProps={{
                          input: {
                            step: 'any',
                            disableUnderline: true
                          }
                        }}
                        type="number"
                        size="small"
                        value={cell.value}
                        disabled={cell.disabled}
                        onChange={(e) =>
                          updateCell(modelKey, thKey, {
                            value: Number(e.target.value)
                          })
                        }
                      />
                    </TableCell>

                    <TableCell>
                      <Checkbox
                        checked={cell.disabled}
                        onChange={(e) =>
                          updateCell(modelKey, thKey, {
                            disabled: e.target.checked
                          })
                        }
                      />
                    </TableCell>
                  </React.Fragment>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Grid>
  );
}

// Props:
// - options: string[] (the enum options from JSON schema)
// - defaultValue: string[] (default selected tokens from JSON schema)
// - label: string
// - onChange: (newValue: string[]) => void
export function MultiSelectField(props) {
  const { formData, fieldPathId, schema, onChange } = props;
  console.log('MultiSelectField props:', props);
  const handleChange = (event) => {
    const value = event.target.value;
    if (onChange) onChange(value, fieldPathId.path);
  };
  const defaultValue = Array.isArray(formData) ? formData : [];
  return (
    <FormControl fullWidth>
      <InputLabel>{schema.title}</InputLabel>
      <Select
        multiple
        value={defaultValue}
        onChange={handleChange}
        input={<OutlinedInput label={schema.title} />}
        renderValue={(selected) => selected.join(', ')}
      >
        {Array.isArray(schema.default) &&
          schema.default.map((token) => (
            <MenuItem key={token} value={token}>
              <Checkbox checked={formData?.indexOf(token) > -1} />
              <ListItemText primary={token} />
            </MenuItem>
          ))}
      </Select>
    </FormControl>
  );
}
