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
  created_at  timestamptz default now()
);

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
