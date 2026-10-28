-- JARVIS-owned storage only. Platform roles already exist; do not alter them.
REVOKE ALL ON SCHEMA jarvis FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA jarvis TO authenticated;

CREATE FUNCTION jarvis.current_subject() RETURNS uuid
LANGUAGE plpgsql STABLE
SET search_path = pg_catalog
AS $$
DECLARE
    claims text;
BEGIN
    claims := current_setting('request.jwt.claims', true);
    IF claims IS NULL OR btrim(claims) = '' THEN
        RETURN NULL;
    END IF;
    RETURN (claims::jsonb ->> 'sub')::uuid;
EXCEPTION WHEN invalid_text_representation THEN
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.current_subject() FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION jarvis.current_subject() TO authenticated;

CREATE TABLE jarvis.workshops (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200 AND btrim(name) <> '')
);

CREATE TABLE jarvis.memberships (
    workshop_id uuid NOT NULL REFERENCES jarvis.workshops(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    can_write boolean NOT NULL DEFAULT false,
    PRIMARY KEY (workshop_id, user_id)
);
CREATE INDEX memberships_user_id ON jarvis.memberships(user_id, workshop_id);

CREATE TABLE jarvis.records (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    owner_id uuid NOT NULL,
    workshop_id uuid REFERENCES jarvis.workshops(id) ON DELETE CASCADE,
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200 AND btrim(title) <> ''),
    payload jsonb NOT NULL CHECK (
        jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 65536
    ),
    revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX records_owner_id ON jarvis.records(owner_id, id) WHERE workshop_id IS NULL;
CREATE INDEX records_workshop_id ON jarvis.records(workshop_id, id) WHERE workshop_id IS NOT NULL;

-- Metadata-only events commit atomically with storage mutations. No record FK:
-- deleting a record must not remove its historical event.
CREATE TABLE jarvis.record_events (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    subject uuid NOT NULL,
    event text NOT NULL CHECK (event IN ('created', 'updated', 'deleted')),
    record_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX record_events_subject ON jarvis.record_events(subject, created_at, id);

CREATE FUNCTION jarvis.enforce_record_update() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
       OR NEW.workshop_id IS DISTINCT FROM OLD.workshop_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Record ownership and identity are immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.revision IS DISTINCT FROM OLD.revision + 1 THEN
        RAISE EXCEPTION 'Record revision must advance by one' USING ERRCODE = '23514';
    END IF;
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.enforce_record_update() FROM PUBLIC, anon, authenticated, service_role;
CREATE TRIGGER records_update BEFORE UPDATE ON jarvis.records
FOR EACH ROW EXECUTE FUNCTION jarvis.enforce_record_update();

ALTER TABLE jarvis.workshops ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.workshops FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.records ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.records FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.record_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.record_events FORCE ROW LEVEL SECURITY;

-- The separate schema owner provisions tenants without disabling FORCE RLS.
-- Runtime cannot assume this migration role or modify membership policies.
DO $$
BEGIN
    EXECUTE format('CREATE POLICY workshops_admin ON jarvis.workshops FOR ALL TO %I USING (true) WITH CHECK (true)', current_user);
    EXECUTE format('CREATE POLICY memberships_admin ON jarvis.memberships FOR ALL TO %I USING (true) WITH CHECK (true)', current_user);
END;
$$;

-- Provisioning is an explicit administrative operation using the separate
-- migration account. FORCE RLS remains enabled even for that table owner;
-- these policies grant it membership/workshop administration, not record
-- access. Runtime and platform roles receive no membership in this account.
DO $$
BEGIN
    EXECUTE format(
        'CREATE POLICY workshops_provision ON jarvis.workshops FOR ALL TO %I USING (true) WITH CHECK (true)',
        current_user
    );
    EXECUTE format(
        'CREATE POLICY memberships_provision ON jarvis.memberships FOR ALL TO %I USING (true) WITH CHECK (true)',
        current_user
    );
END;
$$;

CREATE POLICY record_events_read ON jarvis.record_events FOR SELECT TO authenticated
USING (subject = jarvis.current_subject());
CREATE POLICY record_events_insert ON jarvis.record_events FOR INSERT TO authenticated
WITH CHECK (subject = jarvis.current_subject());

CREATE POLICY memberships_read ON jarvis.memberships FOR SELECT TO authenticated
USING (user_id = jarvis.current_subject());

CREATE POLICY workshops_read ON jarvis.workshops FOR SELECT TO authenticated
USING (EXISTS (
    SELECT 1 FROM jarvis.memberships AS membership
    WHERE membership.workshop_id = workshops.id
      AND membership.user_id = jarvis.current_subject()
));

CREATE POLICY records_read ON jarvis.records FOR SELECT TO authenticated
USING (
    (workshop_id IS NULL AND owner_id = jarvis.current_subject())
    OR EXISTS (
        SELECT 1 FROM jarvis.memberships AS membership
        WHERE membership.workshop_id = records.workshop_id
          AND membership.user_id = jarvis.current_subject()
    )
);

CREATE POLICY records_insert ON jarvis.records FOR INSERT TO authenticated
WITH CHECK (
    owner_id = jarvis.current_subject()
    AND (
        workshop_id IS NULL
        OR EXISTS (
            SELECT 1 FROM jarvis.memberships AS membership
            WHERE membership.workshop_id = records.workshop_id
              AND membership.user_id = jarvis.current_subject()
              AND membership.can_write
        )
    )
);

CREATE POLICY records_update ON jarvis.records FOR UPDATE TO authenticated
USING (
    (workshop_id IS NULL AND owner_id = jarvis.current_subject())
    OR EXISTS (
        SELECT 1 FROM jarvis.memberships AS membership
        WHERE membership.workshop_id = records.workshop_id
          AND membership.user_id = jarvis.current_subject()
          AND membership.can_write
    )
)
WITH CHECK (
    (workshop_id IS NULL AND owner_id = jarvis.current_subject())
    OR EXISTS (
        SELECT 1 FROM jarvis.memberships AS membership
        WHERE membership.workshop_id = records.workshop_id
          AND membership.user_id = jarvis.current_subject()
          AND membership.can_write
    )
);

CREATE POLICY records_delete ON jarvis.records FOR DELETE TO authenticated
USING (
    (workshop_id IS NULL AND owner_id = jarvis.current_subject())
    OR EXISTS (
        SELECT 1 FROM jarvis.memberships AS membership
        WHERE membership.workshop_id = records.workshop_id
          AND membership.user_id = jarvis.current_subject()
          AND membership.can_write
    )
);

-- Explicit grants: neither anonymous traffic nor a BYPASSRLS service role is
-- a storage client. Membership changes remain a separate administrative action.
REVOKE ALL ON ALL TABLES IN SCHEMA jarvis FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA jarvis FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON jarvis.workshops, jarvis.memberships TO authenticated;
GRANT SELECT, INSERT, DELETE ON jarvis.records TO authenticated;
GRANT UPDATE (title, payload, revision) ON jarvis.records TO authenticated;
GRANT SELECT, INSERT ON jarvis.record_events TO authenticated;

-- Expose only the version number, never migration filenames/checksums. The
-- caller cannot replace this function because schema CREATE is not granted.
CREATE FUNCTION jarvis.schema_version() RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog
AS $$ SELECT COALESCE(max(version), 0) FROM jarvis.schema_migrations $$;
REVOKE ALL ON FUNCTION jarvis.schema_version() FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION jarvis.schema_version() TO authenticated;
