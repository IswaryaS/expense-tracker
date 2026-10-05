# Personal Expense & Bill Analysis

## Problem

Keeping track of expenses across bills can involve manually entering information from different vendors into a spreadsheet or other tracking system.

This application provides a single place to upload bill images, extract relevant expense information, review the extracted data, and track monthly expenses.

## Workflow

```text
Bill Image
    ↓
POST /bills/upload
    ↓
Vision LLM extracts structured information
    ↓
Bill stored as Pending
    ↓
GET /bills/review
    ↓
User reviews / edits extracted information
    ↓
PUT /bills/{bill_id}
    ↓
Approved bill stored with user-confirmed values and category
    ↓
Monthly expenses calculated
```

## Features

* Upload bill images from different vendors
* Extract structured bill information using a vision LLM
* Store extracted bills in a pending state for review
* Review and edit extracted information before approval
* Assign an expense category during approval
* Persist approved bill information in the database
* Calculate monthly expenses
* View bill and expense information through a Streamlit dashboard

## API

| Method | Endpoint           | Purpose                                                                       |
| ------ | ------------------ | ----------------------------------------------------------------------------- |
| `POST` | `/bills/upload`    | Upload a bill image and extract structured information using the vision model |
| `GET`  | `/bills/review`    | Retrieve bills awaiting user review                                           |
| `PUT`  | `/bills/{bill_id}` | Update and approve bill information after review                              |

## Data Model

The current bill model stores:

* `bill_id`
* `vendor_name`
* `bill_date`
* `total_amount`
* `category`

The application uses abstracted data models for its tables and row structures rather than coupling application logic directly to SQLite-specific implementations. This keeps the database layer easier to change if the application's requirements eventually call for a different relational database.

**Potential reasons for moving to PostgreSQL/MySQL:** [to be documented]

## Database & Migrations

The application uses **SQLModel**, backed by **SQLAlchemy**, for database interaction with SQLite as the current database.

**Alembic** is used for database migrations, allowing schema changes such as adding columns or introducing new tables to be tracked and applied without manually recreating the database.

## Bill Information Extraction

Different vendors can produce bills with significantly different layouts and formats. Traditional OCR approaches such as Tesseract and PaddleOCR were considered, but OCR alone would require additional logic to interpret the extracted text across different bill formats, including increasingly complex regular expressions and vendor-specific handling.

A vision LLM was selected for the current implementation because it can work directly with the bill image and return the required information in a structured format.

The application currently uses the **Groq API with the Qwen Vision model** for bill extraction. For the current scope, the amount of information required from each bill is relatively small, keeping the expected token usage low.

**[Add measured token/cost figures here.]**

The extraction mechanism is kept separate from the rest of the bill-management workflow so that it can be modified independently as requirements change.

## Technology Stack

| Component           | Technology                  |
| ------------------- | --------------------------- |
| Backend / API       | Python, FastAPI             |
| Database            | SQLite                      |
| Database Layer      | SQLModel, SQLAlchemy        |
| Database Migrations | Alembic                     |
| Frontend            | Streamlit                   |
| Bill Extraction     | Groq API, Qwen Vision Model |
| Testing             | pytest                      |

## AI-Assisted Development

AI tools were used during development for research, debugging, implementation assistance, and exploring alternative approaches.

* Google Gemini / AI Mode
* Groq AI

AI assistance was used as a development aid; application behavior and implementation decisions were reviewed and tested as part of the development process.

## Design Considerations

The database structure and other parts of the application are intentionally kept simple for the current scope. This avoids introducing unnecessary complexity while keeping the structure flexible enough to expand as the expense-tracking requirements grow.

The bill extraction workflow also treats AI-generated information as data requiring verification rather than assuming that the extraction is always correct. Bills remain in a pending state until the extracted information is reviewed and approved by the user.

## Current Status

The core workflow for uploading bills, extracting information, reviewing and editing the extracted data, storing approved bills, and calculating monthly expenses is implemented.

The application is intentionally focused on the current use case while keeping the underlying structure flexible enough for future expansion.
