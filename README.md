# Bristol Regional Food Network Digital Marketplace

Django implementation of the Bristol Regional Food Network marketplace case study.

## Features Covered

- Producer, customer, community group, restaurant, and admin account roles
- Product listings with categories, stock, seasonal availability, organic certification, allergens, harvest/best-before dates, and images
- Product search, category browsing, organic filtering, allergen exclusion, and surplus deal browsing
- Cart, single-producer checkout, multi-producer checkout, mock payment recording, producer sub-orders, and 5% commission calculations
- Producer incoming orders, status transitions, customer notifications, and status audit history
- Weekly-style producer settlements with CSV export
- Food miles estimates from customer and producer postcodes
- Bulk community ordering and restaurant recurring order templates
- Surplus produce discounts
- Producer recipes and farm stories linked to products
- Customer order history, reorder, receipt export, ratings, and verified-purchase reviews
- Low stock thresholds and producer alerts
- Admin commission reporting with filters and CSV export

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000`.

Optional demo data:

```bash
python manage.py seed_data
```

## Docker Setup

```bash
docker compose up --build
docker compose exec web python manage.py seed_data
```

Open `http://127.0.0.1:8000`.

The Docker setup runs four containers:

- `nginx`: reverse proxy exposed on port `8000`
- `web`: Django/Gunicorn application
- `db`: PostgreSQL database
- `payment-mock`: sandbox payment service used by checkout

## Running Tests

```bash
python manage.py test
```

The assessment regression suite covers all provided test-case IDs from `TC-001` through `TC-025` in `orders/test_assessment_cases.py`.

Latest verified result:

```text
Ran 97 tests
OK
```

## Admin Access

Create an admin user locally with:

```bash
python manage.py createsuperuser
```

Admin commission reports are available at `/orders/admin/commissions/` for staff users.
