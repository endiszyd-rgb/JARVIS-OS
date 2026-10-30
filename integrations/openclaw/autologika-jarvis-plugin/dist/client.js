const MAX_RESPONSE_BYTES = 256 * 1024;
const DEFAULT_TIMEOUT_MS = 4000;
const ENTITY_PATTERN = /^[a-z][a-z0-9_]*\.[a-z0-9_]+$/;
export class JarvisBridgeError extends Error {
    code;
    constructor(code) {
        super(code);
        this.code = code;
        this.name = "JarvisBridgeError";
    }
}
function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value)
        ? value
        : null;
}
function boundedText(value, max = 300) {
    return typeof value === "string" ? value.slice(0, max) : "";
}
function nullableText(value, max = 100) {
    return typeof value === "string" ? value.slice(0, max) : null;
}
function finiteNumber(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
function integer(value) {
    return typeof value === "number" && Number.isSafeInteger(value) ? value : null;
}
export function validateLoopbackBaseUrl(raw) {
    if (!raw)
        throw new JarvisBridgeError("JARVIS_CONFIG_MISSING_BASE_URL");
    let parsed;
    try {
        parsed = new URL(raw);
    }
    catch {
        throw new JarvisBridgeError("JARVIS_CONFIG_INVALID_BASE_URL");
    }
    const host = parsed.hostname.toLowerCase();
    const loopback = host === "localhost" || host === "127.0.0.1" || host === "[::1]";
    if (parsed.protocol !== "http:" || !loopback || parsed.username || parsed.password ||
        (parsed.pathname !== "/" && parsed.pathname !== "") || parsed.search || parsed.hash) {
        throw new JarvisBridgeError("JARVIS_CONFIG_LOCAL_HTTP_REQUIRED");
    }
    return parsed.origin;
}
function requiredToken(env, name) {
    const token = env[name];
    if (!token || token.length > 512 || !/^[\x21-\x7e]+$/.test(token)) {
        throw new JarvisBridgeError(`JARVIS_CONFIG_MISSING_${name}`);
    }
    return token;
}
async function boundedJson(baseUrl, path, token, timeoutMs, fetchImpl) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetchImpl(baseUrl + path, {
            method: "GET",
            redirect: "error",
            headers: { "X-Jarvis-Key": token, "Accept": "application/json" },
            signal: controller.signal,
        });
        const declared = Number(response.headers.get("content-length") || "0");
        if (declared > MAX_RESPONSE_BYTES)
            throw new JarvisBridgeError("JARVIS_RESPONSE_TOO_LARGE");
        if (!response.ok)
            throw new JarvisBridgeError(`JARVIS_HTTP_${response.status}`);
        const bytes = new Uint8Array(await response.arrayBuffer());
        if (bytes.byteLength > MAX_RESPONSE_BYTES)
            throw new JarvisBridgeError("JARVIS_RESPONSE_TOO_LARGE");
        try {
            return JSON.parse(new TextDecoder().decode(bytes));
        }
        catch {
            throw new JarvisBridgeError("JARVIS_INVALID_JSON");
        }
    }
    catch (error) {
        if (error instanceof JarvisBridgeError)
            throw error;
        if (error instanceof Error && error.name === "AbortError") {
            throw new JarvisBridgeError("JARVIS_TIMEOUT");
        }
        throw new JarvisBridgeError("JARVIS_UNAVAILABLE");
    }
    finally {
        clearTimeout(timer);
    }
}
export class JarvisReadonlyClient {
    env;
    fetchImpl;
    timeoutMs;
    baseUrl;
    constructor(env = process.env, fetchImpl = fetch, timeoutMs = DEFAULT_TIMEOUT_MS) {
        this.env = env;
        this.fetchImpl = fetchImpl;
        this.timeoutMs = timeoutMs;
        this.baseUrl = validateLoopbackBaseUrl(env.JARVIS_OPENCLAW_BASE_URL);
    }
    async workshopOrders(limit) {
        if (!Number.isInteger(limit) || limit < 1 || limit > 20) {
            throw new JarvisBridgeError("JARVIS_INVALID_LIMIT");
        }
        const token = requiredToken(this.env, "JARVIS_OPENCLAW_WORKSHOP_TOKEN");
        const raw = object(await boundedJson(this.baseUrl, `/api/v1/autologika/snapshot/orders?limit=${limit}&offset=0`, token, this.timeoutMs, this.fetchImpl));
        const data = object(raw?.data);
        if (!raw || !data || !Array.isArray(data.items)) {
            throw new JarvisBridgeError("JARVIS_INVALID_WORKSHOP_CONTRACT");
        }
        const orders = data.items.slice(0, limit).map((entry) => {
            const row = object(entry);
            if (!row || integer(row.id) === null) {
                throw new JarvisBridgeError("JARVIS_INVALID_WORKSHOP_CONTRACT");
            }
            return {
                id: integer(row.id),
                vehicle_id: integer(row.vehicle_id),
                title: boundedText(row.title),
                status: boundedText(row.status, 80),
                wait_state: nullableText(row.wait_state, 80),
                opened_at: nullableText(row.opened_at),
                due_at: nullableText(row.due_at),
                total: finiteNumber(row.total),
                variable_cost: finiteNumber(row.variable_cost),
            };
        });
        return {
            source: "jarvis_autologika_snapshot",
            source_path: "/api/v1/autologika/snapshot/orders",
            trust: "untrusted_tool_data",
            snapshot_created_at: nullableText(raw.snapshot_created_at),
            has_more: data.has_more === true,
            orders,
        };
    }
    async homeEntityState(entityId) {
        if (!ENTITY_PATTERN.test(entityId))
            throw new JarvisBridgeError("JARVIS_INVALID_ENTITY_ID");
        const allow = new Set((this.env.JARVIS_OPENCLAW_HA_ALLOWED_ENTITIES || "")
            .split(",").map(value => value.trim()).filter(Boolean));
        if (!allow.has(entityId))
            throw new JarvisBridgeError("JARVIS_ENTITY_NOT_ALLOWED");
        const token = requiredToken(this.env, "JARVIS_OPENCLAW_HOME_TOKEN");
        const path = `/api/v1/home/states/${encodeURIComponent(entityId)}`;
        const envelope = object(await boundedJson(this.baseUrl, path, token, this.timeoutMs, this.fetchImpl));
        const raw = envelope && Array.isArray(envelope.states) && envelope.states.length === 1
            ? object(envelope.states[0]) : null;
        if (!raw || boundedText(raw.entity_id, 128) !== entityId || typeof raw.state !== "string" ||
            envelope?.controls_enabled !== false) {
            throw new JarvisBridgeError("JARVIS_INVALID_HOME_CONTRACT");
        }
        return {
            source: "jarvis_home_assistant_readonly",
            source_path: path,
            trust: "untrusted_tool_data",
            entity_id: entityId,
            state: boundedText(raw.state, 200),
            last_changed: nullableText(raw.last_changed),
            last_updated: nullableText(raw.last_updated),
        };
    }
}
