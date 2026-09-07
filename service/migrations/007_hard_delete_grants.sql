-- Migration 007: grants required for hard-delete of offers (Action 232).
-- Apply once as superuser. Idempotent.

GRANT DELETE ON offers.job_offers TO api_user;
GRANT DELETE ON offers.offer_assignments TO api_user;
GRANT DELETE ON audit.activity_log TO api_user;
