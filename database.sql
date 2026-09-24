-- Vehicle Service Management System - database setup

 
CREATE DATABASE IF NOT EXISTS vehicle_service;
USE vehicle_service;
 
-- 1. Customers -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    name     VARCHAR(100) NOT NULL,
    phone    VARCHAR(20)  NOT NULL,
    email    VARCHAR(100),
    address  VARCHAR(255)
);
 
-- 2. Vehicles (each vehicle belongs to one customer) -----------------------
CREATE TABLE IF NOT EXISTS vehicles (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    customer_id    INT NOT NULL,
    vehicle_number VARCHAR(20) NOT NULL UNIQUE,
    model          VARCHAR(50),
    vehicle_type   VARCHAR(30),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);
 
-- 3. Services (each service belongs to one vehicle) ------------------------
CREATE TABLE IF NOT EXISTS services (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id   INT NOT NULL,
    service_type VARCHAR(100) NOT NULL,
    service_date DATE NOT NULL,
    cost         DECIMAL(10,2) DEFAULT 0.00,
    status       ENUM('Pending','In Progress','Completed') DEFAULT 'Pending',
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
);
 
-- Sample data so the dashboard is not empty -------------------------------
INSERT INTO customers (name, phone, email, address) VALUES
('Ravi Kumar',  '9876543210', 'ravi@example.com',  'MG Road, Bengaluru'),
('Sneha Patil', '9123456780', 'sneha@example.com', 'FC Road, Pune');
 
INSERT INTO vehicles (customer_id, vehicle_number, model, vehicle_type) VALUES
(1, 'KA01AB1234', 'Maruti Swift', 'Car'),
(2, 'MH12XY5678', 'Honda Activa', 'Bike');
 
INSERT INTO services (vehicle_id, service_type, service_date, cost, status) VALUES
(1, 'Oil Change',     '2026-09-01', 1200.00, 'Completed'),
(1, 'Brake Repair',   '2026-09-10', 2500.00, 'In Progress'),
(2, 'General Service','2026-09-14',  800.00, 'Pending');
 
