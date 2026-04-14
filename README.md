# Library Management System:

A command-line library management application build with Python and SQLite.

Developed as a database systems project.

The application simulates real-world library operations including borrowing, returns, fine tracking, event registration, and volunteer management.

## Technical Highlights:

- Relational database design in BCNF with 8 related tables.
- SQLite database with foreign key constraints, triggers, and multi-table joins.
- Python application layer with full CRUD operations.
- Enforced business logic including borrow limits, overdue fine calculation, and account status checks.

## How to Run:

(Requirements: Python 3)

Setup:
1. Clone the repo.
2. Run `python library.py` to create and populate the database.
3. Run `python LibraryApp.py` to launch the application.

If you need to reset the database, delete `library.db` and re-run `python library.py`.

## Features:

- Search the catalogue by title, author, or item type.
- Borrow and return items (2-week loan period, 5 item limit).
- Automatic overdue fine tracking.
- Browse and register for library events.
- Donate items to the library.
- Volunteer registration.
- Librarian help requests.

Developed as part of a course project at SFU.
