DROP TABLE IF EXISTS branch_actions;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS flights;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
  user_id INTEGER PRIMARY KEY,
  loyalty_tier INTEGER NOT NULL,
  row_version BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE flights (
  flight_id INTEGER PRIMARY KEY,
  price_cents INTEGER NOT NULL CHECK (price_cents > 0),
  seats_left INTEGER NOT NULL CHECK (seats_left >= 0),
  row_version BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE orders (
  order_id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(user_id),
  flight_id INTEGER NOT NULL REFERENCES flights(flight_id),
  status TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled', 'split')),
  row_version BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE branch_actions (
  branch_id BIGINT PRIMARY KEY,
  task_id INTEGER NOT NULL,
  candidate INTEGER NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('rebook', 'cancel_rebook', 'split')),
  target_flight INTEGER NOT NULL REFERENCES flights(flight_id)
);

CREATE INDEX orders_user_id_idx ON orders(user_id);
