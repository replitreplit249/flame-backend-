# E-commerce CRUD API

FastAPI + SQLAlchemy implementation for the supplied Flipkart/Amazon-style schema. It supports PostgreSQL through `DATABASE_URL` and uses SQLite by default for quick local tests.

## Run locally

```bash
cd /home/ubuntu/ecommerce-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Swagger UI: `http://127.0.0.1:8000/docs`

## Authentication

Create a user with `POST /users`, then login with `POST /auth/login`:

```json
{
  "email": "user@example.com",
  "password": "secret123"
}
```

The response contains a JWT `access_token`. Send it on protected requests as:

```text
Authorization: Bearer <access_token>
```

`/cart`, `/orders`, `/addresses`, and `/users` routes require a valid token. Ownership is enforced from the token, so a user cannot read or modify another user's cart, profile, addresses, or orders. `POST /users`, `POST /auth/login`, product/category routes, and `/health` remain public.

Products support `name`, `min_price`, `max_price`, and `sort` query parameters. Example: `/products?name=mouse&min_price=10&max_price=100&sort=price_desc`, where `sort` is `price_asc` or `price_desc`.

Users can have multiple addresses through `/addresses`. The first address becomes default automatically; setting another address as default clears the previous default. New orders require an owned `address_id`, which is stored on the order.

Products support multiple photos through `/products/{product_id}/images`. The first image is automatically primary; setting another image as primary clears the previous one. Deleting or unsetting the primary image promotes another image when available. The legacy `products.image_url` column is retained temporarily for backward compatibility.

For PostgreSQL, start the bundled database first:

```bash
docker compose up -d db
# .env already points to postgresql+psycopg://ecommerce:ecommerce@localhost:5432/ecommerce
uvicorn app.main:app --reload
```

## CRUD endpoints

| Resource | Endpoints |
|---|---|
| Auth | `POST /auth/login` |
| Users | `POST /users`, authenticated `GET /users`, `GET/PATCH/DELETE /users/{id}` |
| Categories | `POST/GET /categories`, `GET/PATCH/DELETE /categories/{id}` |
| Products | `POST/GET /products`, `GET/PATCH/DELETE /products/{id}`; search/filter/sort query params supported |
| Product images | `POST/GET /products/{product_id}/images`, `PATCH/DELETE /product-images/{id}` |
| Addresses | Authenticated `POST/GET /addresses`, `GET/PATCH/DELETE /addresses/{id}` |
| Cart | Authenticated `POST /cart`, `GET /cart?user_id=...`, `PATCH/DELETE /cart/{id}` |
| Orders | Authenticated `POST/GET /orders`, `GET/DELETE /orders/{id}`, `PATCH /orders/{id}/status` |
| Order items | `GET /orders/{id}/items` |

Order creation is transactional: it validates the user, checks stock, snapshots purchase prices, decrements inventory, and calculates `total_amount`. Passwords are stored as bcrypt hashes and never returned by the API.

## Notes

The API creates tables automatically on startup. For production, replace startup creation with Alembic migrations, add authentication/authorization, and use stricter order-state transition rules. The provided SQL schema remains available at `schema.sql`.

For an existing PostgreSQL database created before addresses were added, run `migrations/001_addresses_and_order_address.sql` before restarting the API. It creates a legacy placeholder address for existing orders so the new required `orders.address_id` constraint can be applied safely.

For product image support on an existing database, run `migrations/002_product_images.sql`. It creates the table, indexes, one-primary constraint, and backfills non-null legacy `products.image_url` values.
