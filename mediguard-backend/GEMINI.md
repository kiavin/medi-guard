# CDSS Project Architecture & Rules

## 1. System Operations & CLI Permissions
You have full authorization to manage this project. When asked to implement a feature or fix a bug, you must:
* **Create/Edit Files:** Directly generate or modify files in both the backend (`app/`) and frontend directories.
* **Docker Commands:** Output the exact Docker commands needed to restart services or run commands inside the containers. 
* **Database Migrations:** Whenever you modify a SQLAlchemy model, you must provide the Docker execution commands to run Alembic (e.g., `docker exec -it mediguard_api alembic revision --autogenerate -m "update"` and `alembic upgrade head`).

## 2. Backend Stack & Standards
* **Framework:** FastAPI, Python 3.11+, SQLAlchemy 2.0, Pydantic V2.
* **Database:** PostgreSQL. 
* **Primary Keys:** All tables use UUID strings generated via `str(uuid.uuid4())`.
* **Standardization:** All API endpoints must return data wrapped in the custom `send_success(data=..., message=...)` utility.

## 3. Database Architecture (Modular Setup)
* **Separation of Concerns:** SQLAlchemy models are strictly split into individual files within the `app/models/` directory (e.g., `user.py`, `patient.py`, `laboratory.py`). 
* **Base & Mixins:** Every new model must inherit from `(Base, AuditMixin)` imported from their respective core files to ensure automated `id`, `created_at`, `updated_at`, `is_deleted`, and `deleted_at` tracking.
* **Preventing Circular Imports:** * Always use string references for relationships (e.g., `relationship("LabRequest")`).
    * **CRITICAL:** Every new model file MUST be imported into `app/models/__init__.py` to ensure SQLAlchemy's global registry registers the mappers before the app boots.

## 4. API & Pydantic (UI-Driven Payloads)
* **Pydantic V2:** Use `model_config = ConfigDict(...)`. If using fields that start with `model_` (like `model_used`), you must include `protected_namespaces=()` to suppress warnings.
* **Frontend Alignment:** Pydantic response schemas must be structured to perfectly match the JSON payloads expected by the Vue 3 OneUI frontend. Do not force the frontend to transform backend data.

## 5. AI Integration (Gemini)
* **Prompt Engineering:** All AI prompts must instruct the model to return strict, properly escaped JSON.
* **Raw Storage:** Always save the entire raw JSON response from the Gemini API into the `raw_response` JSONB column in the database.
* **1-to-Many Relationships:** A `Consultation` can have multiple `Predictions`. Always query the most recent prediction by sorting `created_at` descending.

## 6. Frontend Stack
* **Framework:** Vue 3 (Composition API), Vite, Axios.
* **Styling:** OneUI template aesthetics.