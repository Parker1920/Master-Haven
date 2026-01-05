import React from 'react'
import Select from 'react-select'

// Dark theme styles for react-select to match the app's aesthetic
const darkThemeStyles = {
  container: (base) => ({
    ...base,
    minWidth: '220px'
  }),
  control: (base, state) => ({
    ...base,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderColor: state.isFocused ? '#3b82f6' : 'rgba(255, 255, 255, 0.2)',
    borderRadius: '0.25rem',
    minHeight: '34px',
    boxShadow: state.isFocused ? '0 0 0 1px #3b82f6' : 'none',
    cursor: 'pointer',
    '&:hover': {
      borderColor: '#3b82f6'
    }
  }),
  valueContainer: (base) => ({
    ...base,
    padding: '0 8px'
  }),
  input: (base) => ({
    ...base,
    color: 'white',
    margin: 0,
    padding: 0
  }),
  singleValue: (base) => ({
    ...base,
    color: 'white',
    overflow: 'visible',
    textOverflow: 'clip'
  }),
  placeholder: (base) => ({
    ...base,
    color: 'rgba(255, 255, 255, 0.5)'
  }),
  menu: (base) => ({
    ...base,
    backgroundColor: '#1f2937',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    borderRadius: '0.25rem',
    zIndex: 9999,
    minWidth: '280px',
    width: 'max-content',
    maxWidth: '400px'
  }),
  menuList: (base) => ({
    ...base,
    maxHeight: '250px',
    padding: 0
  }),
  option: (base, state) => ({
    ...base,
    backgroundColor: state.isSelected
      ? '#3b82f6'
      : state.isFocused
        ? 'rgba(59, 130, 246, 0.3)'
        : 'transparent',
    color: 'white',
    cursor: 'pointer',
    padding: '10px 14px',
    whiteSpace: 'nowrap',
    '&:active': {
      backgroundColor: '#3b82f6'
    }
  }),
  noOptionsMessage: (base) => ({
    ...base,
    color: 'rgba(255, 255, 255, 0.5)'
  }),
  dropdownIndicator: (base, state) => ({
    ...base,
    color: 'rgba(255, 255, 255, 0.5)',
    padding: '4px',
    transform: state.selectProps.menuIsOpen ? 'rotate(180deg)' : null,
    transition: 'transform 0.2s ease',
    '&:hover': {
      color: 'white'
    }
  }),
  clearIndicator: (base) => ({
    ...base,
    color: 'rgba(255, 255, 255, 0.5)',
    padding: '4px',
    '&:hover': {
      color: 'white'
    }
  }),
  indicatorSeparator: (base) => ({
    ...base,
    backgroundColor: 'rgba(255, 255, 255, 0.2)'
  }),
  multiValue: (base) => ({
    ...base,
    backgroundColor: 'rgba(59, 130, 246, 0.3)',
    borderRadius: '4px'
  }),
  multiValueLabel: (base) => ({
    ...base,
    color: 'white',
    padding: '2px 6px'
  }),
  multiValueRemove: (base) => ({
    ...base,
    color: 'rgba(255, 255, 255, 0.7)',
    cursor: 'pointer',
    '&:hover': {
      backgroundColor: 'rgba(239, 68, 68, 0.5)',
      color: 'white'
    }
  })
}

export default function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = '-- Select --',
  isClearable = true,
  isMulti = false,
  className = ''
}) {
  // Handle value conversion based on single vs multi select
  let selectedOption
  if (isMulti) {
    // For multi-select: convert comma-separated string to array of option objects
    if (value && typeof value === 'string') {
      const values = value.split(',').map(v => v.trim()).filter(v => v)
      selectedOption = values.map(v => options.find(opt => opt.value === v)).filter(Boolean)
    } else {
      selectedOption = []
    }
  } else {
    // For single select: find the matching option
    selectedOption = value ? options.find(opt => opt.value === value) : null
  }

  const handleChange = (selected) => {
    if (isMulti) {
      // For multi-select: convert array of options back to comma-separated string
      const values = selected ? selected.map(opt => opt.value).join(', ') : ''
      onChange(values)
    } else {
      // For single select: just return the value
      onChange(selected ? selected.value : '')
    }
  }

  return (
    <Select
      options={options}
      value={selectedOption}
      onChange={handleChange}
      placeholder={placeholder}
      isClearable={isClearable}
      isSearchable={true}
      isMulti={isMulti}
      styles={darkThemeStyles}
      className={className}
      classNamePrefix="searchable-select"
      noOptionsMessage={() => 'No matches found'}
      menuPlacement="auto"
      closeMenuOnSelect={!isMulti}
    />
  )
}
