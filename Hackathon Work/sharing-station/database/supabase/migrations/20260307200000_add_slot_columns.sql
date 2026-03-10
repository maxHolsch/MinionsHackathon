-- Add physical slot tracking to items table.
-- Grid: 3 rows (0-2) × 10 columns (0-9) = 30 slots.

alter table items add column slot_row integer check (slot_row >= 0 and slot_row <= 2);
alter table items add column slot_col integer check (slot_col >= 0 and slot_col <= 9);

-- Prevent two available items from occupying the same slot.
-- Borrowed items keep their historical slot values but don't block the position.
create unique index items_slot_unique_available
  on items (slot_row, slot_col)
  where status = 'available' and slot_row is not null and slot_col is not null;
