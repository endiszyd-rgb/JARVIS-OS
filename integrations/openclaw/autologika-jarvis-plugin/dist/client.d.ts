export type JarvisEnvironment = Readonly<Record<string, string | undefined>>;
export interface WorkshopOrder {
    id: number;
    vehicle_id: number | null;
    title: string;
    status: string;
    wait_state: string | null;
    opened_at: string | null;
    due_at: string | null;
    total: number;
    variable_cost: number;
}
export interface WorkshopOrdersResult {
    source: "jarvis_autologika_snapshot";
    source_path: "/api/v1/autologika/snapshot/orders";
    trust: "untrusted_tool_data";
    snapshot_created_at: string | null;
    has_more: boolean;
    orders: WorkshopOrder[];
}
export interface HomeEntityResult {
    source: "jarvis_home_assistant_readonly";
    source_path: string;
    trust: "untrusted_tool_data";
    entity_id: string;
    state: string;
    last_changed: string | null;
    last_updated: string | null;
}
export declare class JarvisBridgeError extends Error {
    readonly code: string;
    constructor(code: string);
}
export declare function validateLoopbackBaseUrl(raw: string | undefined): string;
export declare class JarvisReadonlyClient {
    private readonly env;
    private readonly fetchImpl;
    private readonly timeoutMs;
    private readonly baseUrl;
    constructor(env?: JarvisEnvironment, fetchImpl?: typeof fetch, timeoutMs?: number);
    workshopOrders(limit: number): Promise<WorkshopOrdersResult>;
    homeEntityState(entityId: string): Promise<HomeEntityResult>;
}
