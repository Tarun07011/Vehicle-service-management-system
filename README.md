🚗 Vehicle Service Management System
A simple, easy-to-use web application for managing a vehicle service centre. Built with HTML, CSS, JavaScript, Python Flask and MySQL.

✨ Features
Admin authentication – login and logout, with support for a hashed admin password
Dashboard – totals for customers, vehicles, services, completed / pending / in-progress services, revenue from completed services, and the 5 most recent service records
Customer management – add, view, edit and delete customers
Vehicle management – add, view, edit and delete vehicles, each linked to a customer
Service records – track service type, date, cost and status (Pending / In Progress / Completed)
PDF invoices – download an invoice for any Completed service
PDF exports – export the vehicle list and the service records as PDF
Search and filter – search customers by name or phone, vehicles and services by vehicle number or customer name, and filter services by status
Data safety – a customer with vehicles, or a vehicle with service records, cannot be deleted by accident
Form validation – checked in the browser and again on the server
Responsive layout – clean design with a left sidebar that works on desktop and mobile

🛠 Tech Stack
Layer	Technology
Frontend	HTML5, CSS3, JavaScript (no libraries)
Backend	Python, Flask
Database	MySQL (mysql-connector-python)
PDF	xhtml2pdf


📁 Project Structure
vehicle-service-management/
├── app.py                # Flask application (all routes)
├── database.sql          # Database, tables and sample data
├── database_update.sql   # One-time update: safer foreign keys + cost check
├── requirements.txt      # Python dependencies
├── .env.example          # Sample configuration file
├── templates/            # HTML pages (login, dashboard, customers, vehicles,
│                         #   services, plus invoice.html and list_pdf.html for PDFs)
└── static/
    ├── style.css         # All styling
    └── script.js         # Sidebar toggle, delete confirmation, form validation
