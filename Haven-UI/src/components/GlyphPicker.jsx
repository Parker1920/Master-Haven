import React, { useState, useEffect } from 'react';
import axios from 'axios';

/**
 * GlyphPicker Component
 *
 * Allows users to enter No Man's Sky portal glyphs via:
 * 1. Visual glyph picker (clicking on glyph images)
 * 2. Text input (pasting 12-digit hex code)
 *
 * Automatically decodes glyph to coordinates and validates input.
 */
const GlyphPicker = ({ value, onChange, onDecoded }) => {
  const [glyphCode, setGlyphCode] = useState(value || '');
  const [selectedGlyphs, setSelectedGlyphs] = useState([]);
  const [glyphImages, setGlyphImages] = useState({});
  const [inputMode, setInputMode] = useState('visual'); // 'visual' or 'text'
  const [validation, setValidation] = useState({ valid: null, message: null });
  const [decodedCoords, setDecodedCoords] = useState(null);
  const [isDecoding, setIsDecoding] = useState(false);

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

  // Update parent when glyph code changes
  useEffect(() => {
    if (onChange) {
      onChange(glyphCode);
    }
  }, [glyphCode, onChange]);

  // Decode glyph when complete (12 digits)
  useEffect(() => {
    if (glyphCode.length === 12) {
      decodeGlyph(glyphCode);
    } else {
      setDecodedCoords(null);
      setValidation({ valid: null, message: null });
    }
  }, [glyphCode]);

  const decodeGlyph = async (code) => {
    setIsDecoding(true);
    try {
      // Validate first
      const validateResponse = await axios.post('/api/validate_glyph', {
        glyph: code
      });

      if (!validateResponse.data.valid) {
        setValidation({
          valid: false,
          message: validateResponse.data.error
        });
        setDecodedCoords(null);
        setIsDecoding(false);
        return;
      }

      // Decode
      const decodeResponse = await axios.post('/api/decode_glyph', {
        glyph: code,
        apply_scale: false
      });

      setDecodedCoords(decodeResponse.data);

      // Use warnings from decode response (includes phantom star and core void warnings)
      // Also combine with any validation warnings
      const allWarnings = [];
      if (validateResponse.data.warning) {
        allWarnings.push(validateResponse.data.warning);
      }
      if (decodeResponse.data.warnings) {
        allWarnings.push(decodeResponse.data.warnings);
      }

      setValidation({
        valid: true,
        message: allWarnings.length > 0 ? allWarnings.join('; ') : null
      });

      // Notify parent of decoded coordinates
      if (onDecoded) {
        onDecoded(decodeResponse.data);
      }

    } catch (error) {
      setValidation({
        valid: false,
        message: error.response?.data?.detail || 'Failed to decode glyph'
      });
      setDecodedCoords(null);
    }
    setIsDecoding(false);
  };

  const handleGlyphClick = (hexDigit) => {
    if (selectedGlyphs.length < 12) {
      const newGlyphs = [...selectedGlyphs, hexDigit];
      setSelectedGlyphs(newGlyphs);
      setGlyphCode(newGlyphs.join(''));
    }
  };

  const handleBackspace = () => {
    if (selectedGlyphs.length > 0) {
      const newGlyphs = selectedGlyphs.slice(0, -1);
      setSelectedGlyphs(newGlyphs);
      setGlyphCode(newGlyphs.join(''));
    }
  };

  const handleClear = () => {
    setSelectedGlyphs([]);
    setGlyphCode('');
    setDecodedCoords(null);
    setValidation({ valid: null, message: null });
  };

  const handleTextInput = (e) => {
    const input = e.target.value.toUpperCase().replace(/[^0-9A-F]/g, '').slice(0, 12);
    setGlyphCode(input);
    setSelectedGlyphs(input.split(''));
  };

  const formatGlyphDisplay = (code) => {
    if (!code) return '';
    // Format as P-SSS-YY-ZZZ-XXX
    if (code.length === 12) {
      return `${code[0]}-${code.slice(1, 4)}-${code.slice(4, 6)}-${code.slice(6, 9)}-${code.slice(9, 12)}`;
    }
    return code;
  };

  const hexDigits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'];
  const glyphNames = {
    '0': 'Sunset', '1': 'Bird', '2': 'Face', '3': 'Diplo',
    '4': 'Eclipse', '5': 'Balloon', '6': 'Boat', '7': 'Bug',
    '8': 'Dragonfly', '9': 'Galaxy', 'A': 'Voxel', 'B': 'Fish',
    'C': 'Tent', 'D': 'Rocket', 'E': 'Tree', 'F': 'Atlas'
  };

  return (
    <div className="glyph-picker bg-gray-900 p-4 rounded-lg border border-purple-500">
      {/* Mode Toggle */}
      <div className="flex gap-2 mb-4">
        <button type="button"
          onClick={() => setInputMode('visual')}
          className={`px-4 py-2 rounded ${
            inputMode === 'visual'
              ? 'bg-purple-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          Visual Picker
        </button>
        <button type="button"
          onClick={() => setInputMode('text')}
          className={`px-4 py-2 rounded ${
            inputMode === 'text'
              ? 'bg-purple-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          Text Input
        </button>
      </div>

      {/* Glyph Code Display */}
      <div className="mb-4">
            <label className="block text-sm font-medium text-purple-300 mb-2">
              Portal Glyph Code (12 digits)
            </label>
            <div className="bg-gray-800 p-3 rounded border border-gray-700 font-mono text-xl text-center">
              {glyphCode.length > 0 ? (
                <span className={validation.valid === false ? 'text-red-400' : 'text-green-400'}>
                  {formatGlyphDisplay(glyphCode)}
                </span>
              ) : (
                <span className="text-gray-500">Enter or select glyphs...</span>
              )}
            </div>
            <div className="text-xs text-gray-400 mt-1 text-center">
              {glyphCode.length}/12 digits
            </div>
          </div>

          {/* Visual Glyph Picker Mode */}
          {inputMode === 'visual' && (
            <div>
              <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 sm:gap-2 mb-4">
                {hexDigits.map(digit => (
                  <button type="button"
                    key={digit}
                    onClick={() => handleGlyphClick(digit)}
                    disabled={selectedGlyphs.length >= 12}
                    className="relative aspect-square border-2 border-purple-500 rounded hover:border-purple-300 hover:bg-purple-900/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden bg-gray-800"
                    title={`${glyphNames[digit]} (${digit})`}
                  >
                    {glyphImages[digit] ? (
                      <img
                        src={`/haven-ui-photos/${glyphImages[digit]}`}
                        alt={glyphNames[digit]}
                        className="w-full h-full object-contain p-1 sm:p-1 pb-4 sm:pb-4"
                      />
                    ) : (
                      <span className="absolute inset-0 flex items-center justify-center text-purple-300 font-mono text-2xl sm:text-lg pb-4">
                        {digit}
                      </span>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 bg-black/80 text-[10px] sm:text-xs text-purple-300 py-0.5 text-center font-mono">
                      {digit}
                    </div>
                  </button>
                ))}
              </div>

              <div className="flex gap-2">
                <button type="button"
                  onClick={handleBackspace}
                  disabled={selectedGlyphs.length === 0}
                  className="flex-1 px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Backspace
                </button>
                <button type="button"
                  onClick={handleClear}
                  disabled={selectedGlyphs.length === 0}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Clear All
                </button>
              </div>
            </div>
          )}

          {/* Text Input Mode */}
          {inputMode === 'text' && (
            <div>
              <input
                type="text"
                value={glyphCode}
                onChange={handleTextInput}
                placeholder="Paste 12-digit hex code (e.g., 10A4F3E7B2C1)"
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono uppercase focus:border-purple-500 focus:outline-none"
                maxLength={12}
              />
              <button type="button"
                onClick={handleClear}
                className="w-full mt-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded"
              >
                Clear
              </button>
            </div>
          )}

      {/* Validation Message */}
      {validation.message && (
        <div className={`mt-4 p-3 rounded ${
          validation.valid === false
            ? 'bg-red-900/50 border border-red-500 text-red-300'
            : 'bg-yellow-900/50 border border-yellow-500 text-yellow-300'
        }`}>
          <div className="font-semibold mb-1">
            {validation.valid === false ? '❌ Invalid Glyph' : '⚠️ Warning'}
          </div>
          <div className="text-sm">{validation.message}</div>
        </div>
      )}

      {/* Decoded Coordinates Display */}
      {isDecoding && (
        <div className="mt-4 p-3 bg-gray-800 rounded border border-purple-500 text-center text-purple-300">
          Decoding glyph...
        </div>
      )}

      {decodedCoords && !isDecoding && (
        <div className={`mt-4 p-3 rounded border ${
          decodedCoords.is_phantom || decodedCoords.is_in_core
            ? 'bg-orange-900/30 border-orange-500'
            : 'bg-green-900/30 border-green-500'
        }`}>
          <div className="font-semibold mb-2 flex items-center gap-2">
            {decodedCoords.is_phantom || decodedCoords.is_in_core ? (
              <>
                <span className="text-orange-300">⚠ Decoded Coordinates</span>
                {decodedCoords.is_phantom && (
                  <span className="text-xs bg-purple-600 text-white px-2 py-0.5 rounded" title="Phantom Star - Not normally accessible on Galactic Map">
                    👻 PHANTOM
                  </span>
                )}
                {decodedCoords.is_in_core && (
                  <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded" title="Located in Galactic Core Void">
                    🌀 CORE
                  </span>
                )}
              </>
            ) : (
              <span className="text-green-300">✓ Decoded Coordinates</span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm text-gray-300">
            <div>
              <span className="text-gray-400">X:</span> <span className={`font-mono ${decodedCoords.is_phantom || decodedCoords.is_in_core ? 'text-orange-300' : 'text-green-300'}`}>{decodedCoords.x}</span>
            </div>
            <div>
              <span className="text-gray-400">Y:</span> <span className={`font-mono ${decodedCoords.is_phantom || decodedCoords.is_in_core ? 'text-orange-300' : 'text-green-300'}`}>{decodedCoords.y}</span>
            </div>
            <div>
              <span className="text-gray-400">Z:</span> <span className={`font-mono ${decodedCoords.is_phantom || decodedCoords.is_in_core ? 'text-orange-300' : 'text-green-300'}`}>{decodedCoords.z}</span>
            </div>
            <div>
              <span className="text-gray-400">Planet:</span> <span className={`font-mono ${decodedCoords.is_phantom || decodedCoords.is_in_core ? 'text-orange-300' : 'text-green-300'}`}>{decodedCoords.planet}</span>
            </div>
            <div className="col-span-2">
              <span className="text-gray-400">Region:</span> <span className={`font-mono ${decodedCoords.is_phantom || decodedCoords.is_in_core ? 'text-orange-300' : 'text-green-300'}`}>
                [{decodedCoords.region_x}, {decodedCoords.region_y}, {decodedCoords.region_z}]
              </span>
            </div>
            <div className="col-span-2">
              <span className="text-gray-400">Solar System Index:</span> <span className={`font-mono ${decodedCoords.is_phantom || decodedCoords.is_in_core ? 'text-orange-300' : 'text-green-300'}`}>{decodedCoords.solar_system} (0x{decodedCoords.solar_system?.toString(16).toUpperCase().padStart(3, '0')})</span>
            </div>
          </div>
          {/* Classification info */}
          {(decodedCoords.is_phantom || decodedCoords.is_in_core) && (
            <div className="mt-3 pt-3 border-t border-orange-700 text-xs text-orange-200">
              <strong>Classification:</strong> {decodedCoords.classification?.replace('_', ' ').toUpperCase()}
              <div className="mt-1 text-orange-300/80">
                This system will be recorded for tracking purposes but may not appear on standard maps.
              </div>
            </div>
          )}
          {/* Star position is calculated for unique 3D map placement */}
          {decodedCoords.star_x !== undefined && (
            <div className={`mt-3 pt-3 border-t ${decodedCoords.is_phantom || decodedCoords.is_in_core ? 'border-orange-700' : 'border-green-700'}`}>
              <div className="text-xs text-gray-400 mb-1">3D Map Position (calculated from region + SSS):</div>
              <div className="font-mono text-xs text-cyan-300">
                ({decodedCoords.star_x?.toFixed(2)}, {decodedCoords.star_y?.toFixed(2)}, {decodedCoords.star_z?.toFixed(2)})
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default GlyphPicker;
