-- Optional JARVIS memory feature. Foundation migration1 and an administratively
-- installed vector extension in jarvis_extensions are prerequisites. No extension
-- installation, role alteration or production bootstrap is performed here.
DO $$
BEGIN
    IF jarvis.schema_version() <> 1 THEN
        RAISE EXCEPTION 'Foundation migration1 is required';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_extension e
                   JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace
                   WHERE e.extname='vector' AND n.nspname='jarvis_extensions') THEN
        RAISE EXCEPTION 'Administrative pgvector installation is required';
    END IF;
END;
$$;

CREATE TABLE jarvis.memory_records (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    owner_id uuid NOT NULL,
    workshop_id uuid REFERENCES jarvis.workshops(id) ON DELETE CASCADE,
    content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 8000 AND btrim(content) <> ''),
    category text NOT NULL DEFAULT 'note' CHECK (category ~ '^[a-z_]{1,40}$'),
    source text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','session','import')),
    source_id text NOT NULL DEFAULT '' CHECK (char_length(source_id) <= 120),
    revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    text_hash text NOT NULL CHECK (text_hash ~ '^[0-9a-f]{64}$'),
    embedding jarvis_extensions.vector,
    embedding_namespace text,
    created_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp(),
    CHECK ((embedding IS NULL AND embedding_namespace IS NULL) OR
           (embedding IS NOT NULL AND embedding_namespace IS NOT NULL AND embedding_namespace ~ '^[0-9a-f]{64}$' AND
            jarvis_extensions.vector_dims(embedding) BETWEEN 1 AND 4096 AND
            jarvis_extensions.vector_norm(embedding) > 0))
);
CREATE INDEX memory_records_owner ON jarvis.memory_records(owner_id,id) WHERE workshop_id IS NULL;
CREATE INDEX memory_records_workshop ON jarvis.memory_records(workshop_id,id) WHERE workshop_id IS NOT NULL;
CREATE INDEX memory_records_namespace ON jarvis.memory_records(embedding_namespace) WHERE embedding IS NOT NULL;

CREATE TABLE jarvis.memory_events (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    subject uuid NOT NULL,
    event text NOT NULL CHECK (event IN ('created','updated','deleted','indexed')),
    memory_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision >= 0),
    created_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp()
);
CREATE INDEX memory_events_subject ON jarvis.memory_events(subject,created_at,id);

CREATE FUNCTION jarvis.enforce_memory_update() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP='UPDATE' THEN
      IF NEW.id IS DISTINCT FROM OLD.id OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
       OR NEW.workshop_id IS DISTINCT FROM OLD.workshop_id OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Memory identity and ownership are immutable' USING ERRCODE='23514';
      END IF;
      IF NEW.revision IS DISTINCT FROM OLD.revision+1 THEN
        RAISE EXCEPTION 'Memory revision must advance by one' USING ERRCODE='23514';
      END IF;
      IF NEW.content IS DISTINCT FROM OLD.content THEN
        NEW.embedding := NULL;
        NEW.embedding_namespace := NULL;
      END IF;
    END IF;
    NEW.text_hash := encode(sha256(convert_to(NEW.content,'UTF8')),'hex');
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.enforce_memory_update() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER memory_records_update BEFORE INSERT OR UPDATE ON jarvis.memory_records
FOR EACH ROW EXECUTE FUNCTION jarvis.enforce_memory_update();

ALTER TABLE jarvis.memory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_records FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_events FORCE ROW LEVEL SECURITY;

CREATE POLICY memory_read ON jarvis.memory_records FOR SELECT TO authenticated USING (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS (
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_records.workshop_id
        AND m.user_id=jarvis.current_subject()));
CREATE POLICY memory_insert ON jarvis.memory_records FOR INSERT TO authenticated WITH CHECK (
    owner_id=jarvis.current_subject() AND (workshop_id IS NULL OR EXISTS (
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_records.workshop_id
        AND m.user_id=jarvis.current_subject() AND m.can_write)));
CREATE POLICY memory_update ON jarvis.memory_records FOR UPDATE TO authenticated USING (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS (
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_records.workshop_id
        AND m.user_id=jarvis.current_subject() AND m.can_write)) WITH CHECK (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS (
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_records.workshop_id
        AND m.user_id=jarvis.current_subject() AND m.can_write));
CREATE POLICY memory_delete ON jarvis.memory_records FOR DELETE TO authenticated USING (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS (
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_records.workshop_id
        AND m.user_id=jarvis.current_subject() AND m.can_write));
CREATE POLICY memory_events_read ON jarvis.memory_events FOR SELECT TO authenticated
USING (subject=jarvis.current_subject());
CREATE POLICY memory_events_insert ON jarvis.memory_events FOR INSERT TO authenticated
WITH CHECK (subject=jarvis.current_subject());

REVOKE ALL ON jarvis.memory_records,jarvis.memory_events FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON jarvis.memory_schema_migrations FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT,INSERT,DELETE ON jarvis.memory_records TO authenticated;
GRANT UPDATE (content,category,source,source_id,revision,embedding,embedding_namespace) ON jarvis.memory_records TO authenticated;
GRANT SELECT,INSERT ON jarvis.memory_events TO authenticated;

CREATE FUNCTION jarvis.memory_schema_version() RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog
AS $$ SELECT COALESCE(max(version),0) FROM jarvis.memory_schema_migrations $$;
REVOKE ALL ON FUNCTION jarvis.memory_schema_version() FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION jarvis.memory_schema_version() TO authenticated;
