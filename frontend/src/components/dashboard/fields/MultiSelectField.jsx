import {
  Checkbox,
  FormControl,
  InputLabel,
  ListItemText,
  MenuItem,
  OutlinedInput,
  Select,
  Divider,
  Box,
  Typography
} from '@mui/material';

export function MultiSelectField({ formData, fieldPathId, schema, onChange }) {
  const options = schema.enum || schema.default || [];
  const selectedValues = Array.isArray(formData) ? formData : [];
  const allSelected = options.length > 0 && selectedValues.length === options.length;
  const someSelected = selectedValues.length > 0 && selectedValues.length < options.length;

  const handleChange = (event) => {
    const value = event.target.value;
    let newValue;
    if (typeof value === 'string') {
      newValue = value.split(',');
    } else {
      newValue = value;
    }
    onChange(newValue, fieldPathId?.path);
  };

  const handleSelectAll = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (allSelected) {
      onChange([], fieldPathId?.path);
    } else {
      onChange([...options], fieldPathId?.path);
    }
  };

  return (
    <FormControl fullWidth size="small">
      <InputLabel id={`multi-select-label-${fieldPathId?.path || 'default'}`}>
        {schema.title}
      </InputLabel>
      <Select
        labelId={`multi-select-label-${fieldPathId?.path || 'default'}`}
        multiple
        value={selectedValues}
        onChange={handleChange}
        input={<OutlinedInput label={schema.title} />}
        renderValue={(selected) => (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {selected.length <= 3 ? (
              selected.join(', ')
            ) : (
              <Typography variant="body2">
                {selected.length} items selected
              </Typography>
            )}
          </Box>
        )}
        MenuProps={{
          PaperProps: {
            sx: {
              maxHeight: 300,
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              mt: 0.5,
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            }
          },
          anchorOrigin: {
            vertical: 'bottom',
            horizontal: 'left',
          },
          transformOrigin: {
            vertical: 'top',
            horizontal: 'left',
          },
        }}
      >
        {/* Select All Option */}
        <MenuItem 
          onClick={handleSelectAll}
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
          sx={{ 
            fontWeight: 600,
            py: 1,
            position: 'sticky',
            top: 0,
            zIndex: 1,
            bgcolor: allSelected ? 'action.selected' : 'background.paper',
            '&:hover': { 
              bgcolor: allSelected ? 'action.selected' : 'action.hover' 
            },
          }}
        >
          <Checkbox 
            checked={allSelected} 
            indeterminate={someSelected}
            sx={{ mr: 1.5 }}
          />
          <ListItemText 
            primary="Select All" 
            primaryTypographyProps={{ fontWeight: 600 }}
          />
        </MenuItem>
        
        <Divider sx={{ my: 0.5 }} />
        
        {/* Individual Options */}
        {options.map((token) => (
          <MenuItem 
            key={token} 
            value={token}
            sx={{
              py: 0.75,
              '&:hover': { bgcolor: 'action.hover' },
              '&.Mui-selected': { bgcolor: 'action.selected' },
              '&.Mui-selected:hover': { bgcolor: 'action.selected' },
            }}
          >
            <Checkbox 
              checked={selectedValues.includes(token)} 
              sx={{ mr: 1.5 }}
            />
            <ListItemText 
              primary={token}
              primaryTypographyProps={{ 
                fontSize: '0.875rem',
                fontWeight: selectedValues.includes(token) ? 500 : 400,
              }}
            />
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

