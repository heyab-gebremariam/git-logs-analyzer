-- Enable pgcrypto for gen_random_uuid
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE developers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  github_username TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE commits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_name TEXT NOT NULL,
  commit_hash TEXT NOT NULL,
  author_name TEXT NOT NULL,
  author_email TEXT NOT NULL,
  message TEXT,
  timestamp TIMESTAMPTZ NOT NULL,
  is_overtime BOOLEAN NOT NULL DEFAULT false,
  analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  lines_added INTEGER,
  lines_deleted INTEGER,
  UNIQUE (repo_name, commit_hash)
);

CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  developer_id UUID REFERENCES developers(id) ON DELETE CASCADE,
  repo_name TEXT,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  num_commits INTEGER NOT NULL DEFAULT 0,
  num_regular INTEGER NOT NULL DEFAULT 0,
  num_overtime INTEGER NOT NULL DEFAULT 0,
  report_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_to_slack_at TIMESTAMPTZ,
  sent_to_email_at TIMESTAMPTZ
);

CREATE TABLE report_commits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
  commit_id UUID REFERENCES commits(id) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX idx_commits_author_email_ts ON commits(author_email, timestamp DESC);
CREATE INDEX idx_reports_developer_dates ON reports(developer_id, start_date, end_date);