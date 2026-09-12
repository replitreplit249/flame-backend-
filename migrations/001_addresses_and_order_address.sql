-- Run this migration against an existing PostgreSQL database.
-- Existing orders must be assigned an address before the NOT NULL constraint is applied.

CREATE TABLE IF NOT EXISTS addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(50) NOT NULL DEFAULT 'Home',
    address_line TEXT NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(100) NOT NULL DEFAULT 'India',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_addresses_user ON addresses(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_addresses_one_default_per_user ON addresses(user_id) WHERE is_default = TRUE;

ALTER TABLE orders ADD COLUMN IF NOT EXISTS address_id UUID REFERENCES addresses(id);

-- Backfill one placeholder address per user that has existing orders.
INSERT INTO addresses (user_id, label, address_line, city, state, postal_code, country, is_default)
SELECT DISTINCT o.user_id, 'Legacy', 'Address pending update', 'Unknown', 'Unknown', '000000', 'India', TRUE
FROM orders o
WHERE o.user_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM addresses a WHERE a.user_id = o.user_id);

UPDATE orders o
SET address_id = a.id
FROM addresses a
WHERE o.address_id IS NULL AND a.user_id = o.user_id;

ALTER TABLE orders ALTER COLUMN address_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_address ON orders(address_id);
