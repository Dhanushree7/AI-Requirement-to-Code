import os
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
import fitz

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample_docs"
SAMPLE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

LIBRARY_TEXT = """# SOFTWARE REQUIREMENT SPECIFICATION
# Intelligent Library Management System (ILMS)
# Version 1.0 - Academic Year 2026

## 1. Project Overview & Scope
The Intelligent Library Management System (ILMS) is an enterprise web-based application designed to automate the administrative operations of university libraries, optimize resource allocation, and enhance the patron borrowing experience. The system serves two primary categories of end-users: Students (Patrons) and Library Administrators (Staff).

## 2. User Roles & Actors
- Student / Patron: Can register, search the digital catalog, place reservations, borrow up to 3 books concurrently, renew checkouts, and view pending fines.
- Librarian / Admin: Can catalog new books, update inventory, issue and accept physical book returns, calculate fines for overdue returns, and generate circulation reports.
- System Scheduler: An automated background service that checks due dates daily, sends renewal alerts via email, and computes daily overdue fines ($1.00/day).

## 3. Functional Requirements

### Module 1: Catalog & Book Management
- FR-001: The system shall allow patrons to search for books by Title, Author, ISBN, Subject Category, and Availability Status.
- FR-002: The system shall support real-time availability checking showing total copies, copies currently borrowed, and shelf location.
- FR-003: Administrators shall be able to add new book titles with metadata (ISBN, Title, Author, Publisher, Edition, Publication Year, Copies).
- FR-004: Administrators shall be able to update, categorize, or decommission lost/damaged book copies.

### Module 2: Patron Management & Authentication
- FR-005: Students must authenticate using their University ID and secure password with JWT Bearer token authentication.
- FR-006: The system shall maintain student profiles including Department, Contact Email, Student ID, and Current Borrowing Status.
- FR-007: Administrators shall have role-based access control (RBAC) permitting staff privileges not available to standard patrons.

### Module 3: Borrowing & Return Circulation
- FR-008: A patron may borrow a book for a maximum duration of 14 calendar days.
- FR-009: A patron cannot borrow more than 3 books at any given time.
- FR-010: Patrons with unpaid fines exceeding $10.00 shall be blocked from borrowing or reserving additional books.
- FR-011: When a book is returned, the system shall record the return date and compute any applicable overdue penalties.
- FR-012: Patrons may renew an active loan once for an additional 7 days if no reservation exists from another patron.

### Module 4: Fines & Penalty Management
- FR-013: Overdue loans shall incur a penalty of $1.00 per day after the due date.
- FR-014: Administrators shall be able to record fine payments and issue digital payment receipts.

### Module 5: Reservation & Queueing
- FR-015: If all copies of a book are currently borrowed, a patron may place a reservation request.
- FR-016: When a reserved book is returned, the system shall notify the patron at the top of the queue and hold the book for 48 hours.

## 4. Non-Functional Requirements
- NFR-001 (Performance): Book search query responses shall be returned within 500 milliseconds under a concurrent load of 500 users.
- NFR-002 (Security): All patron passwords must be hashed using bcrypt with salt rounds >= 12. Sensitive endpoints require TLS 1.3 encryption.
- NFR-003 (Availability): The system shall maintain 99.9% uptime during university operating semesters.
- NFR-004 (Data Integrity): Database transactions for borrowing and returns must strictly adhere to ACID properties to prevent double-checkout race conditions.
- NFR-005 (Scalability): The architecture shall support a catalog of at least 100,000 book titles and 20,000 active students.

## 5. Domain Entities & Data Attributes
- Book: id, isbn (unique), title, author, publisher, publication_year, category, total_copies, available_copies, created_at
- Student: id, student_id (unique), full_name, email (unique), hashed_password, department, fine_balance, is_active, created_at
- Borrowing: id, student_id (FK), book_id (FK), borrowed_at, due_date, returned_at, status (active, returned, overdue)
- Fine: id, borrowing_id (FK), student_id (FK), amount, status (unpaid, paid), paid_at
- Reservation: id, student_id (FK), book_id (FK), reserved_at, expires_at, status (waiting, fulfilled, cancelled)

## 6. Technical Constraints & Assumptions
- The backend application must be implemented using FastAPI and Python 3.11+.
- Persistence must utilize SQLAlchemy with SQLite for local development and PostgreSQL for production.
- Client applications access the backend via RESTful JSON APIs adhering to OpenAPI 3.0 standards.
"""

HOSPITAL_TEXT = """# SOFTWARE REQUIREMENT SPECIFICATION
# Comprehensive Hospital Management System (HMS)
# Version 1.0 - Healthcare Services 2026

## 1. Project Overview & Scope
The Comprehensive Hospital Management System (HMS) is a HIPAA-compliant healthcare enterprise platform designed to coordinate outpatient and inpatient clinical operations, streamline patient registration, automate appointment scheduling, manage electronic health records (EHR), and facilitate pharmaceutical prescriptions and medical billing.

## 2. User Roles & Actors
- Patient: Can register for an account, view medical history, schedule appointments with specialists, and pay consultation invoices online.
- Doctor / Physician: Can view assigned patient queues, review clinical charts, update diagnostic notes, prescribe medications, and order lab tests.
- Nurse / Triage Staff: Can record vital signs (blood pressure, temperature, pulse), manage bed allocations, and track medication administration.
- Hospital Administrator: Can manage department rosters, physician schedules, billing rate cards, and regulatory compliance reports.

## 3. Functional Requirements

### Module 1: Patient Admission & Identity Management
- FR-001: The system shall register patients with national health identification, contact details, emergency contacts, and insurance information.
- FR-002: Patients shall authenticate securely using multi-factor authentication (MFA) and receive role-permissioned portal access.
- FR-003: Staff shall be able to look up patient records by patient identifier, government ID number, or phone number.

### Module 2: Doctor Schedule & Appointment Booking
- FR-004: Patients shall be able to browse doctor profiles, specialty departments, consultation fees, and available calendar slots.
- FR-005: The system shall allow patients to book, reschedule, or cancel outpatient consultations up to 2 hours prior to scheduled time.
- FR-006: The system shall automatically send appointment confirmation and reminder SMS/emails 24 hours prior to consultation.

### Module 3: Electronic Health Records (EHR) & Clinical Charting
- FR-007: Physicians shall be able to record clinical encounter summaries, ICD-10 diagnostic codes, and treatment plans.
- FR-008: Nursing staff shall record patient vital signs and allergy alerts prior to physician examination.
- FR-009: Patient electronic medical records must maintain immutable audit logs recording the timestamp and staff ID for every access.

### Module 4: Pharmacy & Electronic Prescription Management
- FR-010: Physicians shall issue electronic prescriptions specifying drug name, dosage, frequency, and treatment duration.
- FR-011: The pharmacy module shall verify drug-drug interactions and allergy contraindications before dispensing medication.
- FR-012: Pharmacists shall update inventory stocks when medications are dispensed to patients.

### Module 5: Medical Billing & Insurance Claims
- FR-013: The billing service shall generate itemized invoices encompassing consultation fees, laboratory diagnostics, and medications.
- FR-014: The system shall support electronic insurance pre-authorization and claim submission.

## 4. Non-Functional Requirements
- NFR-001 (Performance): Patient chart retrieval must complete within 400 milliseconds to prevent clinical workflow disruption.
- NFR-002 (Security & Compliance): System must comply with HIPAA and GDPR regulations. All protected health information (PHI) must be encrypted at rest with AES-256 and in transit with TLS 1.3.
- NFR-003 (Availability): The core inpatient clinical system must guarantee 99.99% high availability with zero single points of failure.
- NFR-004 (Auditability): All modifications to medical records must be strictly append-only with cryptographic hash verification.
- NFR-005 (Capacity): The database must scale to accommodate 500,000 patient records and 5,000 daily clinical encounters.

## 5. Domain Entities & Data Attributes
- Patient: id, national_id (unique), full_name, date_of_birth, gender, contact_phone, email, insurance_provider, created_at
- Doctor: id, medical_license (unique), full_name, specialty, department_id (FK), consultation_fee, is_available
- Appointment: id, patient_id (FK), doctor_id (FK), appointment_date, appointment_time, status (scheduled, completed, cancelled)
- MedicalRecord: id, patient_id (FK), doctor_id (FK), appointment_id (FK), diagnosis, clinical_notes, vitals_json, created_at
- Prescription: id, medical_record_id (FK), drug_name, dosage, frequency, duration_days, status (prescribed, dispensed)
- Invoice: id, patient_id (FK), total_amount, insurance_covered, patient_payable, payment_status, created_at

## 6. Technical Constraints & Assumptions
- System must provide RESTful JSON APIs for integration with hospital laboratory equipment and external PACS imaging servers.
- Role-based authorization must enforce strict data partition between clinical staff and administrative billing personnel.
"""

SHOPPING_TEXT = """# SOFTWARE REQUIREMENT SPECIFICATION
# Modern E-Commerce & Online Shopping Platform
# Version 1.0 - Retail Operations 2026

## 1. Project Overview & Scope
The Modern E-Commerce Platform is a high-throughput multi-vendor digital marketplace enabling consumers to discover products, manage shopping carts, process electronic payments, track fulfillment shipments, and leave verified customer reviews.

## 2. User Roles & Actors
- Shopper / Customer: Can create an account, search and filter catalog merchandise, add products to cart, checkout with credit card or digital wallet, and track order deliveries.
- Merchant / Vendor: Can upload product listings, manage inventory stock counts, configure pricing discounts, and process order fulfillment.
- Marketplace Administrator: Oversees merchant onboarding, monitors suspicious transaction flags, mediates dispute refunds, and analyzes gross merchandise value (GMV).

## 3. Functional Requirements

### Module 1: Product Catalog & Intelligent Search
- FR-001: The system shall allow customers to search products by keyword, brand, category, price range, and customer review ratings.
- FR-002: Product detail pages shall display high-resolution image galleries, technical specifications, real-time stock availability, and merchant shipping estimates.
- FR-003: Merchants shall be able to create, update, or archive product SKUs with variants (size, color, weight) and pricing.

### Module 2: Shopping Cart & Wishlist Management
- FR-004: Customers shall be able to add products to a persistent shopping cart that syncs across multiple user devices.
- FR-005: The cart shall validate available inventory quantities and calculate real-time tax and delivery shipping surcharges.
- FR-006: Customers may save products to a personalized wishlist for future purchase.

### Module 3: Checkout & Secure Payment Processing
- FR-007: The checkout workflow shall validate customer shipping address and calculate estimated arrival delivery windows.
- FR-008: The payment service shall integrate with Stripe/PayPal to process PCI-DSS compliant credit card, debit, and digital wallet charges.
- FR-009: Upon successful payment authorization, the system shall decrement product inventory and generate an order confirmation receipt with tracking code.

### Module 4: Order Fulfillment & Shipment Tracking
- FR-010: Merchants shall be able to print shipping labels, update package tracking numbers, and mark orders as dispatched.
- FR-011: Customers shall receive automated push notifications and email status updates as their parcel transitions through logistics milestones.
- FR-012: Customers shall be able to request an order return or refund within 14 calendar days of delivery.

### Module 5: Customer Reviews & Ratings
- FR-013: Verified buyers shall be able to submit 1-to-5 star ratings and written reviews with photo uploads.
- FR-014: The system shall calculate aggregate rating metrics and filter out abusive or fraudulent reviews.

## 4. Non-Functional Requirements
- NFR-001 (Flash-Sale Performance): Catalog search and checkout endpoints must sustain 2,000 requests per second with latency < 300ms during peak promotional sales.
- NFR-002 (Payment Security): Zero raw payment card data may touch application servers. Full compliance with PCI-DSS Level 1 standards is required.
- NFR-003 (Reliability): 99.95% uptime SLA with automated multi-zone database replication.
- NFR-004 (Inventory Integrity): Strict atomic concurrency controls must prevent overselling limited inventory stock.
- NFR-005 (Scalability): The catalog architecture must index at least 2,000,000 active SKUs across 10,000 registered merchants.

## 5. Domain Entities & Data Attributes
- Customer: id, email (unique), hashed_password, full_name, shipping_address, phone_number, is_verified, created_at
- Product: id, merchant_id (FK), title, description, sku (unique), price, inventory_count, category, image_url, created_at
- CartItem: id, customer_id (FK), product_id (FK), quantity, added_at
- Order: id, customer_id (FK), total_price, tax_amount, shipping_fee, payment_status, order_status, tracking_number, created_at
- OrderItem: id, order_id (FK), product_id (FK), quantity, unit_price
- Review: id, customer_id (FK), product_id (FK), rating (1-5), comment, is_verified_buyer, created_at

## 6. Technical Constraints & Assumptions
- Microservice or modular monolith architecture communicating over JSON REST and webhook events.
- Client applications implemented with modern responsive web frameworks.
"""

HOTEL_TEXT = """# SOFTWARE REQUIREMENT SPECIFICATION
# Enterprise Hotel & Resort Booking System
# Version 1.0 - Hospitality Management 2026

## 1. Project Overview & Scope
The Enterprise Hotel & Resort Booking System is an integrated hospitality platform engineered to automate room inventory management, guest reservations, dynamic seasonal pricing, front-desk check-in/check-out services, concierge housekeeping scheduling, and guest billing.

## 2. User Roles & Actors
- Guest / Traveler: Can search available room types by dates, view room amenities, reserve rooms with credit card guarantee, view reservation status, and request room service.
- Front Desk Receptionist: Can process guest check-ins, issue electronic digital key cards, record incidental room charges, process room upgrades, and handle check-outs.
- Housekeeping Supervisor: Can monitor room clean/dirty states, assign cleaning shifts, and flag rooms requiring facility maintenance.
- Hotel General Manager: Configures room categories, sets seasonal tariff rates, monitors occupancy percentages, and reviews revenue per available room (RevPAR).

## 3. Functional Requirements

### Module 1: Room Catalog & Availability Search
- FR-001: The system shall allow guests to search for available rooms by check-in date, check-out date, number of adults/children, and room category (Deluxe, Suite, Standard).
- FR-002: Room detail views shall showcase high-resolution photos, bed configurations, maximum occupancy, and included amenities (Wi-Fi, breakfast, ocean view).
- FR-003: Administrators shall configure room inventories, floor assignments, and operational maintenance blocks.

### Module 2: Reservation & Deposit Management
- FR-004: Guests shall reserve rooms by providing guest contact information and credit card payment authorization.
- FR-005: The system shall calculate total stay costs including night rates, city occupancy taxes, and service fees.
- FR-006: Guests shall be permitted to modify or cancel reservations without penalty up to 48 hours prior to the 3:00 PM check-in time.

### Module 3: Front Desk Check-in & Check-out Operations
- FR-007: Front-desk staff shall execute guest check-ins, verify guest identification, and assign physical room numbers.
- FR-008: Receptionists shall record incidental security deposits and issue digital room key credentials.
- FR-009: During check-out, the system shall compute final folios incorporating room rates, minibar consumption, and dining charges.

### Module 4: Housekeeping & Room Status Management
- FR-010: The housekeeping module shall maintain real-time status for every room: Clean, Dirty, Inspected, Out-of-Order.
- FR-011: When a guest checks out, the room status shall automatically transition to Dirty and notify the housekeeping queue.
- FR-012: Housekeeping staff shall update room status to Clean upon completing sanitation protocols.

### Module 5: Concierge Services & Guest Billing
- FR-013: Guests shall be able to order dining room service and book spa appointments charged directly to their room folio.
- FR-014: The billing engine shall process credit card payments and issue electronic tax invoices upon checkout.

## 4. Non-Functional Requirements
- NFR-001 (Search Speed): Real-time room availability search results must load in less than 450 milliseconds across 10,000 calendar dates.
- NFR-002 (Security & Compliance): Guest personal data and payment credentials must be encrypted with TLS 1.3 and stored in compliance with PCI-DSS.
- NFR-003 (Reservation Integrity): Double-booking prevention must be enforced using pessimistic database row locking during checkout confirmation.
- NFR-004 (High Availability): 99.9% operational uptime to avoid check-in desk disruption during peak hotel arrival hours.
- NFR-005 (Scalability): The platform must manage property portfolios encompassing up to 50 hotel properties and 25,000 rooms.

## 5. Domain Entities & Data Attributes
- Guest: id, full_name, email (unique), phone_number, passport_number, loyalty_tier, created_at
- RoomType: id, name, description, base_price_per_night, max_occupancy, amenities_json
- Room: id, room_number (unique), room_type_id (FK), floor_number, status (clean, dirty, occupied, maintenance)
- Reservation: id, guest_id (FK), room_id (FK), check_in_date, check_out_date, number_of_guests, total_price, status (confirmed, checked_in, checked_out, cancelled)
- FolioCharge: id, reservation_id (FK), charge_type (room, dining, spa, minibar), amount, charged_at
- Payment: id, reservation_id (FK), amount, payment_method, transaction_reference, status, created_at

## 6. Technical Constraints & Assumptions
- Centralized cloud platform with REST APIs enabling integration with global distribution systems (GDS) and online travel agencies (OTAs).
- Automated night-audit scheduled job running daily at midnight to post room charges and update reporting ledgers.
"""

DOCS = [
    ("library_management_system", "Library Management System", LIBRARY_TEXT),
    ("hospital_management_system", "Hospital Management System", HOSPITAL_TEXT),
    ("online_shopping_system", "Online Shopping & E-Commerce Platform", SHOPPING_TEXT),
    ("hotel_booking_system", "Hotel & Resort Booking System", HOTEL_TEXT),
]

def generate_sample_documents():
    for filename_base, title, content_text in DOCS:
        # 1. Plain Text
        txt_path = SAMPLE_DOCS_DIR / f"{filename_base}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content_text.strip())
        print(f"Created {txt_path}")

        # 2. Microsoft Word (DOCX)
        docx_path = SAMPLE_DOCS_DIR / f"{filename_base}.docx"
        doc = docx.Document()
        
        # Set normal font
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0x22, 0x22, 0x22)

        for line in content_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                h1 = doc.add_heading(line.replace("# ", ""), level=1)
                h1.style.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
            elif line.startswith("## "):
                h2 = doc.add_heading(line.replace("## ", ""), level=2)
                h2.style.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
            elif line.startswith("### "):
                h3 = doc.add_heading(line.replace("### ", ""), level=3)
                h3.style.font.color.rgb = RGBColor(0x0F, 0x76, 0x6E)
            elif line.startswith("- "):
                doc.add_paragraph(line[2:], style='List Bullet')
            else:
                doc.add_paragraph(line)

        doc.save(str(docx_path))
        print(f"Created {docx_path}")

        # 3. PDF
        pdf_path = SAMPLE_DOCS_DIR / f"{filename_base}.pdf"
        pdf_doc = fitz.open()

        lines = content_text.strip().split("\n")
        lines_per_page = 40
        page_lines = []
        current_page_lines = []

        for line in lines:
            current_page_lines.append(line)
            if len(current_page_lines) >= lines_per_page:
                page_lines.append(current_page_lines)
                current_page_lines = []
        if current_page_lines:
            page_lines.append(current_page_lines)

        for p_idx, page_content in enumerate(page_lines):
            page = pdf_doc.new_page(width=595, height=842)  # A4
            y_pos = 50
            
            # Header
            page.insert_text(
                fitz.Point(50, y_pos),
                f"Req-to-Code: {title} SRS",
                fontsize=9,
                color=(0.4, 0.4, 0.4)
            )
            y_pos += 25

            for line in page_content:
                text = line.strip()
                if not text:
                    y_pos += 8
                    continue

                if text.startswith("# "):
                    page.insert_text(fitz.Point(50, y_pos), text.replace("# ", "")[:65], fontsize=13, color=(0.1, 0.1, 0.3))
                    y_pos += 18
                elif text.startswith("## "):
                    y_pos += 6
                    page.insert_text(fitz.Point(50, y_pos), text.replace("## ", "")[:75], fontsize=11, color=(0.15, 0.3, 0.6))
                    y_pos += 16
                elif text.startswith("### "):
                    page.insert_text(fitz.Point(50, y_pos), text.replace("### ", "")[:80], fontsize=10, color=(0.2, 0.2, 0.2))
                    y_pos += 14
                elif text.startswith("- "):
                    bullet_text = "• " + text[2:]
                    page.insert_text(fitz.Point(60, y_pos), bullet_text[:85], fontsize=8.5, color=(0.15, 0.15, 0.15))
                    y_pos += 12
                    if len(bullet_text) > 85:
                        page.insert_text(fitz.Point(70, y_pos), bullet_text[85:170], fontsize=8.5, color=(0.15, 0.15, 0.15))
                        y_pos += 12
                else:
                    page.insert_text(fitz.Point(50, y_pos), text[:90], fontsize=9, color=(0.2, 0.2, 0.2))
                    y_pos += 13

            # Footer
            page.insert_text(
                fitz.Point(260, 810),
                f"Page {p_idx + 1} of {len(page_lines)}",
                fontsize=8,
                color=(0.5, 0.5, 0.5)
            )

        pdf_doc.save(str(pdf_path))
        pdf_doc.close()
        print(f"Created {pdf_path}")

if __name__ == "__main__":
    generate_sample_documents()
