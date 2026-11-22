"""
Realistic, comprehensive structured mock data for Library Management System
and generic software requirement projects.
Ensures the application operates 100% offline with full fidelity.
"""

LIBRARY_REQUIREMENTS = {
    "functional": [
        {
            "req_id": "FR-001",
            "category": "functional",
            "title": "Catalog Search & Discovery",
            "description": "The system shall allow patrons to search for books by Title, Author, ISBN, Subject Category, and Availability Status.",
            "priority": "high",
            "module_name": "Catalog & Book Management",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-002",
            "category": "functional",
            "title": "Real-time Availability Status",
            "description": "The system shall support real-time availability checking showing total copies, copies currently borrowed, and shelf location.",
            "priority": "high",
            "module_name": "Catalog & Book Management",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-003",
            "category": "functional",
            "title": "Book Cataloging",
            "description": "Administrators shall be able to add new book titles with metadata (ISBN, Title, Author, Publisher, Edition, Publication Year, Copies).",
            "priority": "high",
            "module_name": "Catalog & Book Management",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-004",
            "category": "functional",
            "title": "Inventory Lifecycle Management",
            "description": "Administrators shall be able to update, categorize, or decommission lost/damaged book copies.",
            "priority": "medium",
            "module_name": "Catalog & Book Management",
            "is_ambiguous": True,
            "ambiguity_notes": "Decommissioning policy for damaged books and replacement fee calculation are not specified.",
            "clarifying_questions": ["Should patrons be charged replacement costs upon decommissioning damaged books?", "Is an audit log required for decommissioned books?"]
        },
        {
            "req_id": "FR-005",
            "category": "functional",
            "title": "Patron Authentication",
            "description": "Students must authenticate using their University ID and secure password with JWT Bearer token authentication.",
            "priority": "high",
            "module_name": "Patron Management & Authentication",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-006",
            "category": "functional",
            "title": "Student Profile Management",
            "description": "The system shall maintain student profiles including Department, Contact Email, Student ID, and Current Borrowing Status.",
            "priority": "medium",
            "module_name": "Patron Management & Authentication",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-007",
            "category": "functional",
            "title": "Borrowing Duration Limit",
            "description": "A patron may borrow a book for a maximum duration of 14 calendar days.",
            "priority": "high",
            "module_name": "Borrowing & Return Circulation",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-008",
            "category": "functional",
            "title": "Concurrency Borrowing Cap",
            "description": "A patron cannot borrow more than 3 books at any given time.",
            "priority": "high",
            "module_name": "Borrowing & Return Circulation",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-009",
            "category": "functional",
            "title": "Overdue Borrowing Freeze",
            "description": "Patrons with unpaid fines exceeding $10.00 shall be blocked from borrowing or reserving additional books.",
            "priority": "high",
            "module_name": "Borrowing & Return Circulation",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-010",
            "category": "functional",
            "title": "Book Check-in & Fine Calculation",
            "description": "When a book is returned, the system shall record the return date and compute any applicable overdue penalties.",
            "priority": "high",
            "module_name": "Borrowing & Return Circulation",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-011",
            "category": "functional",
            "title": "Circulation Loan Renewal",
            "description": "Patrons may renew an active loan once for an additional 7 days if no reservation exists from another patron.",
            "priority": "medium",
            "module_name": "Borrowing & Return Circulation",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-012",
            "category": "functional",
            "title": "Overdue Penalty Rate",
            "description": "Overdue loans shall incur a penalty of $1.00 per day after the due date.",
            "priority": "high",
            "module_name": "Fines & Penalty Management",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-013",
            "category": "functional",
            "title": "Fine Settlement & Receipts",
            "description": "Administrators shall be able to record fine payments and issue digital payment receipts.",
            "priority": "medium",
            "module_name": "Fines & Penalty Management",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-014",
            "category": "functional",
            "title": "Hold & Reservation Queue",
            "description": "If all copies of a book are currently borrowed, a patron may place a reservation request.",
            "priority": "medium",
            "module_name": "Reservation & Queueing",
            "is_ambiguous": False,
            "clarifying_questions": []
        },
        {
            "req_id": "FR-015",
            "category": "functional",
            "title": "Reservation Pickup Window",
            "description": "When a reserved book is returned, the system shall notify the patron at the top of the queue and hold the book for 48 hours.",
            "priority": "medium",
            "module_name": "Reservation & Queueing",
            "is_ambiguous": True,
            "ambiguity_notes": "Behavior when patron fails to collect within 48 hours is not detailed.",
            "clarifying_questions": ["Does the book automatically advance to the next queued patron after 48 hours?"]
        }
    ],
    "non_functional": [
        {
            "req_id": "NFR-001",
            "category": "non_functional",
            "title": "Search Latency SLA",
            "description": "Book search query responses shall be returned within 500 milliseconds under a concurrent load of 500 users.",
            "priority": "high",
            "module_name": "Performance",
            "is_ambiguous": False
        },
        {
            "req_id": "NFR-002",
            "category": "non_functional",
            "title": "Credential Hashing & Encryption",
            "description": "All patron passwords must be hashed using bcrypt with salt rounds >= 12. Sensitive endpoints require TLS 1.3 encryption.",
            "priority": "high",
            "module_name": "Security",
            "is_ambiguous": False
        },
        {
            "req_id": "NFR-003",
            "category": "non_functional",
            "title": "System High Availability",
            "description": "The system shall maintain 99.9% uptime during university operating semesters.",
            "priority": "medium",
            "module_name": "Availability",
            "is_ambiguous": False
        },
        {
            "req_id": "NFR-004",
            "category": "non_functional",
            "title": "ACID Transactional Consistency",
            "description": "Database transactions for borrowing and returns must strictly adhere to ACID properties to prevent double-checkout race conditions.",
            "priority": "high",
            "module_name": "Data Integrity",
            "is_ambiguous": False
        },
        {
            "req_id": "NFR-005",
            "category": "non_functional",
            "title": "Catalog & User Scalability",
            "description": "The architecture shall support a catalog of at least 100,000 book titles and 20,000 active students.",
            "priority": "medium",
            "module_name": "Scalability",
            "is_ambiguous": False
        }
    ],
    "actors": [
        {"req_id": "ACT-001", "category": "actor", "title": "Student / Patron", "description": "University student borrowing and reserving library materials."},
        {"req_id": "ACT-002", "category": "actor", "title": "Librarian / Staff Admin", "description": "Library staff managing inventory, fine payments, and circulation desks."},
        {"req_id": "ACT-003", "category": "actor", "title": "System Scheduler", "description": "Automated daemon processing daily fines and loan due date notifications."}
    ],
    "entities": [
        {"req_id": "ENT-001", "category": "entity", "title": "Book", "description": "Core catalog item containing ISBN, title, author, and available copies."},
        {"req_id": "ENT-002", "category": "entity", "title": "Student", "description": "Registered library patron with profile, email, and fine balance."},
        {"req_id": "ENT-003", "category": "entity", "title": "Borrowing", "description": "Circulation transaction linking student, book copy, due dates, and return status."},
        {"req_id": "ENT-004", "category": "entity", "title": "Reservation", "description": "Hold queue record for high-demand loaned books."},
        {"req_id": "ENT-005", "category": "entity", "title": "Fine", "description": "Monetary penalty issued for overdue returns."}
    ],
    "modules": [
        {"req_id": "MOD-001", "category": "module", "title": "Catalog & Book Management", "description": "Book cataloging, metadata search, and stock tracking."},
        {"req_id": "MOD-002", "category": "module", "title": "Patron Management & Authentication", "description": "JWT authentication, user roles, and student profile registry."},
        {"req_id": "MOD-003", "category": "module", "title": "Borrowing & Return Circulation", "description": "Checkout transactions, loan duration tracking, and return processing."},
        {"req_id": "MOD-004", "category": "module", "title": "Fines & Penalty Management", "description": "Overdue fine assessment, payment recording, and balance thresholding."},
        {"req_id": "MOD-005", "category": "module", "title": "Reservation & Queueing", "description": "Waiting list management and pickup window notifications."}
    ],
    "constraints": [
        {"req_id": "CON-001", "category": "constraint", "title": "Backend Tech Stack", "description": "Backend implementation must use Python FastAPI with SQLAlchemy ORM."},
        {"req_id": "CON-002", "category": "constraint", "title": "Web Standards", "description": "Frontend must adhere to responsive modern web standards with dark-mode aesthetic."}
    ]
}

LIBRARY_SRS = {
    "title": "Software Requirements Specification (SRS) for Intelligent Library Management System",
    "version": "1.0",
    "disclaimer": "AI-generated artifacts are suggestions and should be reviewed and edited by the developer.",
    "sections": [
        {
            "id": "1.0",
            "title": "1. Introduction",
            "content": "This document specifies the software requirements for the Intelligent Library Management System (ILMS). The system automates university library workflows including search, checkout, renewal, overdue fine tracking, and reservation queues."
        },
        {
            "id": "2.0",
            "title": "2. Overall Description & Product Perspective",
            "content": "ILMS operates as a decoupled client-server web application. The frontend communicates with a high-performance RESTful FastAPI backend. The persistence layer maintains ACID-compliant relational tables for inventory, patrons, and loan circulation."
        },
        {
            "id": "3.0",
            "title": "3. User Classes and Characteristics",
            "content": "The application accommodates two primary user classes: Students (Patrons) who search the catalog, borrow books, renew loans, and track fines; and Librarians (Administrators) who manage inventory, process physical check-ins, record payments, and enforce policies."
        },
        {
            "id": "4.0",
            "title": "4. Operating Environment",
            "content": "The backend runs inside containerized Linux/Windows runtimes with Python 3.11+, SQLite/PostgreSQL, and Uvicorn ASGI. The frontend is delivered via modern evergreen web browsers (Chrome, Firefox, Safari, Edge)."
        },
        {
            "id": "5.0",
            "title": "5. Functional Requirements",
            "content": "Detailed functional requirements include 15 verified specifications covering Catalog Search (FR-001), Real-time Availability (FR-002), Admin Cataloging (FR-003), JWT Authentication (FR-005), 14-day Loans (FR-007), 3-book Concurrency Limits (FR-008), $10 Fine Cap (FR-009), Return Processing (FR-010), Loan Renewals (FR-011), Overdue Fines at $1.00/day (FR-012), and Hold Queuing (FR-014)."
        },
        {
            "id": "6.0",
            "title": "6. Non-Functional Requirements",
            "content": "Performance SLAs mandate sub-500ms search latency under 500 concurrent users. Security requires bcrypt credential hashing and JWT session tokens. Availability targets 99.9% uptime with strict ACID transaction isolation to prevent race conditions during book checkout."
        },
        {
            "id": "7.0",
            "title": "7. External Interface Requirements",
            "content": "The REST API exposes JSON-based OpenAPI 3.0 endpoints. Authentication utilizes RFC 7519 JWT Bearer tokens passed via standard HTTP Authorization headers."
        },
        {
            "id": "8.0",
            "title": "8. System Features and Verification Criteria",
            "content": "Every functional requirement maps directly to automated unit and integration tests. Test cases verify edge scenarios including borrowing cap enforcement, fine threshold blocks, and race condition resilience."
        }
    ]
}

LIBRARY_ARCHITECTURE = {
    "title": "System Architecture & Layered Design",
    "disclaimer": "AI-generated artifacts are suggestions and should be reviewed and edited by the developer.",
    "layers_count": 5,
    "pattern": "Layered Microservices / Modular Monolith",
    "layers": [
        {"name": "Presentation Layer", "tech": "React 18 + Vite + Tailwind CSS", "responsibility": "Single-page responsive user interface, state management, interactive dashboards."},
        {"name": "API Gateway / Routing Layer", "tech": "FastAPI + Uvicorn + Pydantic v2", "responsibility": "HTTP request handling, CORS enforcement, JWT validation, and schema serialization."},
        {"name": "Service / Business Logic Layer", "tech": "Python Services", "responsibility": "Core circulation logic, fine assessment, borrowing caps, reservation queues, and concurrency control."},
        {"name": "Data Access Layer (ORM)", "tech": "SQLAlchemy 2.0 ORM", "responsibility": "Declarative relational modeling, unit of work transactions, migration management."},
        {"name": "Persistence & Cache Layer", "tech": "SQLite / PostgreSQL + ChromaDB", "responsibility": "ACID relational persistence for transactional entities and vector collection for RAG semantic search."}
    ],
    "mermaid_diagram": """graph TD
    subgraph Client["Presentation Layer"]
        UI["React Web UI (Tailwind CSS)"]
    end

    subgraph API["API Gateway & Routing Layer"]
        Router["FastAPI Router & JWT Middleware"]
    end

    subgraph Business["Service Layer"]
        AuthSvc["Auth Service"]
        CatalogSvc["Catalog Service"]
        CirculationSvc["Circulation & Loan Service"]
        FineSvc["Fine & Billing Service"]
        QueueSvc["Reservation Queue Service"]
    end

    subgraph DataAccess["Data Access Layer"]
        ORM["SQLAlchemy 2.0 ORM"]
    end

    subgraph Storage["Persistence Layer"]
        DB[("Relational DB (SQLite/PostgreSQL)")]
        VectorStore[("ChromaDB Vector Store")]
    end

    UI -->|REST / HTTPS| Router
    Router --> AuthSvc
    Router --> CatalogSvc
    Router --> CirculationSvc
    Router --> FineSvc
    Router --> QueueSvc
    AuthSvc --> ORM
    CatalogSvc --> ORM
    CirculationSvc --> ORM
    FineSvc --> ORM
    QueueSvc --> ORM
    CatalogSvc --> VectorStore
    ORM --> DB""",
    "justification": "The layered architecture isolates presentation from business workflows and database access. This ensures that circulation rules (borrowing caps, fine freeze limits) are centrally verified in the Service Layer without leaking into UI or persistence tiers."
}

LIBRARY_SCHEMA = {
    "title": "Relational Database Schema & Entity Relationships",
    "disclaimer": "AI-generated artifacts are suggestions and should be reviewed and edited by the developer.",
    "tables_count": 5,
    "tables": [
        {
            "name": "books",
            "description": "Library book catalog inventory",
            "columns": [
                {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": "Primary key UUID"},
                {"name": "isbn", "type": "VARCHAR(20)", "pk": False, "fk": None, "nullable": False, "description": "Unique ISBN-13 identifier"},
                {"name": "title", "type": "VARCHAR(255)", "pk": False, "fk": None, "nullable": False, "description": "Book title"},
                {"name": "author", "type": "VARCHAR(255)", "pk": False, "fk": None, "nullable": False, "description": "Author name"},
                {"name": "publisher", "type": "VARCHAR(150)", "pk": False, "fk": None, "nullable": True, "description": "Publishing house"},
                {"name": "publication_year", "type": "INTEGER", "pk": False, "fk": None, "nullable": True, "description": "Year published"},
                {"name": "category", "type": "VARCHAR(100)", "pk": False, "fk": None, "nullable": False, "description": "Genre / subject category"},
                {"name": "total_copies", "type": "INTEGER", "pk": False, "fk": None, "nullable": False, "description": "Total physical copies owned"},
                {"name": "available_copies", "type": "INTEGER", "pk": False, "fk": None, "nullable": False, "description": "Copies currently on shelf"},
                {"name": "created_at", "type": "DATETIME", "pk": False, "fk": None, "nullable": False, "description": "Record creation timestamp"}
            ]
        },
        {
            "name": "students",
            "description": "Student patrons registered in the system",
            "columns": [
                {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": "Primary key UUID"},
                {"name": "student_id", "type": "VARCHAR(50)", "pk": False, "fk": None, "nullable": False, "description": "University Student ID (unique)"},
                {"name": "full_name", "type": "VARCHAR(150)", "pk": False, "fk": None, "nullable": False, "description": "Student full legal name"},
                {"name": "email", "type": "VARCHAR(255)", "pk": False, "fk": None, "nullable": False, "description": "University email address (unique)"},
                {"name": "hashed_password", "type": "VARCHAR(255)", "pk": False, "fk": None, "nullable": False, "description": "Bcrypt salted password hash"},
                {"name": "department", "type": "VARCHAR(100)", "pk": False, "fk": None, "nullable": False, "description": "Academic major / department"},
                {"name": "fine_balance", "type": "DECIMAL(10,2)", "pk": False, "fk": None, "nullable": False, "description": "Accumulated unpaid fine total"},
                {"name": "is_active", "type": "BOOLEAN", "pk": False, "fk": None, "nullable": False, "description": "Account active flag"},
                {"name": "created_at", "type": "DATETIME", "pk": False, "fk": None, "nullable": False, "description": "Account created timestamp"}
            ]
        },
        {
            "name": "borrowings",
            "description": "Circulation loan transactions",
            "columns": [
                {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": "Primary key UUID"},
                {"name": "student_id", "type": "VARCHAR(36)", "pk": False, "fk": "students.id", "nullable": False, "description": "Borrowing student FK"},
                {"name": "book_id", "type": "VARCHAR(36)", "pk": False, "fk": "books.id", "nullable": False, "description": "Borrowed book FK"},
                {"name": "borrowed_at", "type": "DATETIME", "pk": False, "fk": None, "nullable": False, "description": "Checkout timestamp"},
                {"name": "due_date", "type": "DATETIME", "pk": False, "fk": None, "nullable": False, "description": "Mandatory due date (14 days)"},
                {"name": "returned_at", "type": "DATETIME", "pk": False, "fk": None, "nullable": True, "description": "Actual check-in timestamp"},
                {"name": "status", "type": "VARCHAR(20)", "pk": False, "fk": None, "nullable": False, "description": "active | returned | overdue"}
            ]
        },
        {
            "name": "reservations",
            "description": "Book hold queue for checked-out materials",
            "columns": [
                {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": "Primary key UUID"},
                {"name": "student_id", "type": "VARCHAR(36)", "pk": False, "fk": "students.id", "nullable": False, "description": "Reserving patron FK"},
                {"name": "book_id", "type": "VARCHAR(36)", "pk": False, "fk": "books.id", "nullable": False, "description": "Reserved book FK"},
                {"name": "reserved_at", "type": "DATETIME", "pk": False, "fk": None, "nullable": False, "description": "Reservation placed timestamp"},
                {"name": "expires_at", "type": "DATETIME", "pk": False, "fk": None, "nullable": True, "description": "48hr pickup expiry timestamp"},
                {"name": "status", "type": "VARCHAR(20)", "pk": False, "fk": None, "nullable": False, "description": "pending | fulfilled | expired"}
            ]
        },
        {
            "name": "fines",
            "description": "Overdue monetary penalties and payment status",
            "columns": [
                {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": "Primary key UUID"},
                {"name": "borrowing_id", "type": "VARCHAR(36)", "pk": False, "fk": "borrowings.id", "nullable": False, "description": "Related loan FK"},
                {"name": "student_id", "type": "VARCHAR(36)", "pk": False, "fk": "students.id", "nullable": False, "description": "Debtor student FK"},
                {"name": "amount", "type": "DECIMAL(10,2)", "pk": False, "fk": None, "nullable": False, "description": "Fine amount ($1.00/day)"},
                {"name": "status", "type": "VARCHAR(20)", "pk": False, "fk": None, "nullable": False, "description": "unpaid | paid"},
                {"name": "paid_at", "type": "DATETIME", "pk": False, "fk": None, "nullable": True, "description": "Payment receipt timestamp"}
            ]
        }
    ],
    "mermaid_er": """erDiagram
    STUDENT ||--o{ BORROWING : "places"
    BOOK ||--o{ BORROWING : "loaned_in"
    STUDENT ||--o{ RESERVATION : "reserves"
    BOOK ||--o{ RESERVATION : "reserved_by"
    BORROWING ||--o| FINE : "incurs"
    STUDENT ||--o{ FINE : "owes"

    STUDENT {
        string id PK
        string student_id UK
        string email UK
        string full_name
        decimal fine_balance
    }

    BOOK {
        string id PK
        string isbn UK
        string title
        int total_copies
        int available_copies
    }

    BORROWING {
        string id PK
        string student_id FK
        string book_id FK
        datetime borrowed_at
        datetime due_date
        datetime returned_at
        string status
    }

    RESERVATION {
        string id PK
        string student_id FK
        string book_id FK
        datetime reserved_at
        datetime expires_at
        string status
    }

    FINE {
        string id PK
        string borrowing_id FK
        string student_id FK
        decimal amount
        string status
    }""",
    "sql_ddl": """-- Generated DDL for Intelligent Library Management System
CREATE TABLE books (
    id VARCHAR(36) PRIMARY KEY,
    isbn VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    publisher VARCHAR(150),
    publication_year INT,
    category VARCHAR(100) NOT NULL,
    total_copies INT NOT NULL DEFAULT 1,
    available_copies INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE students (
    id VARCHAR(36) PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    fine_balance DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE borrowings (
    id VARCHAR(36) PRIMARY KEY,
    student_id VARCHAR(36) NOT NULL,
    book_id VARCHAR(36) NOT NULL,
    borrowed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP NOT NULL,
    returned_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE RESTRICT
);

CREATE TABLE reservations (
    id VARCHAR(36) PRIMARY KEY,
    student_id VARCHAR(36) NOT NULL,
    book_id VARCHAR(36) NOT NULL,
    reserved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE fines (
    id VARCHAR(36) PRIMARY KEY,
    borrowing_id VARCHAR(36) NOT NULL,
    student_id VARCHAR(36) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'unpaid',
    paid_at TIMESTAMP,
    FOREIGN KEY (borrowing_id) REFERENCES borrowings(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);"""
}

LIBRARY_APIS = {
    "title": "OpenAPI Specification & REST Endpoints",
    "disclaimer": "AI-generated artifacts are suggestions and should be reviewed and edited by the developer.",
    "endpoints_count": 8,
    "endpoints": [
        {
            "method": "POST",
            "path": "/api/v1/auth/token",
            "tag": "Authentication",
            "summary": "Authenticate student patron or staff librarian",
            "auth_required": False,
            "parameters": [],
            "request_body": {"username": "student@university.edu", "password": "securePassword123"},
            "responses": [
                {"code": 200, "description": "Authentication successful", "example": {"access_token": "jwt_token_here", "token_type": "bearer"}},
                {"code": 401, "description": "Invalid credentials", "example": {"detail": "Incorrect email or password"}}
            ]
        },
        {
            "method": "GET",
            "path": "/api/v1/books",
            "tag": "Catalog",
            "summary": "Search book catalog by query, category, or availability",
            "auth_required": False,
            "parameters": [
                {"name": "q", "in": "query", "type": "string", "required": False, "description": "Search keyword for title, author, or ISBN"},
                {"name": "category", "in": "query", "type": "string", "required": False, "description": "Filter by genre/category"},
                {"name": "available_only", "in": "query", "type": "boolean", "required": False, "description": "Filter for in-stock books"}
            ],
            "request_body": None,
            "responses": [
                {"code": 200, "description": "List of matching catalog books", "example": [{"id": "uuid", "title": "Operating Systems", "author": "Silberschatz", "available_copies": 4}]}
            ]
        },
        {
            "method": "POST",
            "path": "/api/v1/books",
            "tag": "Catalog",
            "summary": "Catalog a new book (Admin only)",
            "auth_required": True,
            "parameters": [],
            "request_body": {"isbn": "978-0131103627", "title": "The C Programming Language", "author": "Kernighan & Ritchie", "category": "Computer Science", "total_copies": 5},
            "responses": [
                {"code": 201, "description": "Book cataloged successfully", "example": {"id": "uuid", "isbn": "978-0131103627", "title": "The C Programming Language"}},
                {"code": 403, "description": "Forbidden - requires admin privilege", "example": {"detail": "Insufficient permissions"}}
            ]
        },
        {
            "method": "POST",
            "path": "/api/v1/borrowings/checkout",
            "tag": "Circulation",
            "summary": "Checkout a book copy for a student",
            "auth_required": True,
            "parameters": [],
            "request_body": {"student_id": "STU-1002", "book_id": "book-uuid-1"},
            "responses": [
                {"code": 201, "description": "Checkout completed", "example": {"borrowing_id": "uuid", "due_date": "2026-11-10T19:00:00Z", "status": "active"}},
                {"code": 400, "description": "Borrowing limits or fine block triggered", "example": {"detail": "Maximum borrowing limit (3 books) reached or unpaid fines exceed $10.00"}}
            ]
        },
        {
            "method": "POST",
            "path": "/api/v1/borrowings/{id}/return",
            "tag": "Circulation",
            "summary": "Check-in a returned book and assess overdue fines",
            "auth_required": True,
            "parameters": [{"name": "id", "in": "path", "type": "string", "required": True, "description": "Borrowing transaction ID"}],
            "request_body": None,
            "responses": [
                {"code": 200, "description": "Book returned successfully", "example": {"borrowing_id": "uuid", "returned_at": "2026-10-27T19:00:00Z", "fine_assessed": 0.00}},
                {"code": 404, "description": "Borrowing record not found", "example": {"detail": "Borrowing record not found"}}
            ]
        },
        {
            "method": "POST",
            "path": "/api/v1/borrowings/{id}/renew",
            "tag": "Circulation",
            "summary": "Renew an active loan for an additional 7 days",
            "auth_required": True,
            "parameters": [{"name": "id", "in": "path", "type": "string", "required": True, "description": "Borrowing transaction ID"}],
            "request_body": None,
            "responses": [
                {"code": 200, "description": "Loan extended by 7 days", "example": {"borrowing_id": "uuid", "new_due_date": "2026-11-17T19:00:00Z"}},
                {"code": 400, "description": "Renewal disallowed due to pending hold", "example": {"detail": "Cannot renew: this item is reserved by another patron"}}
            ]
        },
        {
            "method": "POST",
            "path": "/api/v1/reservations",
            "tag": "Reservations",
            "summary": "Place a reservation hold on a borrowed book",
            "auth_required": True,
            "parameters": [],
            "request_body": {"book_id": "book-uuid-1"},
            "responses": [
                {"code": 201, "description": "Hold reservation queued", "example": {"reservation_id": "uuid", "queue_position": 1, "status": "pending"}}
            ]
        },
        {
            "method": "POST",
            "path": "/api/v1/fines/{id}/pay",
            "tag": "Billing",
            "summary": "Record fine settlement and issue payment confirmation",
            "auth_required": True,
            "parameters": [{"name": "id", "in": "path", "type": "string", "required": True, "description": "Fine ID"}],
            "request_body": {"amount": 5.00, "payment_method": "Credit Card"},
            "responses": [
                {"code": 200, "description": "Fine settled successfully", "example": {"fine_id": "uuid", "status": "paid", "remaining_balance": 0.00}}
            ]
        }
    ]
}

LIBRARY_TEST_CASES = {
    "title": "Requirements-Driven Verification & Test Cases",
    "disclaimer": "AI-generated artifacts are suggestions and should be reviewed and edited by the developer.",
    "cases_count": 7,
    "cases": [
        {
            "test_id": "TC-001",
            "linked_req_id": "FR-001",
            "scenario": "Verify patron can search books by keyword with partial matching",
            "preconditions": "Catalog contains 'Operating System Concepts' by Silberschatz.",
            "steps": "1. Send GET /api/v1/books?q=operating\n2. Inspect response HTTP status and body.",
            "expected_result": "HTTP 200 returned with matching book record in list.",
            "type": "positive"
        },
        {
            "test_id": "TC-002",
            "linked_req_id": "FR-008",
            "scenario": "Verify patron borrowing cap blocks 4th concurrent loan",
            "preconditions": "Student STU-101 has 3 currently active, unreturned borrowings.",
            "steps": "1. Attempt POST /api/v1/borrowings/checkout for student STU-101 with available book.\n2. Observe response status code.",
            "expected_result": "HTTP 400 Bad Request returned with error indicating 3-book limit reached.",
            "type": "boundary"
        },
        {
            "test_id": "TC-003",
            "linked_req_id": "FR-009",
            "scenario": "Verify borrowing blocked when patron unpaid fines exceed $10.00",
            "preconditions": "Student STU-102 has an outstanding fine balance of $12.00.",
            "steps": "1. Send POST /api/v1/borrowings/checkout for STU-102.",
            "expected_result": "HTTP 400 Bad Request indicating account frozen due to unpaid fines.",
            "type": "negative"
        },
        {
            "test_id": "TC-004",
            "linked_req_id": "FR-010",
            "scenario": "Verify fine of $1.00/day calculated upon overdue check-in",
            "preconditions": "Borrowing loan due date was 5 days prior to today.",
            "steps": "1. Execute POST /api/v1/borrowings/{id}/return.\n2. Verify fine entity and student fine balance.",
            "expected_result": "HTTP 200 returned with fine assessed equal to exactly $5.00 ($1.00 x 5 days).",
            "type": "positive"
        },
        {
            "test_id": "TC-005",
            "linked_req_id": "FR-011",
            "scenario": "Verify renewal rejected when another patron holds active reservation",
            "preconditions": "Book has an active pending reservation in queue.",
            "steps": "1. Send POST /api/v1/borrowings/{id}/renew for current borrower.",
            "expected_result": "HTTP 400 Bad Request returned; loan due date is not extended.",
            "type": "negative"
        },
        {
            "test_id": "TC-006",
            "linked_req_id": "NFR-001",
            "scenario": "Verify catalog search query latency under 500ms",
            "preconditions": "Database populated with 10,000 book records.",
            "steps": "1. Measure roundtrip response time of GET /api/v1/books?q=science across 50 iterations.",
            "expected_result": "95th percentile response time is strictly below 500ms.",
            "type": "positive"
        },
        {
            "test_id": "TC-007",
            "linked_req_id": "FR-005",
            "scenario": "Verify authentication fails with invalid student password",
            "preconditions": "Student STU-103 exists with password 'correctPass'.",
            "steps": "1. Send POST /api/v1/auth/token with incorrect password 'wrongPass'.",
            "expected_result": "HTTP 401 Unauthorized returned with invalid credentials message.",
            "type": "negative"
        }
    ]
}

LIBRARY_SKELETON_FILES = {
    "files_count": 8,
    "files": [
        {
            "path": "README.md",
            "language": "markdown",
            "content": """# Intelligent Library Management System - Backend API Starter

Generated by **Req-to-Code AI Assistant**.

## Quick Start
1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
4. Access interactive API documentation at: `http://localhost:8000/docs`
"""
        },
        {
            "path": "requirements.txt",
            "language": "text",
            "content": """fastapi>=0.110.0
uvicorn[standard]>=0.28.0
pydantic>=2.6.0
sqlalchemy>=2.0.28
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.9
"""
        },
        {
            "path": ".env.example",
            "language": "text",
            "content": """DATABASE_URL=sqlite:///./library.db
SECRET_KEY=supersecretjwtkey_replace_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
"""
        },
        {
            "path": "database/session.py",
            "language": "python",
            "content": """from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./library.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""
        },
        {
            "path": "models/entities.py",
            "language": "python",
            "content": """from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database.session import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(String(36), primary_key=True)
    isbn = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    publisher = Column(String(150), nullable=True)
    publication_year = Column(Integer, nullable=True)
    category = Column(String(100), nullable=False)
    total_copies = Column(Integer, default=1)
    available_copies = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class Student(Base):
    __tablename__ = "students"

    id = Column(String(36), primary_key=True)
    student_id = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False)
    fine_balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Borrowing(Base):
    __tablename__ = "borrowings"

    id = Column(String(36), primary_key=True)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False)
    book_id = Column(String(36), ForeignKey("books.id"), nullable=False)
    borrowed_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=False)
    returned_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="active")
"""
        },
        {
            "path": "schemas/book.py",
            "language": "python",
            "content": """from typing import Optional
from pydantic import BaseModel, ConfigDict

class BookBase(BaseModel):
    isbn: str
    title: str
    author: str
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    category: str
    total_copies: int = 1

class BookCreate(BookBase):
    pass

class BookResponse(BookBase):
    id: str
    available_copies: int

    model_config = ConfigDict(from_attributes=True)
"""
        },
        {
            "path": "routes/books.py",
            "language": "python",
            "content": """import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.session import get_db
from models.entities import Book
from schemas.book import BookCreate, BookResponse

router = APIRouter(prefix="/books", tags=["Books"])

@router.get("", response_model=List[BookResponse])
def search_books(q: Optional[str] = None, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Book)
    if q:
        search_filter = f"%{q}%"
        query = query.filter((Book.title.ilike(search_filter)) | (Book.author.ilike(search_filter)) | (Book.isbn.ilike(search_filter)))
    if category:
        query = query.filter(Book.category == category)
    return query.all()

@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    book = Book(
        id=str(uuid.uuid4()),
        **book_in.model_dump(),
        available_copies=book_in.total_copies
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book
"""
        },
        {
            "path": "main.py",
            "language": "python",
            "content": """from fastapi import FastAPI
from database.session import Base, engine
from routes.books import router as books_router

# Initialize tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Intelligent Library Management System API",
    description="Starter backend generated by Req-to-Code AI Assistant",
    version="1.0.0"
)

app.include_router(books_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "online", "docs": "/docs"}
"""
        }
    ]
}

LIBRARY_GRAPH = {
    "nodes": [
        {"id": "FR-001", "label": "Catalog Search", "type": "Requirement", "category": "functional"},
        {"id": "FR-007", "label": "14-day Duration", "type": "Requirement", "category": "functional"},
        {"id": "FR-008", "label": "3-Book Concurrency Limit", "type": "Requirement", "category": "functional"},
        {"id": "FR-009", "label": "Overdue Fine Freeze", "type": "Requirement", "category": "functional"},
        {"id": "FR-010", "label": "Return Processing & Fine Calc", "type": "Requirement", "category": "functional"},
        {"id": "ACT-001", "label": "Student Patron", "type": "Actor", "category": "actor"},
        {"id": "ACT-002", "label": "Librarian Admin", "type": "Actor", "category": "actor"},
        {"id": "MOD-001", "label": "Catalog Management", "type": "Module", "category": "module"},
        {"id": "MOD-003", "label": "Circulation Management", "type": "Module", "category": "module"},
        {"id": "API-002", "label": "GET /api/v1/books", "type": "API", "category": "api"},
        {"id": "API-004", "label": "POST /api/v1/borrowings/checkout", "type": "API", "category": "api"},
        {"id": "API-005", "label": "POST /api/v1/borrowings/{id}/return", "type": "API", "category": "api"},
        {"id": "ENT-001", "label": "Book", "type": "Database Entity", "category": "entity"},
        {"id": "ENT-002", "label": "Student", "type": "Database Entity", "category": "entity"},
        {"id": "ENT-003", "label": "Borrowing", "type": "Database Entity", "category": "entity"},
        {"id": "ENT-005", "label": "Fine", "type": "Database Entity", "category": "entity"},
        {"id": "TC-001", "label": "TC-001 Search Verification", "type": "Test Case", "category": "testcase"},
        {"id": "TC-002", "label": "TC-002 Concurrency Limit Test", "type": "Test Case", "category": "testcase"},
        {"id": "TC-003", "label": "TC-003 Fine Freeze Boundary Test", "type": "Test Case", "category": "testcase"},
        {"id": "TC-004", "label": "TC-004 Overdue Fine Calculation", "type": "Test Case", "category": "testcase"}
    ],
    "edges": [
        {"id": "e1", "source": "ACT-001", "target": "FR-001", "label": "uses"},
        {"id": "e2", "source": "FR-001", "target": "MOD-001", "label": "belongs_to"},
        {"id": "e3", "source": "MOD-001", "target": "API-002", "label": "exposes"},
        {"id": "e4", "source": "API-002", "target": "ENT-001", "label": "uses_entity"},
        {"id": "e5", "source": "TC-001", "target": "FR-001", "label": "verified_by"},
        {"id": "e6", "source": "ACT-001", "target": "FR-008", "label": "uses"},
        {"id": "e7", "source": "FR-008", "target": "MOD-003", "label": "belongs_to"},
        {"id": "e8", "source": "MOD-003", "target": "API-004", "label": "exposes"},
        {"id": "e9", "source": "API-004", "target": "ENT-003", "label": "uses_entity"},
        {"id": "e10", "source": "TC-002", "target": "FR-008", "label": "verified_by"},
        {"id": "e11", "source": "FR-009", "target": "MOD-003", "label": "belongs_to"},
        {"id": "e12", "source": "TC-003", "target": "FR-009", "label": "verified_by"},
        {"id": "e13", "source": "FR-010", "target": "MOD-003", "label": "belongs_to"},
        {"id": "e14", "source": "MOD-003", "target": "API-005", "label": "exposes"},
        {"id": "e15", "source": "API-005", "target": "ENT-005", "label": "uses_entity"},
        {"id": "e16", "source": "TC-004", "target": "FR-010", "label": "verified_by"}
    ],
    "matrix": [
        {"requirement_id": "FR-001", "requirement_title": "Catalog Search & Discovery", "category": "functional", "module": "Catalog & Book Management", "apis": ["GET /api/v1/books"], "entities": ["Book"], "test_cases": ["TC-001"], "coverage_status": "complete"},
        {"requirement_id": "FR-007", "requirement_title": "Borrowing Duration Limit", "category": "functional", "module": "Borrowing & Return Circulation", "apis": ["POST /api/v1/borrowings/checkout"], "entities": ["Borrowing"], "test_cases": ["TC-002"], "coverage_status": "complete"},
        {"requirement_id": "FR-008", "requirement_title": "Concurrency Borrowing Cap", "category": "functional", "module": "Borrowing & Return Circulation", "apis": ["POST /api/v1/borrowings/checkout"], "entities": ["Borrowing", "Student"], "test_cases": ["TC-002"], "coverage_status": "complete"},
        {"requirement_id": "FR-009", "requirement_title": "Overdue Borrowing Freeze", "category": "functional", "module": "Borrowing & Return Circulation", "apis": ["POST /api/v1/borrowings/checkout"], "entities": ["Borrowing", "Fine", "Student"], "test_cases": ["TC-003"], "coverage_status": "complete"},
        {"requirement_id": "FR-010", "requirement_title": "Book Check-in & Fine Calculation", "category": "functional", "module": "Borrowing & Return Circulation", "apis": ["POST /api/v1/borrowings/{id}/return"], "entities": ["Borrowing", "Fine"], "test_cases": ["TC-004"], "coverage_status": "complete"}
    ]
}
