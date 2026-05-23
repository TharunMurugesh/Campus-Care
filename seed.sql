-- seed.sql

-- Insert Departments
INSERT INTO departments (name) VALUES 
('Academics'),
('Hostel'),
('IT'),
('Essentials'),
('Maintenance');

-- The default password for all users is: password123
-- which is hashed below using Werkzeug's generate_password_hash default method (scrypt)
-- Hash: scrypt:32768:8:1$P3o4X4W1Dq6M3nU0$e7d6a5c2d3b2f2c2b3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8

-- NOTE: For simplicity, replacing with a statically generated hash from Werkzeug.
-- hash of 'password123'
DO $$ 
DECLARE 
    test_hash VARCHAR := 'scrypt:32768:8:1$qQd1w9T809QnN00z$455351aab2a1b9423c139db92ce570d588da9d8032483da52c6f66de92e92e59e22dbdb5ef90b7a83d3e33e9b16b47c030310ebccbeaa52d2745300e84b72ba4';
BEGIN

-- Insert Users
-- Superadmin
INSERT INTO users (name, email, password_hash, role, department_id) VALUES 
('Super Admin', 'admin@campus.edu', test_hash, 'superadmin', NULL);

-- Students
INSERT INTO users (name, email, password_hash, role, department_id) VALUES 
('Alice Student', 'student1@campus.edu', test_hash, 'student', NULL),
('Bob Student', 'student2@campus.edu', test_hash, 'student', NULL);

-- Staff Members
INSERT INTO users (name, email, password_hash, role, department_id) VALUES 
('Charlie IT', 'it_staff@campus.edu', test_hash, 'staff', 3), -- IT
('Dave IT', 'it_staff2@campus.edu', test_hash, 'staff', 3), -- IT
('Eve Maintenance', 'maint_staff@campus.edu', test_hash, 'staff', 5), -- Maintenance
('Frank Academics', 'acad_staff@campus.edu', test_hash, 'staff', 1); -- Academics

-- Insert sample tickets
INSERT INTO tickets (ticket_code, title, description, priority, status, student_id, department_id, assigned_to, created_at, updated_at) VALUES 
('CAMP-101', 'Wifi not working in Room 204', 'The wifi has been down since morning.', 'HIGH', 'OPEN', 2, 3, NULL, CURRENT_TIMESTAMP - INTERVAL '1 day', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CAMP-102', 'Broken chair in Library', 'One of the chairs in the reading hall is broken.', 'LOW', 'CLAIMED', 3, 5, 6, CURRENT_TIMESTAMP - INTERVAL '2 days', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('CAMP-103', 'Course registration portal error', 'Unable to register for CS101.', 'MEDIUM', 'IN_PROGRESS', 2, 1, 7, CURRENT_TIMESTAMP - INTERVAL '3 days', CURRENT_TIMESTAMP - INTERVAL '12 hours');

-- Set claimed_at for the claimed/in_progress tickets
UPDATE tickets SET claimed_at = CURRENT_TIMESTAMP - INTERVAL '1 day' WHERE ticket_code IN ('CAMP-102', 'CAMP-103');

-- Insert initial activity logs
INSERT INTO activity_logs (ticket_id, action, performed_by, created_at) VALUES 
(1, 'Ticket created', 2, CURRENT_TIMESTAMP - INTERVAL '1 day'),
(2, 'Ticket created', 3, CURRENT_TIMESTAMP - INTERVAL '2 days'),
(2, 'Ticket claimed', 6, CURRENT_TIMESTAMP - INTERVAL '1 day'),
(3, 'Ticket created', 2, CURRENT_TIMESTAMP - INTERVAL '3 days'),
(3, 'Ticket claimed', 7, CURRENT_TIMESTAMP - INTERVAL '1 day'),
(3, 'Status changed to IN_PROGRESS', 7, CURRENT_TIMESTAMP - INTERVAL '12 hours');

-- Add some comments
INSERT INTO comments (ticket_id, user_id, comment, created_at) VALUES 
(2, 6, 'I will fix this by evening.', CURRENT_TIMESTAMP - INTERVAL '20 hours'),
(3, 7, 'Looking into the server logs.', CURRENT_TIMESTAMP - INTERVAL '11 hours');

END $$;
