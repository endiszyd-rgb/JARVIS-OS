export interface ModelOption { provider: 'demo' | 'ollama' | 'openai'; name: string; cloud: boolean }
export interface ModelCatalog { default_provider: 'demo' | 'ollama' | 'openai'; default_ollama_model: string; models: ModelOption[] }
export interface ChatSession {
  id: string; title: string; provider: 'demo' | 'ollama' | 'openai'; model_name: string
  created: number; updated: number; input_mode: 'text' | 'voice'; active_turn: string | null
  message_count?: number
}
export interface ChatMessage { id: number; role: 'user' | 'assistant'; content: string; created: number; state: 'pending' | 'completed' | 'failed'; turn_id: string }
export interface ChatReply { reply: string; session_id: string; turn_id: string; model?: string; ai_generated?: boolean; proposal?: unknown }
