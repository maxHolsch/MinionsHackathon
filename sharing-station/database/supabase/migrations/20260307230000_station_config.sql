create table station_config (
  id            int primary key default 1 check (id = 1), -- single row enforced
  station_asleep boolean not null default true
);

insert into station_config (id, station_asleep) values (1, true);
