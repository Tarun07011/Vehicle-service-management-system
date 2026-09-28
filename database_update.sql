
USE vehicle_service;

ALTER TABLE vehicles DROP FOREIGN KEY vehicles_ibfk_1;
ALTER TABLE vehicles
    ADD CONSTRAINT fk_vehicle_customer
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT;

ALTER TABLE services DROP FOREIGN KEY services_ibfk_1;
ALTER TABLE services
    ADD CONSTRAINT fk_service_vehicle
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT;

ALTER TABLE services MODIFY cost DECIMAL(10,2) NOT NULL DEFAULT 0.00;

-- Needs MySQL 8.0.16 or newer (older versions accept it but ignore it)
ALTER TABLE services ADD CONSTRAINT chk_service_cost CHECK (cost >= 0);
