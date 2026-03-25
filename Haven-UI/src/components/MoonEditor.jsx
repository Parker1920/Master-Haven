import React from 'react'
import CelestialBodyEditor from './CelestialBodyEditor'

/**
 * Moon editor - thin wrapper around CelestialBodyEditor with type="moon".
 * Props: moon, index, onChange, onRemove, onSave.
 */
export default function MoonEditor({ moon, index, onChange, onRemove, onSave }) {
  return (
    <CelestialBodyEditor
      type="moon"
      body={moon}
      index={index}
      onChange={onChange}
      onRemove={onRemove}
      onSave={onSave}
    />
  )
}
