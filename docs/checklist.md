# Financial Planner - MVP Development Roadmap

This document outlines the focused roadmap to deliver the Minimum Viable Product (MVP). All other features will be considered for future releases after the MVP is complete and validated.

---

## Phase 1: Foundations (✅ Complete)

### Epic 0: Project Setup

* [X] Initialize FastAPI backend
* [X] Initialize React frontend
* [X] Setup Docker for development
* [X] Implement logging and error handling

### Epic 1: Data Model & Migrations

* [X] Define database schema with SQLAlchemy
* [X] Implement double-entry accounting model
* [X] Setup Alembic for database migrations
* [X] Write comprehensive tests for the data model

---

## Phase 2: Core MVP Features (🚧 In Progress)

### Epic 2: MVP Backend Development

The current focus is on exposing all necessary API endpoints for the frontend to consume.

* **Account Management**
  * [X] Implement `GET /accounts/`
  * [X] Implement `POST /accounts/`
  * [X] Implement `GET /accounts/{account_id}`
  * [ ] Implement `PUT /accounts/{account_id}`
  * [ ] Implement `DELETE /accounts/{account_id}`
* **Transaction Management**
  * [ ] Implement `POST /transactions`
* **Dashboard**
  * [ ] Implement `GET /dashboard/timeseries`
  * [ ] Add filtering by date range
  * [ ] Add filtering by account IDs
    ---
