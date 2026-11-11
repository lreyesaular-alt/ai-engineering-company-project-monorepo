import { api } from "./api";

const TELEMETRY_ENDPOINT = (
  process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT ||
  "http://127.0.0.1:8000/telemetry/events"
).replace(/\/$/, "");

const SCHEMA_VERSION = "1.0.0";

const MAX_BATCH_SIZE = 20;
const FLUSH_INTERVAL = 10_000;
const MAX_QUEUE_SIZE = 100;
const MAX_RETRIES = 3;
const RETRY_BASE_DELAY = 1_000;
const MAX_RETRY_DELAY = 8_000;

type TelemetryProperties = Record<string, unknown>;

type TelemetryEvent = {
  eventId: string;
  timestamp: string;
  sessionId: string | null;
  userId: string | null;
  event_type: string;
  schemaVersion: string;
  requestId: string | null;
  properties: TelemetryProperties;
};

let queue: TelemetryEvent[] = [];
let sessionId: string | null = null;
let userId: string | null = null;
let userLoaded = false;
let flushTimer: ReturnType<typeof setInterval> | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let initialized = false;
let isFlushing = false;
let retryCount = 0;

function getSessionId(): string {
  if (sessionId) return sessionId;

  const storageKey = "telemetry_session_id";

  try {
    sessionId = sessionStorage.getItem(storageKey);

    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem(storageKey, sessionId);
    }
  } catch {
    sessionId = crypto.randomUUID();
  }

  return sessionId;
}

async function loadAuthenticatedUser(): Promise<void> {
  if (userLoaded || typeof window === "undefined") return;

  userLoaded = true;

  try {
    const response = await api("/auth/me");
    const user = await response.json();

    userId = user?.id != null ? String(user.id) : null;
  } catch {
    userId = null;
  }
}

function createEventId(): string {
  return crypto.randomUUID();
}

function createEvent(
  eventType: string,
  properties: TelemetryProperties,
): TelemetryEvent {
  return {
    eventId: createEventId(),
    timestamp: new Date().toISOString(),
    sessionId: getSessionId(),
    userId,
    event_type: eventType,
    schemaVersion: SCHEMA_VERSION,
    requestId: crypto.randomUUID(),
    properties,
  };
}

function scheduleRetry(): void {
  if (retryTimer) return;

  const delay = Math.min(
    RETRY_BASE_DELAY * 2 ** (retryCount - 1),
    MAX_RETRY_DELAY,
  );

  retryTimer = setTimeout(() => {
    retryTimer = null;
    void flushTelemetry();
  }, delay);
}

export function track(
  eventType: string,
  properties: TelemetryProperties = {},
): void {
  if (typeof window === "undefined") return;

  const event = createEvent(eventType, properties);

  if (queue.length >= MAX_QUEUE_SIZE) {
    queue.shift();
  }

  queue.push(event);

  if (queue.length >= MAX_BATCH_SIZE) {
    void flushTelemetry();
  }
}

export async function flushTelemetry(): Promise<void> {
  if (
    typeof window === "undefined" ||
    isFlushing ||
    queue.length === 0 ||
    retryTimer
  ) {
    return;
  }

  isFlushing = true;
  const batch = queue.splice(0, MAX_BATCH_SIZE);

  try {
    const response = await fetch(TELEMETRY_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    });

    if (!response.ok) {
      throw new Error(`Telemetry request failed: ${response.status}`);
    }

    retryCount = 0;
  } catch (error) {
    queue = [...batch, ...queue].slice(0, MAX_QUEUE_SIZE);
    retryCount += 1;

    console.warn(
      "Telemetry delivery failed. Events queued for retry.",
      error,
    );

    if (retryCount <= MAX_RETRIES) {
      scheduleRetry();
    } else {
      console.error(
        "Maximum telemetry retries reached. Events remain queued.",
      );
      retryCount = 0;
    }
  } finally {
    isFlushing = false;
  }
}

function flushOnUnload(): void {
  if (queue.length === 0 || typeof navigator === "undefined") return;

  while (queue.length > 0) {
    const batch = queue.splice(0, MAX_BATCH_SIZE);
    const blob = new Blob(
      [JSON.stringify({ events: batch })],
      { type: "application/json" },
    );

    if (!navigator.sendBeacon(TELEMETRY_ENDPOINT, blob)) {
      queue = [...batch, ...queue].slice(0, MAX_QUEUE_SIZE);
      break;
    }
  }
}

export function initializeTelemetry(): () => void {
  if (typeof window === "undefined" || initialized) {
    return () => {};
  }

  initialized = true;
  getSessionId();
  void loadAuthenticatedUser();

  flushTimer = setInterval(() => {
    void flushTelemetry();
  }, FLUSH_INTERVAL);

  const handleVisibilityChange = () => {
    if (document.visibilityState === "hidden") {
      flushOnUnload();
    }
  };

  document.addEventListener("visibilitychange", handleVisibilityChange);
  window.addEventListener("pagehide", flushOnUnload);

  return () => {
    if (flushTimer) {
      clearInterval(flushTimer);
      flushTimer = null;
    }

    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }

    document.removeEventListener(
      "visibilitychange",
      handleVisibilityChange,
    );
    window.removeEventListener("pagehide", flushOnUnload);

    initialized = false;
  };
}

