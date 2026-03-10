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
