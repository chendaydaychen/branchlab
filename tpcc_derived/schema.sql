CREATE SCHEMA IF NOT EXISTS tpcc_derived;
SET search_path TO tpcc_derived;

DROP TABLE IF EXISTS candidate_order;
DROP TABLE IF EXISTS stock;
DROP TABLE IF EXISTS item;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS district;
DROP TABLE IF EXISTS warehouse;

CREATE TABLE warehouse (
  w_id INTEGER PRIMARY KEY,
  w_tax NUMERIC(4,3) NOT NULL,
  row_version BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE district (
  d_w_id INTEGER NOT NULL REFERENCES warehouse(w_id),
  d_id INTEGER NOT NULL,
  d_tax NUMERIC(4,3) NOT NULL,
  d_next_o_id BIGINT NOT NULL,
  row_version BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (d_w_id, d_id)
);
CREATE TABLE customer (
  c_w_id INTEGER NOT NULL,
  c_d_id INTEGER NOT NULL,
  c_id INTEGER NOT NULL,
  c_discount NUMERIC(4,3) NOT NULL,
  row_version BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (c_w_id, c_d_id, c_id),
  FOREIGN KEY (c_w_id, c_d_id) REFERENCES district(d_w_id, d_id)
);
CREATE TABLE item (
  i_id INTEGER PRIMARY KEY,
  i_price INTEGER NOT NULL,
  row_version BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE stock (
  s_w_id INTEGER NOT NULL REFERENCES warehouse(w_id),
  s_i_id INTEGER NOT NULL REFERENCES item(i_id),
  s_quantity INTEGER NOT NULL CHECK (s_quantity >= 0),
  row_version BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (s_w_id, s_i_id)
);
CREATE TABLE candidate_order (
  branch_id BIGINT PRIMARY KEY,
  w_id INTEGER NOT NULL,
  d_id INTEGER NOT NULL,
  c_id INTEGER NOT NULL,
  supplying_w_id INTEGER NOT NULL,
  i_id INTEGER NOT NULL,
  amount INTEGER NOT NULL CHECK (amount > 0)
);
