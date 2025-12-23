# Haven UI - Google Forms Submission System

This guide explains how to set up a Google Forms-based submission system that allows users to submit star system discoveries without using the Haven UI directly. All submissions are consolidated and automatically sent to Haven UI's pending approval queue.

## Overview

The system uses **4 Google Forms** that all feed into a **single Google Sheet**:

| Form | Purpose | Required |
|------|---------|----------|
| Form 1: System | Core system data + Space Station | Yes (once per system) |
| Form 2: Planet | Planet details | Yes (at least once) |
| Form 3: Moon | Moon details | Optional |
| Form 4: Finalize | Triggers submission to Haven UI | Yes (once when done) |

All data is linked together using the **System Glyph Code** (positions 2-12 of the portal address).

---

## Understanding the Glyph Structure

Portal glyphs are 12 hexadecimal characters in the format: `P SSS YY ZZZ XXX`

```
Position:  1   2-4   5-6   7-9   10-12
           P   SSS   YY    ZZZ   XXX
           |    |     |     |     |
           |    |     |     |     +-- X coordinate (East/West)
           |    |     |     +-------- Z coordinate (North/South)
           |    |     +-------------- Y coordinate (Up/Down)
           |    +-------------------- Solar System Index
           +------------------------- Planet Index (changes per planet)
```

**Important**:
- Positions 2-12 (11 characters) identify the **SYSTEM** and stay the same for all planets
- Position 1 identifies which **PLANET** within that system
- When users submit planets, they enter the planet index separately

---

## Glyph Reference

The 16 portal glyphs and their hex values:

| Hex | Name | Description | Image URL (for Google Forms) |
|-----|------|-------------|------------------------------|
| 0 | Sunset | Waves/sunset over water | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/5/5d/PORTALSYMBOL.0.png/revision/latest?cb=20170818050005` |
| 1 | Bird | Flying bird | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/5/56/PORTALSYMBOL.1.png/revision/latest?cb=20170818050037` |
| 2 | Face | Face/mask | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/2/21/PORTALSYMBOL.2.png/revision/latest?cb=20170818050110` |
| 3 | Diplo | Dinosaur | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/d/d8/PORTALSYMBOL.3.png/revision/latest?cb=20170818050138` |
| 4 | Eclipse | Crescent moon | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/e/e0/PORTALSYMBOL.4.png/revision/latest?cb=20170818050205` |
| 5 | Balloon | Teardrop/balloon | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/d/de/PORTALSYMBOL.5.png/revision/latest?cb=20170818050230` |
| 6 | Boat | Platform/boat | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/d/d1/PORTALSYMBOL.6.png/revision/latest?cb=20170818050304` |
| 7 | Bug | Insect | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/6/6e/PORTALSYMBOL.7.png/revision/latest?cb=20170818050333` |
| 8 | Dragonfly | Dragonfly | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/0/06/PORTALSYMBOL.8.png/revision/latest?cb=20170818050400` |
| 9 | Galaxy | Spiral galaxy | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/f/f0/PORTALSYMBOL.9.png/revision/latest?cb=20170818050428` |
| A | Voxel | Hexagon | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/a/ae/PORTALSYMBOL.A.png/revision/latest?cb=20170818050455` |
| B | Fish | Fish | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/b/be/PORTALSYMBOL.B.png/revision/latest?cb=20170818050521` |
| C | Tent | Tent/tipi | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/9/95/PORTALSYMBOL.C.png/revision/latest?cb=20170818050551` |
| D | Rocket | Rocket ship | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/6/66/PORTALSYMBOL.D.png/revision/latest?cb=20170818050619` |
| E | Tree | Tree | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/b/b0/PORTALSYMBOL.E.png/revision/latest?cb=20170818050649` |
| F | Atlas | Triangle/Atlas | `https://static.wikia.nocookie.net/nomanssky_gamepedia/images/5/51/PORTALSYMBOL.F.png/revision/latest?cb=20170818050717` |

> **Source**: Official images from the [No Man's Sky Wiki](https://nomanssky.fandom.com/wiki/Glyph)

### Quick Copy - Glyph Image URLs

Copy these URLs directly when adding images to Google Forms:

```
0: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/5/5d/PORTALSYMBOL.0.png/revision/latest?cb=20170818050005
1: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/5/56/PORTALSYMBOL.1.png/revision/latest?cb=20170818050037
2: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/2/21/PORTALSYMBOL.2.png/revision/latest?cb=20170818050110
3: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/d/d8/PORTALSYMBOL.3.png/revision/latest?cb=20170818050138
4: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/e/e0/PORTALSYMBOL.4.png/revision/latest?cb=20170818050205
5: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/d/de/PORTALSYMBOL.5.png/revision/latest?cb=20170818050230
6: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/d/d1/PORTALSYMBOL.6.png/revision/latest?cb=20170818050304
7: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/6/6e/PORTALSYMBOL.7.png/revision/latest?cb=20170818050333
8: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/0/06/PORTALSYMBOL.8.png/revision/latest?cb=20170818050400
9: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/f/f0/PORTALSYMBOL.9.png/revision/latest?cb=20170818050428
A: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/a/ae/PORTALSYMBOL.A.png/revision/latest?cb=20170818050455
B: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/b/be/PORTALSYMBOL.B.png/revision/latest?cb=20170818050521
C: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/9/95/PORTALSYMBOL.C.png/revision/latest?cb=20170818050551
D: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/6/66/PORTALSYMBOL.D.png/revision/latest?cb=20170818050619
E: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/b/b0/PORTALSYMBOL.E.png/revision/latest?cb=20170818050649
F: https://static.wikia.nocookie.net/nomanssky_gamepedia/images/5/51/PORTALSYMBOL.F.png/revision/latest?cb=20170818050717
```

---

## Step 1: Create the Google Sheet

1. Go to [Google Sheets](https://sheets.google.com) and create a new spreadsheet
2. Name it: `Haven UI Submissions`
3. Create **5 tabs** (sheets) at the bottom:
   - `Systems`
   - `Planets`
   - `Moons`
   - `Submissions`
   - `Config`

### Config Tab Setup

In the `Config` tab, add these settings:

| A | B |
|---|---|
| HAVEN_UI_URL | https://your-haven-ui-server.com |
| API_ENDPOINT | /api/submit_system |

---

## Step 2: Create Form 1 - System + Space Station

### Form Settings
- Title: `Haven UI - System Submission`
- Description: `Submit a new star system discovery. After this form, submit Form 2 for each planet.`

### Questions

#### Section 1: System Glyphs (Positions 2-12)

For each glyph position, create a **Multiple Choice** question with images.

##### How to Add Images to Multiple Choice Options in Google Forms:

1. Create a new **Multiple Choice** question
2. Type the first option (e.g., "0 - Sunset")
3. Hover over the option and click the **image icon** that appears on the right
4. Select **"URL"** tab
5. Paste the image URL from the Glyph Reference table above
6. Click **Select**
7. Repeat for all 16 options (0-9, A-F)

##### Create These 11 Questions (one for each glyph position 2-12):

**Question 1: "Glyph Position 2"**
```
Options with images:
- 0 - Sunset    [Add image: PORTALSYMBOL.0.png URL]
- 1 - Bird      [Add image: PORTALSYMBOL.1.png URL]
- 2 - Face      [Add image: PORTALSYMBOL.2.png URL]
- 3 - Diplo     [Add image: PORTALSYMBOL.3.png URL]
- 4 - Eclipse   [Add image: PORTALSYMBOL.4.png URL]
- 5 - Balloon   [Add image: PORTALSYMBOL.5.png URL]
- 6 - Boat      [Add image: PORTALSYMBOL.6.png URL]
- 7 - Bug       [Add image: PORTALSYMBOL.7.png URL]
- 8 - Dragonfly [Add image: PORTALSYMBOL.8.png URL]
- 9 - Galaxy    [Add image: PORTALSYMBOL.9.png URL]
- A - Voxel     [Add image: PORTALSYMBOL.A.png URL]
- B - Fish      [Add image: PORTALSYMBOL.B.png URL]
- C - Tent      [Add image: PORTALSYMBOL.C.png URL]
- D - Rocket    [Add image: PORTALSYMBOL.D.png URL]
- E - Tree      [Add image: PORTALSYMBOL.E.png URL]
- F - Atlas     [Add image: PORTALSYMBOL.F.png URL]
```
- Required: Yes

**Repeat** this exact question structure for positions 3, 4, 5, 6, 7, 8, 9, 10, 11, and 12 (11 total glyph questions).

> **Time-Saving Tip**: After creating the first glyph question with all 16 image options, use the **Duplicate** button (two overlapping squares icon) to copy it. Then just change the question title for each position.

**Tip**: Use a section header "System Location Glyphs (Positions 2-12)" before these questions to help users understand what they're entering.

#### Section 2: System Information

| Question | Type | Required | Options/Validation |
|----------|------|----------|-------------------|
| System Name | Short text | Yes | |
| Galaxy | Dropdown | Yes | Euclid, Hilbert Dimension, Calypso, Hesperius Dimension, Hyades, Ickjamatew, Budullangr, Kikolgallr, Eltiensleen, Eissentam, ... (add more as needed) |
| Star Type | Dropdown | No | Yellow, Red, Green, Blue |
| Economy Type | Dropdown | No | Balanced, Trading, Mining, Technology, Manufacturing, Scientific, Power Generation, Advanced Materials |
| Economy Level | Dropdown | No | Low, Medium, High |
| Conflict Level | Dropdown | No | Low, Medium, High |
| Dominant Lifeform | Dropdown | No | Gek, Vy'keen, Korvax, None |
| Discovered By | Short text | No | Your username |
| System Description/Notes | Paragraph | No | |

#### Section 3: Space Station

| Question | Type | Required | Options |
|----------|------|----------|---------|
| Has Space Station? | Multiple choice | Yes | Yes, No |
| Station Race | Dropdown | No (show if Yes) | Gek, Vy'keen, Korvax, Unknown |
| Station Sell % | Number | No | 0-100 |
| Station Buy % | Number | No | 0-100 |

### Form Response Destination
1. Click the "Responses" tab
2. Click the spreadsheet icon
3. Select "Select existing spreadsheet"
4. Choose your `Haven UI Submissions` spreadsheet
5. It will create/use the `Systems` tab

---

## Step 3: Create Form 2 - Planet

### Form Settings
- Title: `Haven UI - Planet Submission`
- Description: `Submit planet details. Submit this form once for each planet in the system.`

### Questions

#### Section 1: Link to System

| Question | Type | Required | Notes |
|----------|------|----------|-------|
| System Glyph (Positions 2-12) | Short text | Yes | User enters the 11-character system code |

**Or** repeat the 11 image-based glyph questions from Form 1 for positions 2-12.

#### Section 2: Planet Glyph Position 1

**Question: "Planet Index (Glyph Position 1)"**
- Type: Multiple choice with images
- Required: Yes

Create these options with the glyph images (same method as Form 1):
```
- 0 - Sunset    [Add image: PORTALSYMBOL.0.png URL]
- 1 - Bird      [Add image: PORTALSYMBOL.1.png URL]
- 2 - Face      [Add image: PORTALSYMBOL.2.png URL]
- 3 - Diplo     [Add image: PORTALSYMBOL.3.png URL]
- 4 - Eclipse   [Add image: PORTALSYMBOL.4.png URL]
- 5 - Balloon   [Add image: PORTALSYMBOL.5.png URL]
- 6 - Boat      [Add image: PORTALSYMBOL.6.png URL]
```

> **Note**: Most systems have 2-6 planets, so options 0-6 cover typical cases. You can add 7-F if needed for systems with more planets/moons.

#### Section 3: Planet Information

| Question | Type | Required | Options |
|----------|------|----------|---------|
| Planet Name | Short text | Yes | |
| Planet Size | Dropdown | No | Large, Medium, Small |
| Biome | Dropdown | No | Lush, Barren, Dead, Exotic, Scorched, Frozen, Toxic, Irradiated, Marsh, Volcanic, Swamp, Mineral, Fungal |
| Climate/Weather | Short text | No | |
| Sentinel Level | Dropdown | No | None, Low, Medium, High, Aggressive |
| Flora Level | Dropdown | No | N/A, None, Sparse, Low, Moderate, Abundant, Rich |
| Fauna Level | Dropdown | No | N/A, None, Sparse, Low, Moderate, Abundant, Rich |
| Fauna Count | Number | No | Number of species |
| Flora Count | Number | No | Number of species |
| Has Water? | Multiple choice | No | Yes, No |
| Resources/Materials | Short text | No | Comma-separated list |
| Planet Notes | Paragraph | No | |

### Form Response Destination
- Link to `Planets` tab in the same spreadsheet

---

## Step 4: Create Form 3 - Moon

### Form Settings
- Title: `Haven UI - Moon Submission`
- Description: `Submit moon details. Only submit if the planet has moons.`

### Questions

#### Section 1: Link to System & Planet

| Question | Type | Required |
|----------|------|----------|
| System Glyph (Positions 2-12) | Short text | Yes |
| Parent Planet Name | Short text | Yes |

#### Section 2: Moon Information

| Question | Type | Required | Options |
|----------|------|----------|---------|
| Moon Name | Short text | Yes | |
| Sentinel Level | Dropdown | No | None, Low, Medium, High, Aggressive |
| Flora Level | Dropdown | No | N/A, None, Sparse, Low, Moderate, Abundant, Rich |
| Fauna Level | Dropdown | No | N/A, None, Sparse, Low, Moderate, Abundant, Rich |
| Resources/Materials | Short text | No | |
| Moon Notes | Paragraph | No | |

### Form Response Destination
- Link to `Moons` tab in the same spreadsheet

---

## Step 5: Create Form 4 - Finalize Submission

### Form Settings
- Title: `Haven UI - Finalize & Submit`
- Description: `Submit this form AFTER you have entered all planets and moons. This will send your complete system to Haven UI for approval.`

### Questions

| Question | Type | Required |
|----------|------|----------|
| System Glyph (Positions 2-12) | Short text | Yes |
| Confirmation | Checkbox | Yes | "I have finished adding all planets and moons for this system" |
| Submitter Name (Optional) | Short text | No |

### Form Response Destination
- Link to `Submissions` tab in the same spreadsheet

---

## Step 6: Add the Apps Script

1. In your Google Sheet, go to **Extensions > Apps Script**
2. Delete any existing code
3. Paste the following code:

```javascript
/**
 * Haven UI - Google Forms Auto-Submission Script
 *
 * This script consolidates form responses and submits them to Haven UI
 * when a user completes Form 4 (Finalize Submission).
 */

// Configuration - Update these values
const CONFIG = {
  HAVEN_UI_URL: 'https://your-haven-ui-server.com', // Your Haven UI server URL
  API_ENDPOINT: '/api/submit_system',

  // Sheet names (must match your tab names)
  SYSTEMS_SHEET: 'Systems',
  PLANETS_SHEET: 'Planets',
  MOONS_SHEET: 'Moons',
  SUBMISSIONS_SHEET: 'Submissions'
};

/**
 * Trigger function - runs when Form 4 (Finalize) is submitted
 * Set this up: Triggers > Add Trigger > onFinalizeSubmission > From spreadsheet > On form submit
 */
function onFinalizeSubmission(e) {
  const sheet = e.range.getSheet();

  // Only process if this is from the Submissions sheet (Form 4)
  if (sheet.getName() !== CONFIG.SUBMISSIONS_SHEET) {
    return;
  }

  const row = e.range.getRow();
  const values = sheet.getRange(row, 1, 1, sheet.getLastColumn()).getValues()[0];

  // Column mapping for Submissions sheet (adjust based on your form)
  // Typically: Timestamp, System Glyph, Confirmation, Submitter Name
  const systemGlyph = values[1]; // Adjust index based on your form structure
  const submitterName = values[3] || 'Anonymous';

  if (!systemGlyph || systemGlyph.length !== 11) {
    Logger.log('Invalid system glyph: ' + systemGlyph);
    markSubmissionStatus(sheet, row, 'ERROR: Invalid glyph');
    return;
  }

  try {
    const payload = buildSubmissionPayload(systemGlyph, submitterName);

    if (!payload) {
      markSubmissionStatus(sheet, row, 'ERROR: No system data found');
      return;
    }

    const result = submitToHavenUI(payload);

    if (result.success) {
      markSubmissionStatus(sheet, row, 'SUBMITTED: ' + new Date().toISOString());
      markDataAsSubmitted(systemGlyph);
    } else {
      markSubmissionStatus(sheet, row, 'ERROR: ' + result.error);
    }
  } catch (error) {
    Logger.log('Submission error: ' + error.toString());
    markSubmissionStatus(sheet, row, 'ERROR: ' + error.toString());
  }
}

/**
 * Build the complete submission payload from all sheets
 */
function buildSubmissionPayload(systemGlyph, submitterName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Get system data
  const systemData = getSystemData(ss, systemGlyph);
  if (!systemData) {
    Logger.log('No system found for glyph: ' + systemGlyph);
    return null;
  }

  // Get planets
  const planets = getPlanetsData(ss, systemGlyph);
  if (planets.length === 0) {
    Logger.log('No planets found for glyph: ' + systemGlyph);
    return null;
  }

  // Get moons and attach to planets
  const moons = getMoonsData(ss, systemGlyph);
  attachMoonsToPlanets(planets, moons);

  // Build final payload
  const payload = {
    name: systemData.name,
    galaxy: systemData.galaxy || 'Euclid',
    glyph_code: buildFullGlyphCode(systemGlyph, planets[0].planetIndex),
    star_type: systemData.starType || null,
    economy_type: systemData.economyType || null,
    economy_level: systemData.economyLevel || null,
    conflict_level: systemData.conflictLevel || null,
    dominant_lifeform: systemData.dominantLifeform || null,
    discovered_by: systemData.discoveredBy || submitterName,
    description: systemData.description || null,
    submitted_by: submitterName,
    planets: planets.map(p => ({
      name: p.name,
      planet_index: hexToInt(p.planetIndex),
      biome: p.biome || null,
      climate: p.climate || null,
      sentinel: p.sentinel || 'None',
      flora: p.flora || 'N/A',
      fauna: p.fauna || 'N/A',
      fauna_count: p.faunaCount || 0,
      flora_count: p.floraCount || 0,
      has_water: p.hasWater ? 1 : 0,
      materials: p.resources || null,
      notes: p.notes || null,
      planet_size: p.planetSize || null,
      moons: (p.moons || []).map(m => ({
        name: m.name,
        sentinel: m.sentinel || 'None',
        flora: m.flora || 'N/A',
        fauna: m.fauna || 'N/A',
        materials: m.resources || null,
        notes: m.notes || null
      }))
    }))
  };

  // Add space station if present
  if (systemData.hasSpaceStation) {
    payload.space_station = {
      name: systemData.name + ' Station',
      race: systemData.stationRace || 'Unknown',
      sell_percent: systemData.stationSellPercent || 80,
      buy_percent: systemData.stationBuyPercent || 50
    };
  }

  return payload;
}

/**
 * Get system data from Systems sheet
 */
function getSystemData(ss, systemGlyph) {
  const sheet = ss.getSheetByName(CONFIG.SYSTEMS_SHEET);
  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  // Find the glyph column (should be columns for positions 2-12)
  // This assumes the glyphs are in columns after timestamp
  // Adjust column indices based on your actual form structure

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const rowGlyph = extractSystemGlyph(row, headers);

    if (rowGlyph === systemGlyph) {
      return parseSystemRow(row, headers);
    }
  }

  return null;
}

/**
 * Extract 11-character system glyph from row
 * Adjust column indices based on your form structure
 */
function extractSystemGlyph(row, headers) {
  // If glyphs are in separate columns (positions 2-12)
  // Columns after timestamp would be indices 1-11
  let glyph = '';
  for (let i = 1; i <= 11; i++) {
    glyph += (row[i] || '0').toString().toUpperCase();
  }
  return glyph;
}

/**
 * Parse system row into structured data
 * IMPORTANT: Adjust column indices to match your form!
 */
function parseSystemRow(row, headers) {
  // These indices assume:
  // 0: Timestamp
  // 1-11: Glyph positions 2-12
  // 12+: System fields

  return {
    name: row[12] || '',                    // System Name
    galaxy: row[13] || 'Euclid',            // Galaxy
    starType: row[14] || null,              // Star Type
    economyType: row[15] || null,           // Economy Type
    economyLevel: row[16] || null,          // Economy Level
    conflictLevel: row[17] || null,         // Conflict Level
    dominantLifeform: row[18] || null,      // Dominant Lifeform
    discoveredBy: row[19] || null,          // Discovered By
    description: row[20] || null,           // Description
    hasSpaceStation: row[21] === 'Yes',     // Has Space Station
    stationRace: row[22] || null,           // Station Race
    stationSellPercent: parseInt(row[23]) || 80,  // Sell %
    stationBuyPercent: parseInt(row[24]) || 50    // Buy %
  };
}

/**
 * Get all planets for a system
 */
function getPlanetsData(ss, systemGlyph) {
  const sheet = ss.getSheetByName(CONFIG.PLANETS_SHEET);
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const planets = [];

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const rowGlyph = row[1]; // Assuming system glyph is in column B (index 1)

    if (rowGlyph && rowGlyph.toString().toUpperCase() === systemGlyph) {
      planets.push(parsePlanetRow(row, headers));
    }
  }

  return planets;
}

/**
 * Parse planet row into structured data
 * IMPORTANT: Adjust column indices to match your form!
 */
function parsePlanetRow(row, headers) {
  // Adjust these indices based on your Planet form structure
  return {
    planetIndex: (row[2] || '0').toString().toUpperCase(), // Planet Index (glyph position 1)
    name: row[3] || '',                     // Planet Name
    planetSize: row[4] || null,             // Planet Size
    biome: row[5] || null,                  // Biome
    climate: row[6] || null,                // Climate/Weather
    sentinel: row[7] || 'None',             // Sentinel Level
    flora: row[8] || 'N/A',                 // Flora Level
    fauna: row[9] || 'N/A',                 // Fauna Level
    faunaCount: parseInt(row[10]) || 0,     // Fauna Count
    floraCount: parseInt(row[11]) || 0,     // Flora Count
    hasWater: row[12] === 'Yes',            // Has Water
    resources: row[13] || null,             // Resources
    notes: row[14] || null,                 // Notes
    moons: []                               // Will be populated later
  };
}

/**
 * Get all moons for a system
 */
function getMoonsData(ss, systemGlyph) {
  const sheet = ss.getSheetByName(CONFIG.MOONS_SHEET);
  if (!sheet) return [];

  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const moons = [];

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const rowGlyph = row[1]; // System glyph column

    if (rowGlyph && rowGlyph.toString().toUpperCase() === systemGlyph) {
      moons.push(parseMoonRow(row, headers));
    }
  }

  return moons;
}

/**
 * Parse moon row into structured data
 * IMPORTANT: Adjust column indices to match your form!
 */
function parseMoonRow(row, headers) {
  return {
    parentPlanetName: row[2] || '',         // Parent Planet Name
    name: row[3] || '',                     // Moon Name
    sentinel: row[4] || 'None',             // Sentinel Level
    flora: row[5] || 'N/A',                 // Flora Level
    fauna: row[6] || 'N/A',                 // Fauna Level
    resources: row[7] || null,              // Resources
    notes: row[8] || null                   // Notes
  };
}

/**
 * Attach moons to their parent planets
 */
function attachMoonsToPlanets(planets, moons) {
  for (const moon of moons) {
    const parentPlanet = planets.find(p =>
      p.name.toLowerCase() === moon.parentPlanetName.toLowerCase()
    );

    if (parentPlanet) {
      parentPlanet.moons.push(moon);
    }
  }
}

/**
 * Build full 12-character glyph code
 */
function buildFullGlyphCode(systemGlyph, planetIndex) {
  return (planetIndex || '1') + systemGlyph;
}

/**
 * Convert hex character to integer
 */
function hexToInt(hex) {
  return parseInt(hex, 16);
}

/**
 * Submit payload to Haven UI
 */
function submitToHavenUI(payload) {
  const url = CONFIG.HAVEN_UI_URL + CONFIG.API_ENDPOINT;

  const options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();

    Logger.log('Haven UI Response: ' + responseCode + ' - ' + responseText);

    if (responseCode >= 200 && responseCode < 300) {
      return { success: true, response: JSON.parse(responseText) };
    } else {
      return { success: false, error: responseText };
    }
  } catch (error) {
    Logger.log('HTTP Error: ' + error.toString());
    return { success: false, error: error.toString() };
  }
}

/**
 * Mark submission status in the Submissions sheet
 */
function markSubmissionStatus(sheet, row, status) {
  const statusColumn = sheet.getLastColumn() + 1;
  sheet.getRange(row, statusColumn).setValue(status);
}

/**
 * Mark source data as submitted (optional - adds a column to track)
 */
function markDataAsSubmitted(systemGlyph) {
  // Optionally mark rows in Systems/Planets/Moons sheets as submitted
  // This prevents duplicate submissions
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Add "Submitted" column to Systems sheet
  const systemsSheet = ss.getSheetByName(CONFIG.SYSTEMS_SHEET);
  const systemsData = systemsSheet.getDataRange().getValues();

  for (let i = 1; i < systemsData.length; i++) {
    const rowGlyph = extractSystemGlyph(systemsData[i], systemsData[0]);
    if (rowGlyph === systemGlyph) {
      // Add submitted timestamp to last column
      const lastCol = systemsSheet.getLastColumn();
      systemsSheet.getRange(i + 1, lastCol + 1).setValue('Submitted: ' + new Date().toISOString());
    }
  }
}

/**
 * Manual test function - run this to test with a specific glyph
 */
function testSubmission() {
  const testGlyph = '00000000000'; // Replace with a real 11-character glyph from your data
  const payload = buildSubmissionPayload(testGlyph, 'Test User');

  if (payload) {
    Logger.log('Payload built successfully:');
    Logger.log(JSON.stringify(payload, null, 2));

    // Uncomment to actually submit:
    // const result = submitToHavenUI(payload);
    // Logger.log('Submission result: ' + JSON.stringify(result));
  } else {
    Logger.log('Failed to build payload - check your data');
  }
}

/**
 * Setup function - creates necessary triggers
 * Run this once after setting up the script
 */
function setupTriggers() {
  // Remove existing triggers
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'onFinalizeSubmission') {
      ScriptApp.deleteTrigger(trigger);
    }
  }

  // Create new trigger for form submissions
  ScriptApp.newTrigger('onFinalizeSubmission')
    .forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet())
    .onFormSubmit()
    .create();

  Logger.log('Trigger created successfully');
}
```

---

## Step 7: Configure and Deploy

### 7.1 Update Configuration

In the Apps Script, update the `CONFIG` object:

```javascript
const CONFIG = {
  HAVEN_UI_URL: 'https://your-actual-server.com',  // Your Haven UI URL
  API_ENDPOINT: '/api/submit_system',
  // ... rest of config
};
```

### 7.2 Adjust Column Indices

The script has comments marked `IMPORTANT: Adjust column indices to match your form!`

After creating your forms and checking the sheet columns, update these functions:
- `parseSystemRow()` - Match to your Systems sheet columns
- `parsePlanetRow()` - Match to your Planets sheet columns
- `parseMoonRow()` - Match to your Moons sheet columns
- `extractSystemGlyph()` - Match to where glyph data appears

### 7.3 Run Setup

1. In Apps Script, select `setupTriggers` from the function dropdown
2. Click Run
3. Grant necessary permissions when prompted

### 7.4 Test

1. Run `testSubmission` function to verify payload building
2. Check the Logs (View > Logs) for output
3. Submit a test through the forms and verify it reaches Haven UI

---

## Step 8: Share the Forms

Once everything is working:

1. In each Google Form, click "Send"
2. Copy the shareable link
3. Provide users with links to all 4 forms in order:
   - Form 1: System (start here)
   - Form 2: Planet (submit for each planet)
   - Form 3: Moon (optional)
   - Form 4: Finalize (submit when done)

### Recommended: Create a Landing Page

Create a simple Google Doc or Google Site that explains the process and links to all forms in order.

---

## User Flow Summary

```
User Journey:

1. Fill Form 1 (System)
   - Enter 11 glyphs (positions 2-12)
   - Enter system name, galaxy, etc.
   - Enter space station info
                    ↓
2. Fill Form 2 (Planet) - repeat for each planet
   - Enter same 11 glyphs to link
   - Enter planet index (position 1)
   - Enter planet details
                    ↓
3. Fill Form 3 (Moon) - optional, for each moon
   - Enter same 11 glyphs
   - Enter parent planet name
   - Enter moon details
                    ↓
4. Fill Form 4 (Finalize)
   - Enter same 11 glyphs
   - Confirm completion
   - Script auto-submits to Haven UI!
                    ↓
5. Admin reviews in Haven UI pending queue
```

---

## Troubleshooting

### "No system data found"
- Check that the system glyph in Form 4 matches exactly what was entered in Form 1
- Verify column indices in the script match your sheet structure

### "Invalid glyph"
- Ensure glyph is exactly 11 characters (positions 2-12)
- Check for extra spaces or lowercase letters

### Script not triggering
- Run `setupTriggers()` again
- Check Triggers page (Edit > Current project's triggers)

### Network/Permission errors
- Ensure Haven UI server is accessible from Google's servers
- Check CORS settings on Haven UI if needed

---

## Security Notes

- Form responses are stored in your Google Sheet (you control access)
- The script POSTs to Haven UI's public submission endpoint
- No authentication is sent (submissions go to pending queue)
- Haven UI admin must approve all submissions
- Users remain anonymous unless they provide a name

---

## Optional Enhancements

### Add Duplicate Prevention
Add a check in `onFinalizeSubmission` to prevent resubmitting the same system.

### Add Email Notifications
Use `MailApp.sendEmail()` to notify admin of new submissions.

### Add Validation
Add client-side validation in Google Forms using data validation rules.

### Hosted Glyph Images
Host the 16 glyph images somewhere accessible and add them to each multiple choice option in the forms.
