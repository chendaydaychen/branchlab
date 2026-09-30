-- TATP-derived schema.  The four operational tables and primary keys follow
-- BenchBase TATP's PostgreSQL DDL. `row_version` and `branch_commit` are
-- BranchLab extensions used only for explicit optimistic validation/auditing.
CREATE SCHEMA IF NOT EXISTS tatp_derived;
SET search_path TO tatp_derived;

DROP TABLE IF EXISTS branch_commit;
DROP TABLE IF EXISTS call_forwarding;
DROP TABLE IF EXISTS special_facility;
DROP TABLE IF EXISTS access_info;
DROP TABLE IF EXISTS subscriber;

CREATE TABLE subscriber (
  s_id INTEGER PRIMARY KEY,
  sub_nbr VARCHAR(15) NOT NULL UNIQUE,
  bit_1 SMALLINT NOT NULL DEFAULT 0,
  msc_location INTEGER NOT NULL DEFAULT 0,
  vlr_location INTEGER NOT NULL DEFAULT 0,
  row_version BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE access_info (
  s_id INTEGER NOT NULL REFERENCES subscriber(s_id),
  ai_type SMALLINT NOT NULL,
  data1 SMALLINT NOT NULL,
  data2 SMALLINT NOT NULL,
  data3 VARCHAR(3) NOT NULL,
  data4 VARCHAR(5) NOT NULL,
  row_version BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (s_id, ai_type)
);
CREATE TABLE special_facility (
  s_id INTEGER NOT NULL REFERENCES subscriber(s_id),
  sf_type SMALLINT NOT NULL,
  is_active SMALLINT NOT NULL DEFAULT 1,
  data_a SMALLINT NOT NULL DEFAULT 0,
  row_version BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (s_id, sf_type)
);
CREATE TABLE call_forwarding (
  s_id INTEGER NOT NULL,
  sf_type SMALLINT NOT NULL,
  start_time SMALLINT NOT NULL,
  end_time SMALLINT NOT NULL,
  numberx VARCHAR(15) NOT NULL,
  PRIMARY KEY (s_id, sf_type, start_time),
  FOREIGN KEY (s_id, sf_type) REFERENCES special_facility(s_id, sf_type)
);
CREATE TABLE branch_commit (
  branch_id BIGINT PRIMARY KEY,
  task_id INTEGER NOT NULL,
  candidate_id INTEGER NOT NULL,
  s_id INTEGER NOT NULL REFERENCES subscriber(s_id),
  action VARCHAR(32) NOT NULL,
  materialized BOOLEAN NOT NULL,
  committed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
