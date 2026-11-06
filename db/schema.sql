CREATE TABLE stops(id INTEGER PRIMARY KEY, name TEXT, lat REAL, lon REAL);
CREATE TABLE routes(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE route_stops(route_id INT, seq INT, stop_id INT, PRIMARY KEY(route_id, seq));
CREATE TABLE buses(id INTEGER PRIMARY KEY, plate TEXT, route_id INT, base_speed REAL);
CREATE TABLE position_log(id INTEGER PRIMARY KEY AUTOINCREMENT, bus_id INT, lat REAL, lon REAL, speed REAL, ts DATETIME DEFAULT CURRENT_TIMESTAMP);

-- BVC Engineering College (Odalarevu) & Amalapuram Bus Network
INSERT INTO stops VALUES
(0, 'Amalapuram RTC Bus Complex', 16.5798, 81.9978),
(1, 'Amalapuram Clock Tower', 16.5748, 81.9935),
(2, 'Black Bridge (Nalla Vantena)', 16.5680, 81.9920),
(3, 'Bandarulanka Center', 16.5510, 81.9910),
(4, 'Allavaram Junction', 16.5171, 81.9885),
(5, 'Mogalikuduru', 16.4820, 81.9680),
(6, 'Godi Junction', 16.4420, 81.9450),
(7, 'Komaragiripatnam', 16.3980, 81.9120),
(8, 'Odalarevu Village Center', 16.3580, 81.8750),
(9, 'BVC Main Entrance Arch', 16.3496, 81.8654),
(10, 'BVC Admin & Central Library', 16.3508, 81.8665),
(11, 'BVC CSE & ECE Blocks', 16.3518, 81.8678),
(12, 'BVC Campus Canteen', 16.3524, 81.8685),
(13, 'BVC Hostels & Sports Ground', 16.3532, 81.8696),
(14, 'Odalarevu Beach Road', 16.3480, 81.8720);

INSERT INTO routes VALUES
(1, 'R1 Amalapuram - BVC College Express'),
(2, 'R2 BVC Odalarevu Campus & Beach Shuttle');

-- Route 1: Amalapuram to BVC Campus
INSERT INTO route_stops VALUES
(1, 0, 0),
(1, 1, 1),
(1, 2, 2),
(1, 3, 3),
(1, 4, 4),
(1, 5, 5),
(1, 6, 6),
(1, 7, 7),
(1, 8, 8),
(1, 9, 9);

-- Route 2: BVC Campus & Odalarevu Loop
INSERT INTO route_stops VALUES
(2, 0, 9),
(2, 1, 10),
(2, 2, 11),
(2, 3, 12),
(2, 4, 13),
(2, 5, 14),
(2, 6, 8);

-- BVC College Buses
INSERT INTO buses VALUES
(101, 'AP-29-BV-1001', 1, 38.0),
(102, 'AP-29-BV-1002', 1, 34.0),
(103, 'AP-29-BV-2001', 2, 26.0),
(104, 'AP-29-BV-2002', 2, 24.0);
