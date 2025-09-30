# WMS (Warehouse Management System) Application

## Overview
This Flask-based Warehouse Management System integrates with SAP B1 to provide comprehensive inventory management, transfer operations, barcode generation, and invoice creation functionalities. It aims to streamline warehouse processes and enhance operational efficiency with features like serial number tracking, pick list management, and GRPO (Goods Receipt PO) functionality. The project's ambition is to offer a production-ready, robust solution for warehouse operations.

## User Preferences
I prefer iterative development with clear, modular code. Please ask before making major architectural changes or introducing new external dependencies. I appreciate detailed explanations for complex solutions. Do not make changes to files related to MySQL if PostgreSQL is the active database.

## System Architecture
The application is built with Flask, utilizing HTML templates with Bootstrap for the frontend, prioritizing clear, functional design. PostgreSQL is the primary database, managed by Replit. Authentication is handled via Flask-Login. The system integrates with SAP Business One through a dedicated API. Credentials for SAP B1 and database connections are managed via a JSON file (`C:/tmp/sap_login/credential.json` or `/tmp/sap_login/credential.json`), with environment variables as a fallback. The application is production-ready, configured to run on Gunicorn, and includes file-based logging. Key modules include Inventory Transfer, Serial Item Transfer, Invoice Creation, GRPO, and SO Against Invoice, all designed for robust, atomic operations with idempotent approval processes and background job processing for SAP posting. Performance optimizations, such as bulk lookups for SAP B1, have been implemented for critical operations like Serial Number Transfers.

## External Dependencies
- **SAP Business One API**: For integration with SAP B1 for warehouse operations.
- **PostgreSQL**: Replit-managed database for all application data.
- **Flask**: Python web framework.
- **Gunicorn**: WSGI HTTP Server for Python web applications.
- **Flask-Login**: For user authentication and session management.
- **uv package manager**: For managing Python dependencies.
- **Bootstrap**: Frontend styling and components.