-- Run this migration against an existing PostgreSQL database.

CREATE TABLE IF NOT EXISTS product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_images_one_primary ON product_images(product_id) WHERE is_primary = TRUE;

-- Optional compatibility backfill: move each legacy products.image_url into the new table.
INSERT INTO product_images (product_id, image_url, is_primary)
SELECT p.id, p.image_url, TRUE
FROM products p
WHERE p.image_url IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM product_images pi WHERE pi.product_id = p.id);
