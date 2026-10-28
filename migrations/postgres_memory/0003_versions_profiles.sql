-- Immutable snapshots are written by narrow trigger functions, never by runtime
-- clients. FORCE RLS remains in effect for the limited migration owner.
CREATE TABLE jarvis.memory_versions (
    memory_id uuid NOT NULL REFERENCES jarvis.memory_records(id) ON DELETE CASCADE,
    revision integer NOT NULL CHECK (revision>=0),
    content text NOT NULL,
    category text NOT NULL,
    source text NOT NULL,
    source_id text NOT NULL,
    text_hash text NOT NULL,
    indexed boolean NOT NULL,
    record_updated_at timestamptz NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY(memory_id,revision)
);
CREATE TABLE jarvis.memory_profiles (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    owner_id uuid NOT NULL,
    workshop_id uuid REFERENCES jarvis.workshops(id) ON DELETE CASCADE,
    name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100 AND btrim(name)<>''),
    instructions text NOT NULL CHECK (char_length(instructions) BETWEEN 1 AND 4000 AND btrim(instructions)<>''),
    revision integer NOT NULL DEFAULT 0 CHECK (revision>=0),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX memory_profiles_owner ON jarvis.memory_profiles(owner_id,id) WHERE workshop_id IS NULL;
CREATE INDEX memory_profiles_workshop ON jarvis.memory_profiles(workshop_id,id) WHERE workshop_id IS NOT NULL;
CREATE TABLE jarvis.memory_profile_versions (
    profile_id uuid NOT NULL REFERENCES jarvis.memory_profiles(id) ON DELETE CASCADE,
    revision integer NOT NULL CHECK (revision>=0),
    name text NOT NULL,
    instructions text NOT NULL,
    record_updated_at timestamptz NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY(profile_id,revision)
);
CREATE TABLE jarvis.memory_profile_events (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    subject uuid NOT NULL,
    profile_id uuid NOT NULL,
    event text NOT NULL CHECK (event IN ('created','updated','deleted')),
    revision integer NOT NULL CHECK (revision>=0),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX memory_profile_events_subject ON jarvis.memory_profile_events(subject,created_at,id);
ALTER TABLE jarvis.memory_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_profile_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_profile_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_profile_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_profile_events FORCE ROW LEVEL SECURITY;

CREATE POLICY memory_versions_read ON jarvis.memory_versions FOR SELECT TO authenticated
USING (EXISTS(SELECT 1 FROM jarvis.memory_records r WHERE r.id=memory_versions.memory_id));
CREATE POLICY memory_profiles_read ON jarvis.memory_profiles FOR SELECT TO authenticated USING (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS(
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_profiles.workshop_id AND m.user_id=jarvis.current_subject()));
CREATE POLICY memory_profiles_insert ON jarvis.memory_profiles FOR INSERT TO authenticated WITH CHECK (
    owner_id=jarvis.current_subject() AND (workshop_id IS NULL OR EXISTS(
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_profiles.workshop_id AND m.user_id=jarvis.current_subject() AND m.can_write)));
CREATE POLICY memory_profiles_update ON jarvis.memory_profiles FOR UPDATE TO authenticated USING (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS(
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_profiles.workshop_id AND m.user_id=jarvis.current_subject() AND m.can_write)) WITH CHECK (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS(
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_profiles.workshop_id AND m.user_id=jarvis.current_subject() AND m.can_write));
CREATE POLICY memory_profiles_delete ON jarvis.memory_profiles FOR DELETE TO authenticated USING (
    (workshop_id IS NULL AND owner_id=jarvis.current_subject()) OR EXISTS(
        SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_profiles.workshop_id AND m.user_id=jarvis.current_subject() AND m.can_write));
CREATE POLICY memory_profile_versions_read ON jarvis.memory_profile_versions FOR SELECT TO authenticated
USING (EXISTS(SELECT 1 FROM jarvis.memory_profiles p WHERE p.id=memory_profile_versions.profile_id));
CREATE POLICY memory_profile_events_read ON jarvis.memory_profile_events FOR SELECT TO authenticated USING (subject=jarvis.current_subject());
CREATE POLICY memory_profile_events_insert ON jarvis.memory_profile_events FOR INSERT TO authenticated WITH CHECK (subject=jarvis.current_subject());
DO $$
BEGIN
    EXECUTE format('CREATE POLICY memory_versions_trigger_insert ON jarvis.memory_versions FOR INSERT TO %I WITH CHECK(true)',current_user);
    EXECUTE format('CREATE POLICY memory_profile_versions_trigger_insert ON jarvis.memory_profile_versions FOR INSERT TO %I WITH CHECK(true)',current_user);
END;
$$;
REVOKE ALL ON jarvis.memory_versions,jarvis.memory_profiles,jarvis.memory_profile_versions,jarvis.memory_profile_events FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON jarvis.memory_versions,jarvis.memory_profile_versions TO authenticated;
GRANT SELECT,INSERT,DELETE ON jarvis.memory_profiles TO authenticated;
GRANT UPDATE (name,instructions,revision) ON jarvis.memory_profiles TO authenticated;
GRANT SELECT,INSERT ON jarvis.memory_profile_events TO authenticated;

CREATE FUNCTION jarvis.capture_memory_version() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP='UPDATE' THEN
        INSERT INTO jarvis.memory_versions(memory_id,revision,content,category,source,source_id,text_hash,indexed,record_updated_at)
        VALUES(OLD.id,OLD.revision,OLD.content,OLD.category,OLD.source,OLD.source_id,OLD.text_hash,OLD.embedding IS NOT NULL,OLD.updated_at)
        ON CONFLICT DO NOTHING;
    END IF;
    INSERT INTO jarvis.memory_versions(memory_id,revision,content,category,source,source_id,text_hash,indexed,record_updated_at)
    VALUES(NEW.id,NEW.revision,NEW.content,NEW.category,NEW.source,NEW.source_id,NEW.text_hash,NEW.embedding IS NOT NULL,NEW.updated_at);
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.capture_memory_version() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER memory_versions_capture AFTER INSERT OR UPDATE ON jarvis.memory_records
FOR EACH ROW EXECUTE FUNCTION jarvis.capture_memory_version();

CREATE FUNCTION jarvis.enforce_memory_profile_update() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
       OR NEW.workshop_id IS DISTINCT FROM OLD.workshop_id OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Profile identity and scope are immutable' USING ERRCODE='23514';
    END IF;
    IF NEW.revision<>OLD.revision+1 THEN
        RAISE EXCEPTION 'Profile revision must advance by one' USING ERRCODE='23514';
    END IF;
    NEW.updated_at:=statement_timestamp();
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.enforce_memory_profile_update() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER memory_profiles_update BEFORE UPDATE ON jarvis.memory_profiles
FOR EACH ROW EXECUTE FUNCTION jarvis.enforce_memory_profile_update();
CREATE FUNCTION jarvis.capture_memory_profile_version() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    INSERT INTO jarvis.memory_profile_versions(profile_id,revision,name,instructions,record_updated_at)
    VALUES(NEW.id,NEW.revision,NEW.name,NEW.instructions,NEW.updated_at);
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.capture_memory_profile_version() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER memory_profile_versions_capture AFTER INSERT OR UPDATE ON jarvis.memory_profiles
FOR EACH ROW EXECUTE FUNCTION jarvis.capture_memory_profile_version();
