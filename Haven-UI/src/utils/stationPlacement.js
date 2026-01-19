/**
 * Space Station Placement Utility
 * Generates safe orbital positions for space stations in star systems
 * Ensures no planet orbit intersects with the station's orbital radius
 */

// Rendering sizes from VISUAL_CONFIG in map-viewer.js
const OBJECT_SIZES = {
    SUN_RADIUS: 0.5,
    PLANET_SIZE: 0.8,
    PLANET_HIT_RADIUS: 1.2,
    MOON_SIZE: 0.4,
    STATION_SIZE: 0.27,
    STATION_GLOW: 0.38
};

// Minimum safe distances
const MIN_DISTANCES = {
    STATION_TO_SUN: 1.5,      // Minimum distance from star center
    ORBITAL_BUFFER: 3.0,      // Buffer between station orbit and planet orbits
    STATION_TO_STATION: 1.5   // Buffer between multiple stations
};

/**
 * Calculate distance from origin (star center)
 */
function getOrbitalRadius(x, y, z) {
    return Math.sqrt(x * x + y * y + z * z);
}

/**
 * Calculate the orbital radius of each planet including its moons
 * Returns the effective orbital "zone" that the planet and its moons occupy
 */
function getPlanetOrbitalZone(planet) {
    const planetRadius = getOrbitalRadius(planet.x || 0, planet.y || 0, planet.z || 0);

    // Account for moon orbits - find the maximum moon orbital distance
    let maxMoonOrbit = 0;
    if (planet.moons && Array.isArray(planet.moons)) {
        for (const moon of planet.moons) {
            const moonOrbitRadius = moon.orbit_radius || moon.orbit_distance || 0.5;
            maxMoonOrbit = Math.max(maxMoonOrbit, moonOrbitRadius);
        }
    }

    return {
        name: planet.name,
        innerEdge: Math.max(0, planetRadius - maxMoonOrbit - MIN_DISTANCES.ORBITAL_BUFFER),
        center: planetRadius,
        outerEdge: planetRadius + maxMoonOrbit + MIN_DISTANCES.ORBITAL_BUFFER
    };
}

/**
 * Find safe orbital slots between planet orbits
 * Returns array of {min, max} orbital radius ranges where stations can be placed
 */
function findSafeOrbitalSlots(planets) {
    if (planets.length === 0) {
        // No planets - entire system is safe, default range
        return [{ min: MIN_DISTANCES.STATION_TO_SUN + 2, max: 40 }];
    }

    // Get orbital zones for all planets
    const zones = planets.map(getPlanetOrbitalZone);

    // Sort by orbital radius (closest to star first)
    zones.sort((a, b) => a.center - b.center);

    const safeSlots = [];

    // Check gap between sun and first planet
    const firstPlanetInner = zones[0].innerEdge;
    if (firstPlanetInner > MIN_DISTANCES.STATION_TO_SUN + 2) {
        safeSlots.push({
            min: MIN_DISTANCES.STATION_TO_SUN + 2,
            max: firstPlanetInner - 1,
            label: 'Inner system (before first planet)'
        });
    }

    // Check gaps between planets
    for (let i = 0; i < zones.length - 1; i++) {
        const currentOuter = zones[i].outerEdge;
        const nextInner = zones[i + 1].innerEdge;

        const gapSize = nextInner - currentOuter;
        if (gapSize >= 2) {  // Need at least 2 units of space
            safeSlots.push({
                min: currentOuter + 0.5,
                max: nextInner - 0.5,
                label: `Between ${zones[i].name} and ${zones[i + 1].name}`
            });
        }
    }

    // Add outer system (beyond last planet) - always safe
    const lastPlanetOuter = zones[zones.length - 1].outerEdge;
    safeSlots.push({
        min: lastPlanetOuter + 1,
        max: lastPlanetOuter + 15,  // Reasonable outer limit
        label: 'Outer system (beyond last planet)'
    });

    return safeSlots;
}

/**
 * Generate safe station position that doesn't intersect with any planet orbit
 * Uses NMS-style placement: fixed orbital distance between planet orbits
 *
 * @param {Array} planets - Array of planet objects with x, y, z, name, moons
 * @param {Array} existingStations - Array of existing stations to avoid
 * @param {Object} options - Configuration options
 * @returns {Object} - {x, y, z, orbitalRadius, slot} coordinates and metadata
 */
export function generateStationPosition(planets = [], existingStations = [], options = {}) {
    const {
        preferredSlot = 'outer',  // 'inner', 'outer', or 'largest'
        fixedAngle = null         // null for random, or specific angle in degrees
    } = options;

    // Find safe orbital slots
    const safeSlots = findSafeOrbitalSlots(planets);

    console.log(`[Station Placement] Found ${safeSlots.length} safe orbital slots:`);
    safeSlots.forEach((slot, i) => {
        console.log(`  ${i + 1}. ${slot.label}: ${slot.min.toFixed(1)} - ${slot.max.toFixed(1)} units`);
    });

    if (safeSlots.length === 0) {
        console.warn('[Station Placement] No safe slots found, using fallback');
        return {
            x: 10,
            y: 0,
            z: 0,
            orbitalRadius: 10,
            slot: 'fallback',
            fallback: true
        };
    }

    // Select slot based on preference
    let selectedSlot;
    if (preferredSlot === 'inner' && safeSlots.length > 0) {
        selectedSlot = safeSlots[0];
    } else if (preferredSlot === 'largest') {
        // Find largest gap
        selectedSlot = safeSlots.reduce((largest, slot) => {
            const size = slot.max - slot.min;
            const largestSize = largest.max - largest.min;
            return size > largestSize ? slot : largest;
        }, safeSlots[0]);
    } else {
        // Default: outer system (last slot, beyond all planets)
        selectedSlot = safeSlots[safeSlots.length - 1];
    }

    console.log(`[Station Placement] Selected slot: ${selectedSlot.label}`);

    // Calculate orbital radius (middle of the selected slot)
    const orbitalRadius = (selectedSlot.min + selectedSlot.max) / 2;

    // Determine angle (theta)
    let theta;
    if (fixedAngle !== null) {
        theta = (fixedAngle * Math.PI) / 180;  // Convert degrees to radians
    } else {
        // Random angle, but avoid placing too close to existing stations
        theta = Math.random() * Math.PI * 2;

        // Check existing stations and adjust if too close
        for (const station of existingStations) {
            const stationRadius = getOrbitalRadius(station.x, station.y, station.z);
            // If similar orbital radius, ensure angular separation
            if (Math.abs(stationRadius - orbitalRadius) < 5) {
                const stationAngle = Math.atan2(station.z, station.x);
                const angleDiff = Math.abs(theta - stationAngle);
                if (angleDiff < Math.PI / 4) {  // Too close (< 45 degrees)
                    theta = (theta + Math.PI) % (Math.PI * 2);  // Flip to opposite side
                }
            }
        }
    }

    // Slight vertical offset (phi) - stations typically near ecliptic plane
    const phi = (Math.random() - 0.5) * 0.2;  // ±0.1 radians (~6 degrees)

    // Convert to Cartesian coordinates
    const x = orbitalRadius * Math.cos(phi) * Math.cos(theta);
    const y = orbitalRadius * Math.sin(phi);
    const z = orbitalRadius * Math.cos(phi) * Math.sin(theta);

    console.log(`[Station Placement] ✅ Position: (${x.toFixed(2)}, ${y.toFixed(2)}, ${z.toFixed(2)})`);
    console.log(`[Station Placement] Orbital radius: ${orbitalRadius.toFixed(2)} units`);

    return {
        x: parseFloat(x.toFixed(2)),
        y: parseFloat(y.toFixed(2)),
        z: parseFloat(z.toFixed(2)),
        orbitalRadius: parseFloat(orbitalRadius.toFixed(2)),
        slot: selectedSlot.label,
        fallback: false
    };
}

/**
 * Legacy function name for backwards compatibility
 */
export function generateRandomStationPosition(planets = [], existingStations = [], options = {}) {
    return generateStationPosition(planets, existingStations, options);
}

/**
 * Validate that a station position doesn't intersect with any planet orbit
 */
export function validateStationOrbit(stationX, stationY, stationZ, planets) {
    const stationRadius = getOrbitalRadius(stationX, stationY, stationZ);

    for (const planet of planets) {
        const zone = getPlanetOrbitalZone(planet);

        // Check if station's orbital radius falls within planet's orbital zone
        if (stationRadius >= zone.innerEdge && stationRadius <= zone.outerEdge) {
            return {
                valid: false,
                reason: `Station orbit (${stationRadius.toFixed(1)} units) intersects with ${planet.name}'s orbital zone (${zone.innerEdge.toFixed(1)} - ${zone.outerEdge.toFixed(1)} units)`
            };
        }
    }

    // Check minimum distance from star
    if (stationRadius < MIN_DISTANCES.STATION_TO_SUN) {
        return {
            valid: false,
            reason: `Station too close to star (${stationRadius.toFixed(1)} < ${MIN_DISTANCES.STATION_TO_SUN} units)`
        };
    }

    return { valid: true, reason: 'Position is safe' };
}

/**
 * Get orbital information for display
 */
export function getOrbitalInfo(x, y, z) {
    const radius = getOrbitalRadius(x, y, z);
    const angle = Math.atan2(z, x) * (180 / Math.PI);  // Convert to degrees

    return {
        radius: parseFloat(radius.toFixed(2)),
        angle: parseFloat(angle.toFixed(1)),
        description: `${radius.toFixed(1)} units from star at ${angle.toFixed(0)}°`
    };
}

// Export constants for testing/debugging
export { OBJECT_SIZES, MIN_DISTANCES };
