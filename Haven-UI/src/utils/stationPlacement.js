/**
 * Space Station Random Placement Utility
 * Generates collision-free random positions for space stations in star systems
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

// Minimum safe distances (center-to-center)
const MIN_DISTANCES = {
    STATION_TO_SUN: 1.5,      // 0.5 sun + 0.38 station glow + 0.6 buffer
    STATION_TO_PLANET: 2.0,   // 1.2 planet hit + 0.38 station glow + 0.4 buffer
    STATION_TO_MOON: 1.5,     // 0.4 moon + 0.38 station glow + 0.7 buffer
    STATION_TO_STATION: 1.5   // 0.38 + 0.38 + 0.7 buffer
};

/**
 * Calculate distance between two 3D points
 */
function distance3D(x1, y1, z1, x2, y2, z2) {
    return Math.sqrt(
        (x2 - x1) ** 2 +
        (y2 - y1) ** 2 +
        (z2 - z1) ** 2
    );
}

/**
 * Calculate moon absolute position (moons are relative to planets)
 * This is a simplified calculation - actual moon positions orbit over time
 */
function getMoonAbsolutePosition(planet, moon) {
    // Moons orbit their planets, so we need to check a safe radius around the planet
    // For collision detection, we use the maximum orbital radius
    const orbitRadius = moon.orbit_radius || moon.orbit_distance || 0.5;

    return {
        x: planet.x,
        y: planet.y,
        z: planet.z,
        radius: orbitRadius  // Treat as sphere around planet
    };
}

/**
 * Check if a position collides with any existing objects
 */
function checkCollision(x, y, z, planets, existingStations = []) {
    // Check collision with sun (at origin 0, 0, 0)
    const distToSun = Math.sqrt(x * x + y * y + z * z);
    if (distToSun < MIN_DISTANCES.STATION_TO_SUN) {
        return { collision: true, reason: `Too close to sun (${distToSun.toFixed(2)} < ${MIN_DISTANCES.STATION_TO_SUN})` };
    }

    // Check collision with planets
    for (const planet of planets) {
        const distToPlanet = distance3D(x, y, z, planet.x || 0, planet.y || 0, planet.z || 0);
        if (distToPlanet < MIN_DISTANCES.STATION_TO_PLANET) {
            return {
                collision: true,
                reason: `Too close to planet "${planet.name}" (${distToPlanet.toFixed(2)} < ${MIN_DISTANCES.STATION_TO_PLANET})`
            };
        }

        // Check collision with moons orbiting this planet
        if (planet.moons && Array.isArray(planet.moons)) {
            for (const moon of planet.moons) {
                const moonPos = getMoonAbsolutePosition(planet, moon);

                // Check distance to moon's orbital sphere
                const distToMoonCenter = distance3D(
                    x, y, z,
                    moonPos.x, moonPos.y, moonPos.z
                );

                // Add orbital radius to minimum distance
                const minDistToMoon = MIN_DISTANCES.STATION_TO_MOON + moonPos.radius;

                if (distToMoonCenter < minDistToMoon) {
                    return {
                        collision: true,
                        reason: `Too close to moon "${moon.name}" orbit (${distToMoonCenter.toFixed(2)} < ${minDistToMoon.toFixed(2)})`
                    };
                }
            }
        }
    }

    // Check collision with existing space stations
    for (const station of existingStations) {
        const distToStation = distance3D(x, y, z, station.x || 0, station.y || 0, station.z || 0);
        if (distToStation < MIN_DISTANCES.STATION_TO_STATION) {
            return {
                collision: true,
                reason: `Too close to station "${station.name}" (${distToStation.toFixed(2)} < ${MIN_DISTANCES.STATION_TO_STATION})`
            };
        }
    }

    return { collision: false };
}

/**
 * Generate random position for space station with collision avoidance
 *
 * @param {Array} planets - Array of planet objects with x, y, z, name, moons
 * @param {Array} existingStations - Array of existing stations to avoid
 * @param {Object} options - Configuration options
 * @returns {Object} - {x, y, z, attempts, fallback} coordinates
 */
export function generateRandomStationPosition(planets = [], existingStations = [], options = {}) {
    const {
        maxAttempts = 100,
        minOrbitMultiplier = 0.5,  // Start at 50% of innermost planet radius
        maxOrbitMultiplier = 1.5,  // End at 150% of outermost planet radius
        defaultMinOrbit = 5.0,     // Fallback if no planets
        defaultMaxOrbit = 40.0,    // Fallback if no planets
        phiRange = 0.5,            // Vertical angle range (0.5 = ±45° from equator)
        preferTradeRoutes = false  // Future: bias towards planet midpoints
    } = options;

    // Determine orbital radius range based on planets
    let minOrbit = defaultMinOrbit;
    let maxOrbit = defaultMaxOrbit;

    if (planets.length > 0) {
        const planetRadii = planets.map(p =>
            Math.sqrt((p.x || 0) ** 2 + (p.y || 0) ** 2 + (p.z || 0) ** 2)
        );

        const innermost = Math.min(...planetRadii);
        const outermost = Math.max(...planetRadii);

        minOrbit = innermost * minOrbitMultiplier;
        maxOrbit = outermost * maxOrbitMultiplier;

        // Ensure minimum orbit is at least outside sun's danger zone
        minOrbit = Math.max(minOrbit, MIN_DISTANCES.STATION_TO_SUN + 1.0);
    }

    console.log(`[Station Placement] Orbital range: ${minOrbit.toFixed(2)} to ${maxOrbit.toFixed(2)} units`);
    console.log(`[Station Placement] Avoiding ${planets.length} planets and ${existingStations.length} existing stations`);

    // Try to find a collision-free position
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        // Generate random spherical coordinates
        const radius = minOrbit + Math.random() * (maxOrbit - minOrbit);
        const theta = Math.random() * Math.PI * 2;  // 0 to 360° (azimuth)
        const phi = (Math.random() - 0.5) * Math.PI * phiRange;  // Vertical angle from equator

        // Convert to Cartesian coordinates
        const x = radius * Math.cos(phi) * Math.cos(theta);
        const y = radius * Math.sin(phi);
        const z = radius * Math.cos(phi) * Math.sin(theta);

        // Check for collisions
        const collisionCheck = checkCollision(x, y, z, planets, existingStations);

        if (!collisionCheck.collision) {
            console.log(`[Station Placement] ✅ Found safe position after ${attempt + 1} attempts`);
            console.log(`[Station Placement] Position: (${x.toFixed(2)}, ${y.toFixed(2)}, ${z.toFixed(2)})`);

            return {
                x: parseFloat(x.toFixed(2)),
                y: parseFloat(y.toFixed(2)),
                z: parseFloat(z.toFixed(2)),
                attempts: attempt + 1,
                fallback: false
            };
        } else {
            if (attempt % 20 === 0 && attempt > 0) {
                console.log(`[Station Placement] Attempt ${attempt}: ${collisionCheck.reason}`);
            }
        }
    }

    // Fallback: place at a safe default location
    console.warn(`[Station Placement] ⚠️ Could not find collision-free position after ${maxAttempts} attempts`);
    console.warn(`[Station Placement] Using fallback position`);

    const fallbackX = minOrbit + 5;
    const fallbackY = 0;
    const fallbackZ = 0;

    return {
        x: parseFloat(fallbackX.toFixed(2)),
        y: parseFloat(fallbackY.toFixed(2)),
        z: parseFloat(fallbackZ.toFixed(2)),
        attempts: maxAttempts,
        fallback: true
    };
}

/**
 * Generate multiple station positions (for systems with multiple stations)
 */
export function generateMultipleStationPositions(planets, count = 1, options = {}) {
    const stations = [];

    for (let i = 0; i < count; i++) {
        const position = generateRandomStationPosition(planets, stations, options);
        stations.push({
            name: `Station ${i + 1}`,
            ...position
        });
    }

    return stations;
}

/**
 * Validate existing station position (for migration/debugging)
 */
export function validateStationPosition(station, planets, otherStations = []) {
    const collisionCheck = checkCollision(
        station.x,
        station.y,
        station.z,
        planets,
        otherStations
    );

    return {
        valid: !collisionCheck.collision,
        reason: collisionCheck.reason || 'Position is safe',
        station: station.name || 'Unnamed Station'
    };
}

// Export constants for testing/debugging
export { OBJECT_SIZES, MIN_DISTANCES };
