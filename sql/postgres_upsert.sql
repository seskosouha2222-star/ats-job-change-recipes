-- Keep a Postgres table of open jobs in sync with the ATS Job Changes Feed (agitools/ats-jobs-delta).
-- Load the dataset items of one run into feed_items (in dataset order), then run the two statements below in one
-- transaction. Insert or update on new / changed / reopened / unchanged, delete on closed / unmatched: afterwards
-- open_jobs equals the open jobs that match your current filters.
-- Built by AGI Tools Team.

CREATE TABLE IF NOT EXISTS open_jobs (
    ats             text NOT NULL,
    company_slug    text NOT NULL,
    job_id          text NOT NULL,
    company_name    text,
    title           text,
    department      text,
    team            text,
    locations       jsonb,
    country         text,
    workplace_type  text,
    employment_type text,
    salary          jsonb,
    url             text,
    apply_url       text,
    published_at    timestamptz,
    first_seen_at   timestamptz,
    last_change     text,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ats, company_slug, job_id)
);

-- One row per dataset item, in the order the run wrote them (ord). Truncate before each load.
CREATE TABLE IF NOT EXISTS feed_items (ord bigserial PRIMARY KEY, item jsonb NOT NULL);

BEGIN;

-- 1. Latest record per job in this run wins (a job appears at most once per run, but be safe).
WITH latest AS (
    SELECT DISTINCT ON (item->>'ats', item->>'companySlug', item->>'jobId') item
    FROM feed_items
    WHERE item->>'recordType' = 'job'
    ORDER BY item->>'ats', item->>'companySlug', item->>'jobId', ord DESC
)
INSERT INTO open_jobs AS o (ats, company_slug, job_id, company_name, title, department, team, locations, country,
                            workplace_type, employment_type, salary, url, apply_url, published_at, first_seen_at,
                            last_change)
SELECT item->>'ats', item->>'companySlug', item->>'jobId', item->>'companyName', item->>'title',
       item->>'department', item->>'team', item->'locations', item->>'country', item->>'workplaceType',
       item->>'employmentType', NULLIF(item->'salary', 'null'::jsonb), item->>'url', item->>'applyUrl',
       (item->>'publishedAt')::timestamptz, (item->>'firstSeenAt')::timestamptz, item->>'changeType'
FROM latest
WHERE item->>'changeType' IN ('new', 'changed', 'reopened', 'unchanged')
ON CONFLICT (ats, company_slug, job_id) DO UPDATE SET
    company_name = EXCLUDED.company_name, title = EXCLUDED.title, department = EXCLUDED.department,
    team = EXCLUDED.team, locations = EXCLUDED.locations, country = EXCLUDED.country,
    workplace_type = EXCLUDED.workplace_type, employment_type = EXCLUDED.employment_type,
    salary = EXCLUDED.salary, url = EXCLUDED.url, apply_url = EXCLUDED.apply_url,
    published_at = EXCLUDED.published_at, last_change = EXCLUDED.last_change, updated_at = now();

-- 2. Remove jobs that closed on the board or left your filtered view.
DELETE FROM open_jobs o
USING feed_items f
WHERE f.item->>'recordType' = 'job'
  AND f.item->>'changeType' IN ('closed', 'unmatched')
  AND o.ats = f.item->>'ats' AND o.company_slug = f.item->>'companySlug' AND o.job_id = f.item->>'jobId';

COMMIT;
