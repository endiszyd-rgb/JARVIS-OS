-- Account-private text sessions in one immutable private/workshop data scope.
-- Expiration limits use of messages; metadata remains deletable by the owner.
CREATE TABLE jarvis.memory_sessions (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    owner_id uuid NOT NULL,
    workshop_id uuid REFERENCES jarvis.workshops(id) ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider IN ('ollama','openai')),
    model_name text NOT NULL CHECK (char_length(model_name) BETWEEN 1 AND 150),
    revision integer NOT NULL DEFAULT 0 CHECK (revision BETWEEN 0 AND 64),
    expires_at timestamptz NOT NULL,
    active_turn uuid,
    active_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp(),
    CHECK ((active_turn IS NULL AND active_until IS NULL) OR
           (active_turn IS NOT NULL AND active_until IS NOT NULL)),
    CHECK (expires_at > created_at AND expires_at <= created_at + interval '24 hours')
);
CREATE INDEX memory_sessions_owner ON jarvis.memory_sessions(owner_id,created_at,id);
CREATE TABLE jarvis.memory_turns (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES jarvis.memory_sessions(id) ON DELETE CASCADE,
    sequence integer NOT NULL CHECK (sequence BETWEEN 1 AND 64),
    user_text text NOT NULL CHECK (char_length(user_text) BETWEEN 1 AND 8000 AND btrim(user_text)<>''),
    assistant_text text NOT NULL CHECK (char_length(assistant_text) BETWEEN 1 AND 32000 AND btrim(assistant_text)<>''),
    memory_refs jsonb NOT NULL CHECK (jsonb_typeof(memory_refs)='array' AND
        jsonb_array_length(memory_refs)<=20 AND octet_length(memory_refs::text)<=4096),
    created_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp(),
    UNIQUE(session_id,sequence)
);
CREATE TABLE jarvis.memory_session_events (
    id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    subject uuid NOT NULL,
    session_id uuid NOT NULL,
    event text NOT NULL CHECK (event IN ('created','completed','deleted')),
    revision integer NOT NULL CHECK (revision BETWEEN 0 AND 64),
    created_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp()
);
CREATE INDEX memory_session_events_subject ON jarvis.memory_session_events(subject,created_at,id);
CREATE FUNCTION jarvis.enforce_memory_session_update() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
       OR NEW.workshop_id IS DISTINCT FROM OLD.workshop_id OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.model_name IS DISTINCT FROM OLD.model_name OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Session identity, scope, model and expiry are immutable' USING ERRCODE='23514';
    END IF;
    IF NEW.revision<>OLD.revision AND (NEW.revision<>OLD.revision+1 OR OLD.active_turn IS NULL
       OR NEW.active_turn IS NOT NULL) THEN
        RAISE EXCEPTION 'Session revision requires completion of one claimed turn' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.enforce_memory_session_update() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER memory_sessions_update BEFORE UPDATE ON jarvis.memory_sessions
FOR EACH ROW EXECUTE FUNCTION jarvis.enforce_memory_session_update();
ALTER TABLE jarvis.memory_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_turns FORCE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_session_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis.memory_session_events FORCE ROW LEVEL SECURITY;
-- Workshop conversation text is still account-private, even to another member.
CREATE POLICY memory_sessions_owner ON jarvis.memory_sessions FOR ALL TO authenticated
USING (owner_id=jarvis.current_subject() AND (workshop_id IS NULL OR EXISTS (
    SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_sessions.workshop_id AND m.user_id=jarvis.current_subject())))
WITH CHECK (owner_id=jarvis.current_subject() AND (workshop_id IS NULL OR EXISTS (
    SELECT 1 FROM jarvis.memberships m WHERE m.workshop_id=memory_sessions.workshop_id AND m.user_id=jarvis.current_subject())));
CREATE POLICY memory_turns_read ON jarvis.memory_turns FOR SELECT TO authenticated USING (EXISTS (
    SELECT 1 FROM jarvis.memory_sessions s WHERE s.id=memory_turns.session_id AND s.expires_at>statement_timestamp()));
CREATE POLICY memory_turns_insert ON jarvis.memory_turns FOR INSERT TO authenticated WITH CHECK (EXISTS (
    SELECT 1 FROM jarvis.memory_sessions s WHERE s.id=memory_turns.session_id AND s.expires_at>statement_timestamp()
        AND s.active_turn=memory_turns.id AND s.active_until>statement_timestamp() AND memory_turns.sequence=s.revision+1));
CREATE POLICY memory_session_events_owner ON jarvis.memory_session_events FOR ALL TO authenticated
USING (subject=jarvis.current_subject()) WITH CHECK (subject=jarvis.current_subject());
REVOKE ALL ON jarvis.memory_sessions,jarvis.memory_turns,jarvis.memory_session_events FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT,INSERT,DELETE ON jarvis.memory_sessions TO authenticated;
GRANT UPDATE (revision,active_turn,active_until) ON jarvis.memory_sessions TO authenticated;
GRANT SELECT,INSERT ON jarvis.memory_turns TO authenticated;
GRANT SELECT,INSERT ON jarvis.memory_session_events TO authenticated;
