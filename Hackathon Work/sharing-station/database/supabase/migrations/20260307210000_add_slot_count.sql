-- Add slot_count to track how many contiguous columns an item occupies.
-- Default 1 for backwards compatibility with existing single-slot items.

alter table items add column slot_count integer not null default 1 check (slot_count >= 1 and slot_count <= 10);
