# Bistate

Bistate is a real-estate property workspace. This first milestone establishes the Python API, React dashboard, local database migration path, containers, and continuous integration. Underwriting is intentionally out of scope for now.

## Stack

- **API:** Python, FastAPI, SQLAlchemy, SQLite, and Alembic
- **Web:** React, TypeScript, Vite, and Tailwind CSS
- **Delivery:** Docker Compose and GitHub Actions

## Local development

### Prerequisites

- Python 3.13+
- Node.js 22+

### API

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; `GET /api/health` returns `{ "status": "ok" }`.

### Web dashboard

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite forwards `/api` requests to the local API, and the dashboard displays its health status.

## Tests and migrations

```bash
cd backend
pytest -q
alembic upgrade head
```

Create a future migration after changing SQLAlchemy models with:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
```

## Containers

To run the application in Docker:

```bash
docker compose up --build
```

The dashboard is then served on `http://localhost:5173`, and the API on `http://localhost:8000`.

## Underwriting engine

`POST /api/underwriting/calculate` evaluates the Scenario A formulas from the primary
`Upstate_Airbnb_Wedding_Venue_Underwriting_Model.xlsx` workbook. Send an empty JSON
object to use the workbook defaults, or override any documented assumption:

```json
{"purchase_price": 500000, "occupancy": 0.5, "nightly_rate": 425}
```

The response returns the workbook's acquisition, revenue, operating-cost, financing,
tax, and dashboard sections. Formula references that are internally inconsistent in
the workbook are intentionally retained literally: the dashboard uses Revenue Model
B19, while the worksheet's total-gross-revenue B20 uses B10 and B18.
