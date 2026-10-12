// Calls to the backend chat API (backend/app/api/chat.py).

export type Role = 'customer' | 'assistant' | 'staff'

export type ChatResponse = {
  session_id: string
  reply: string | null // null when the owner has taken over
  handed_off: boolean
}

export type ChatHistory = {
  session_id: string
  handed_off: boolean
  messages: { role: Role; content: string; created_at: string }[]
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Chat API returned ${status}`)
    this.status = status
  }
}

export async function sendMessage(
  apiBase: string,
  sessionId: string | null,
  message: string,
): Promise<ChatResponse> {
  const response = await fetch(`${apiBase}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  if (!response.ok) throw new ApiError(response.status)
  return response.json()
}

/** The conversation for a session, or null if the server doesn't know it (anymore). */
export async function fetchHistory(apiBase: string, sessionId: string): Promise<ChatHistory | null> {
  const response = await fetch(`${apiBase}/api/chat/${encodeURIComponent(sessionId)}`)
  if (response.status === 404) return null
  if (!response.ok) throw new ApiError(response.status)
  return response.json()
}
