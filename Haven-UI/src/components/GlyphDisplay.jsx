import React, { useState, useEffect } from 'react';
import axios from 'axios';

/**
 * GlyphDisplay Component
 *
 * Displays a 12-digit glyph code as visual NMS portal glyphs.
 * Read-only display version of GlyphPicker.
 */
const GlyphDisplay = ({ glyphCode, size = 'medium' }) => {
  const [glyphImages, setGlyphImages] = useState({});

  // Size presets
  const sizeClasses = {
    small: 'w-5 h-5',
    medium: 'w-7 h-7',
    large: 'w-10 h-10',
  };

  const glyphSize = sizeClasses[size] || sizeClasses.medium;

  // Fetch glyph images mapping on mount
  useEffect(() => {
    axios.get('/api/glyph_images')
      .then(response => {
        setGlyphImages(response.data);
      })
      .catch(error => {
        console.error('Failed to load glyph images:', error);
      });
  }, []);

  // Glyph names for tooltips
  const glyphNames = {
    '0': 'Sunset', '1': 'Bird', '2': 'Face', '3': 'Diplo',
    '4': 'Eclipse', '5': 'Balloon', '6': 'Boat', '7': 'Bug',
    '8': 'Dragonfly', '9': 'Galaxy', 'A': 'Voxel', 'B': 'Fish',
    'C': 'Tent', 'D': 'Rocket', 'E': 'Tree', 'F': 'Atlas'
  };

  if (!glyphCode || glyphCode.length !== 12) {
    return (
      <span className="font-mono text-gray-400">
        {glyphCode || 'No glyph code'}
      </span>
    );
  }

  const glyphs = glyphCode.toUpperCase().split('');

  return (
    <div className="flex items-center gap-0.5 flex-wrap">
      {glyphs.map((digit, index) => (
        <div
          key={index}
          className={`${glyphSize} flex items-center justify-center bg-gray-800 rounded border border-purple-600/50 overflow-hidden`}
          title={`${glyphNames[digit]} (${digit})`}
        >
          {glyphImages[digit] ? (
            <img
              src={`/haven-ui-photos/${glyphImages[digit]}`}
              alt={glyphNames[digit]}
              className="w-full h-full object-contain p-0.5"
            />
          ) : (
            <span className="text-purple-300 font-mono text-xs">
              {digit}
            </span>
          )}
        </div>
      ))}
    </div>
  );
};

export default GlyphDisplay;
