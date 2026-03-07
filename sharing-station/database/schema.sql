-- Sharing Station — Supabase Schema

create table users (
  id         uuid primary key default gen_random_uuid(),
  nfc_uuid   text unique not null,
  name       text not null,
  nickname   text,
  is_active  boolean not null default false,
  created_at timestamptz default now()
);

create table items (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  category    text,
  status      text not null default 'available' check (status in ('available', 'borrowed')),
  donated_by  uuid references users(id) on delete set null,
  slot_row    integer check (slot_row >= 0 and slot_row <= 2),
  slot_col    integer check (slot_col >= 0 and slot_col <= 9),
  created_at  timestamptz default now()
);

-- Prevent two available items from occupying the same physical slot
create unique index items_slot_unique_available
  on items (slot_row, slot_col)
  where status = 'available' and slot_row is not null and slot_col is not null;

create table transactions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users(id) on delete cascade,
  item_id    uuid not null references items(id) on delete cascade,
  action     text not null check (action in ('check_in', 'check_out')),
  created_at timestamptz default now()
);

create table memories (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references users(id) on delete cascade,
  content    text not null,
  created_at timestamptz default now()
);

-- Index for fast NFC lookup
create unique index users_nfc_uuid_idx on users(nfc_uuid);

-- Index for fetching all memories for a user
create index memories_user_id_idx on memories(user_id);

-- Index for fetching transaction history per user/item
create index transactions_user_id_idx on transactions(user_id);
create index transactions_item_id_idx on transactions(item_id);

-- Seed baseline hackathon users (idempotent).
insert into users (nfc_uuid, name, nickname, is_active)
values
  ('abc123', 'Peter', 'Tiger', false),
  ('def456', 'Alice', null, false),
  ('ghi789', 'Bob', null, false)
on conflict (nfc_uuid) do update
set
  name = excluded.name,
  nickname = excluded.nickname;

-- Seed baseline memories/preferences for Peter (idempotent).
insert into memories (user_id, content)
select u.id, m.content
from (
  values
    ('abc123', 'Loves sci-fi books'),
    ('abc123', 'Plays Catan every Thursday'),
    ('abc123', 'preferences::science fiction, strategy games')
) as m(nfc_uuid, content)
join users u on u.nfc_uuid = m.nfc_uuid
where not exists (
  select 1
  from memories existing
  where existing.user_id = u.id
    and existing.content = m.content
);
