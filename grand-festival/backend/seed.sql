-- Grand Festival — initial civ roster.
-- db.init_db() runs this ONLY when the civilizations table is empty,
-- so it never duplicates rows or overwrites admin edits on restart.
--
-- Seeded from the participants in the festival schedule sheet. Roles are short
-- labels derived from each host's stated activity; descriptions use what they
-- actually signed up to run. Statuses are all 'confirmed' (everyone here has a
-- scheduled slot) except Neoterra, marked 'host' since it runs the Grand
-- Festival at the main system. Manage everything else via /admin.

INSERT INTO civilizations (name, role, description, status, approval_state, display_order) VALUES
('Neoterra', 'Festival Host',
 'Hosting the Grand Festival at the main system (6055FA438506).',
 'host', 'approved', 1),

('Voyager''s Haven', 'Festival Builds',
 'Joining the Summer Grand Festival — activity to be announced.',
 'confirmed', 'approved', 10),

('The Galactic Tea Rooms', 'Community Showcase',
 'Running a Community Showcase and Activities.',
 'confirmed', 'approved', 20),

('Everion Empire', 'PvP Arena',
 'PvP battle and spectating, plus an exotic egg giveaway.',
 'confirmed', 'approved', 30),

('Bunsmasters', 'Baking Competition',
 'Running the festival Baking Competition at the main system.',
 'confirmed', 'approved', 40),

('Redwater Runners', 'Build Cruise',
 'A planet and build cruise with a corvette showcase.',
 'confirmed', 'approved', 50),

('Solara Prime - Eissentam', 'City Showcase',
 'Solara Prime Sol City showcase, plus Pulse Racing and the Bitten Bay rendezvous.',
 'confirmed', 'approved', 60),

('Dread-Force', 'Showcases',
 'A Community Showcase, a Castle show, and the Thal Nexus of Dread showcase.',
 'confirmed', 'approved', 70),

('PodManSky', 'Festival Participant',
 'Joining the Summer Grand Festival — activity to be announced.',
 'confirmed', 'approved', 80),

('NMSCord Hub', 'Community Hub',
 'Details to be announced.',
 'confirmed', 'approved', 90);
