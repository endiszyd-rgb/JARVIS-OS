-- Pin a profile revision; deleting a profile invalidates use of old sessions,
-- while sessions remain independently deletable. No cascade or hidden repinning.
ALTER TABLE jarvis.memory_sessions
    ADD COLUMN profile_id uuid,
    ADD COLUMN profile_revision integer,
    ADD CONSTRAINT memory_session_profile_pair CHECK (
        (profile_id IS NULL AND profile_revision IS NULL) OR
        (profile_id IS NOT NULL AND profile_revision IS NOT NULL AND profile_revision>=0));
CREATE FUNCTION jarvis.enforce_session_profile_pin() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.profile_id IS DISTINCT FROM OLD.profile_id OR NEW.profile_revision IS DISTINCT FROM OLD.profile_revision THEN
        RAISE EXCEPTION 'Session profile is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION jarvis.enforce_session_profile_pin() FROM PUBLIC,anon,authenticated,service_role;
CREATE TRIGGER memory_session_profile_pin BEFORE UPDATE ON jarvis.memory_sessions
FOR EACH ROW EXECUTE FUNCTION jarvis.enforce_session_profile_pin();
