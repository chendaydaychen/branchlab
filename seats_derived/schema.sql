-- SEATS-derived subset. Flight and reservation keys/seat uniqueness follow
-- BenchBase SEATS; versions and branch_commit are BranchLab extensions.
CREATE SCHEMA IF NOT EXISTS seats_derived;
SET search_path TO seats_derived;
DROP TABLE IF EXISTS branch_commit;
DROP TABLE IF EXISTS reservation;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS flight;
CREATE TABLE flight (
  f_id VARCHAR(32) PRIMARY KEY,
  f_base_price NUMERIC(10,2) NOT NULL,
  f_seats_total INTEGER NOT NULL CHECK (f_seats_total > 0),
  f_seats_left INTEGER NOT NULL CHECK (f_seats_left >= 0),
  row_version BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE customer (
  c_id VARCHAR(32) PRIMARY KEY,
  reservations INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE reservation (
  r_id BIGINT PRIMARY KEY,
  r_c_id VARCHAR(32) NOT NULL REFERENCES customer(c_id),
  r_f_id VARCHAR(32) NOT NULL REFERENCES flight(f_id),
  r_seat INTEGER NOT NULL,
  r_price NUMERIC(10,2) NOT NULL,
  UNIQUE (r_f_id, r_seat),
  UNIQUE (r_f_id, r_c_id)
);
CREATE TABLE branch_commit (
  branch_id BIGINT PRIMARY KEY,
  task_id INTEGER NOT NULL,
  candidate_id INTEGER NOT NULL,
  f_id VARCHAR(32) NOT NULL REFERENCES flight(f_id),
  committed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
