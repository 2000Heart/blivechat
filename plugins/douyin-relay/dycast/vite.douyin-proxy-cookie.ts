/**
 * 开发/预览服务器：将用户粘贴的请求头中的 Cookie 注入到对抖音的代理请求（HTTP + WS）。
 * 仅存在于 Node 进程内存，不写 env、不写磁盘。
 */
import type { ClientRequest } from 'node:http';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { SidecarEngine, setSidecarModuleLoader } from './src/sidecar/engine';
import {
  createCookieLoginSessionFromEnv,
  isLoopbackAddress
} from './src/sidecar/cookie-login-browser';
import type { CookieLoginSession } from './src/sidecar/cookie-login-session';

let pastedCookie = '';
let socketProxyHost = 'webcast100-ws-web-lq.douyin.com';

export function socketProxyTarget(): string {
  return `wss://${socketProxyHost}`;
}

export function setSocketProxyHost(host: string): void {
  const trimmed = host.trim().replace(/^wss?:\/\//i, '').replace(/\/.*$/, '').replace(/\/+$/, '');
  if (trimmed) socketProxyHost = trimmed;
}
type ControlAction = 'none' | 'connect' | 'disconnect';
type PreviewClient = { id: string; res: ServerResponse };

interface SidecarControlState {
  commandVersion: number;
  action: ControlAction;
  roomNum: string;
  relayUrl: string;
  rawHeaders: string;
  autoReconnect: boolean;
  status: Record<string, unknown>;
  updatedAt: number;
}

const controlState: SidecarControlState = {
  commandVersion: 0,
  action: 'none',
  roomNum: '',
  relayUrl: '',
  rawHeaders: '',
  autoReconnect: true,
  status: {},
  updatedAt: Date.now()
};

const sidecarEngine = new SidecarEngine(400);
const previewClients = new Map<string, PreviewClient>();
const sidecarOrigin = 'http://127.0.0.1:5173';
let cookieLoginSession: CookieLoginSession | null = null;

function getCookieLoginSession(): CookieLoginSession {
  if (!cookieLoginSession) {
    cookieLoginSession = createCookieLoginSessionFromEnv();
  }
  return cookieLoginSession;
}

function requestPathname(url: string): string {
  const q = url.indexOf('?');
  return q === -1 ? url : url.slice(0, q);
}

function isLoginMode(mode: unknown): mode is 'interactive' | 'silent' {
  return mode === 'interactive' || mode === 'silent';
}

export function setSidecarSsrModuleLoader(loader: ((id: string) => Promise<any>) | null): void {
  setSidecarModuleLoader(loader);
}

function writeSse(res: ServerResponse, event: string, data: unknown): void {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

function broadcastPreview(event: string, data: unknown): void {
  for (const client of previewClients.values()) {
    writeSse(client.res, event, data);
  }
}

sidecarEngine.on('event', payload => {
  broadcastPreview('dycast', payload);
});

/** 从整段 Request Headers 或纯 Cookie 字符串解析出 Cookie 值 */
export function parseCookieFromPaste(raw: string): string {
  const t = raw.trim();
  if (!t) return '';
  for (const line of t.split(/\r?\n/)) {
    const m = line.match(/^\s*cookie\s*:\s*(.+)$/i);
    if (m) return m[1].trim();
  }
  return t;
}

export function setPastedCookieFromRaw(raw: string): void {
  pastedCookie = parseCookieFromPaste(raw);
}

export function getPastedCookie(): string {
  return pastedCookie;
}

function parseCookiePairs(header: string): Map<string, string> {
  const jar = new Map<string, string>();
  for (const part of header.split(';')) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const eq = trimmed.indexOf('=');
    if (eq <= 0) continue;
    jar.set(trimmed.slice(0, eq), trimmed.slice(eq + 1));
  }
  return jar;
}

/** 登录 Cookie 覆盖页面里同名的 Cookie，页面独有的项保留。 */
export function replacePageCookie(pageCookie: string, loginCookie: string): string {
  const jar = parseCookiePairs(pageCookie);
  for (const [name, value] of parseCookiePairs(loginCookie)) {
    jar.set(name, value);
  }
  return [...jar.entries()].map(([name, value]) => `${name}=${value}`).join('; ');
}

export function applyPastedCookieToProxyReq(proxyReq: ClientRequest): void {
  const extra = pastedCookie;
  if (!extra) return;
  const prev = proxyReq.getHeader('cookie');
  const prevStr = Array.isArray(prev) ? prev.join('; ') : (prev as string | undefined) || '';
  proxyReq.setHeader('Cookie', replacePageCookie(prevStr, extra));
}

function handleUpstreamHeadersPost(req: IncomingMessage, res: ServerResponse): void {
  let body = '';
  req.on('data', chunk => {
    body += chunk;
  });
  req.on('end', () => {
    try {
      const json = JSON.parse(body || '{}') as { raw?: string };
      setPastedCookieFromRaw(typeof json.raw === 'string' ? json.raw : '');
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.statusCode = 200;
      res.end(
        JSON.stringify({
          ok: true,
          cookieLength: getPastedCookie().length
        })
      );
    } catch {
      res.statusCode = 400;
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.end(JSON.stringify({ ok: false, error: 'invalid_json' }));
    }
  });
}

function jsonResponse(res: ServerResponse, statusCode: number, body: Record<string, unknown>): void {
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(body));
}

function readJsonBody(req: IncomingMessage, done: (obj: any) => void, failed: () => void): void {
  let body = '';
  req.on('data', chunk => {
    body += chunk;
  });
  req.on('end', () => {
    try {
      done(JSON.parse(body || '{}'));
    } catch {
      failed();
    }
  });
}

function handleControlStatus(res: ServerResponse): void {
  const engine = sidecarEngine.getSnapshot();
  jsonResponse(res, 200, {
    ok: true,
    ...controlState,
    engine,
    cookieLength: getPastedCookie().length
  });
}

function handleControlConnect(req: IncomingMessage, res: ServerResponse): void {
  readJsonBody(
    req,
    (obj: { roomNum?: string; relayUrl?: string; rawHeaders?: string; autoReconnect?: boolean }) => {
      const roomNum = String(obj.roomNum || '').trim();
      const relayUrl = String(obj.relayUrl || '').trim();
      const rawHeaders = typeof obj.rawHeaders === 'string' ? obj.rawHeaders : '';
      if (!roomNum || !relayUrl) {
        jsonResponse(res, 400, { ok: false, error: 'roomNum and relayUrl are required' });
        return;
      }
      setPastedCookieFromRaw(rawHeaders);
      controlState.commandVersion += 1;
      controlState.action = 'connect';
      controlState.roomNum = roomNum;
      controlState.relayUrl = relayUrl;
      controlState.rawHeaders = rawHeaders;
      controlState.autoReconnect = obj.autoReconnect !== false;
      controlState.updatedAt = Date.now();
      sidecarEngine
        .connect(
          {
            roomNum,
            relayUrl,
            rawHeaders,
            autoReconnect: controlState.autoReconnect
          },
          sidecarOrigin
        )
        .then(() => {
          handleControlStatus(res);
        })
        .catch(err => {
          const detail =
            err instanceof Error
              ? { message: err.message, stack: err.stack || '' }
              : { message: String(err || 'connect failed'), stack: '' };
          jsonResponse(res, 500, {
            ok: false,
            error: detail.message,
            detail
          });
        });
    },
    () => jsonResponse(res, 400, { ok: false, error: 'invalid_json' })
  );
}

function handleControlDisconnect(req: IncomingMessage, res: ServerResponse): void {
  readJsonBody(
    req,
    () => {
      controlState.commandVersion += 1;
      controlState.action = 'disconnect';
      controlState.updatedAt = Date.now();
      sidecarEngine.disconnect('disconnect by control');
      handleControlStatus(res);
    },
    () => jsonResponse(res, 400, { ok: false, error: 'invalid_json' })
  );
}

function handleControlReport(req: IncomingMessage, res: ServerResponse): void {
  readJsonBody(
    req,
    (obj: Record<string, unknown>) => {
      controlState.status = obj || {};
      controlState.updatedAt = Date.now();
      handleControlStatus(res);
    },
    () => jsonResponse(res, 400, { ok: false, error: 'invalid_json' })
  );
}

function handlePreviewSnapshot(res: ServerResponse): void {
  jsonResponse(res, 200, {
    ok: true,
    engine: sidecarEngine.getSnapshot(),
    events: sidecarEngine.getPreviewBuffer()
  });
}

function handlePreviewSse(req: IncomingMessage, res: ServerResponse): void {
  const clientId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  previewClients.set(clientId, { id: clientId, res });
  writeSse(res, 'ready', {
    ok: true,
    id: clientId,
    engine: sidecarEngine.getSnapshot()
  });
  req.on('close', () => {
    previewClients.delete(clientId);
  });
}

function handleLoginApi(req: IncomingMessage, res: ServerResponse): boolean {
  const url = requestPathname(req.url || '');
  const isStart = url === '/__api/dycast/login/start' && req.method === 'POST';
  const isStatus = url === '/__api/dycast/login/status' && req.method === 'GET';
  const isConsume = url === '/__api/dycast/login/consume' && req.method === 'POST';
  const isCancel = url === '/__api/dycast/login/cancel' && req.method === 'POST';
  if (!isStart && !isStatus && !isConsume && !isCancel) return false;

  if (!isLoopbackAddress(req.socket?.remoteAddress)) {
    jsonResponse(res, 403, { ok: false, error: 'forbidden' });
    return true;
  }

  const session = getCookieLoginSession();
  if (isStatus) {
    jsonResponse(res, 200, { ...session.status(false) });
    return true;
  }
  if (isConsume) {
    const cookie = session.consumeCookie();
    jsonResponse(res, 200, { ok: true, cookie, cookieLength: cookie.length });
    return true;
  }
  if (isCancel) {
    session.cancel();
    jsonResponse(res, 200, { ...session.status(false) });
    return true;
  }

  readJsonBody(
    req,
    (obj: { mode?: unknown }) => {
      if (!isLoginMode(obj?.mode)) {
        jsonResponse(res, 400, { ok: false, error: 'invalid_mode' });
        return;
      }
      const result = session.start(obj.mode);
      jsonResponse(res, result.status, { ...result.body });
    },
    () => jsonResponse(res, 400, { ok: false, error: 'invalid_json' })
  );
  return true;
}

/** Connect 中间件：POST /__api/dycast/upstream-headers */
export function douyinUpstreamCookieApiMiddleware(
  req: IncomingMessage,
  res: ServerResponse,
  next: () => void
): void {
  if (handleLoginApi(req, res)) return;
  const url = req.url || '';
  if (url.startsWith('/__api/dycast/socket-host') && req.method === 'POST') {
    readJsonBody(
      req,
      (obj: { host?: unknown }) => {
        setSocketProxyHost(typeof obj?.host === 'string' ? obj.host : '');
        jsonResponse(res, 200, { ok: true });
      },
      () => jsonResponse(res, 400, { ok: false, error: 'invalid_json' })
    );
    return;
  }
  if (url.startsWith('/__api/dycast/control/status') && req.method === 'GET') {
    handleControlStatus(res);
    return;
  }
  if (url.startsWith('/__api/dycast/control/connect') && req.method === 'POST') {
    handleControlConnect(req, res);
    return;
  }
  if (url.startsWith('/__api/dycast/control/disconnect') && req.method === 'POST') {
    handleControlDisconnect(req, res);
    return;
  }
  if (url.startsWith('/__api/dycast/control/report') && req.method === 'POST') {
    handleControlReport(req, res);
    return;
  }
  if (url.startsWith('/__api/dycast/preview/snapshot') && req.method === 'GET') {
    handlePreviewSnapshot(res);
    return;
  }
  if (url.startsWith('/__api/dycast/preview/sse') && req.method === 'GET') {
    handlePreviewSse(req, res);
    return;
  }
  if (!url.startsWith('/__api/dycast/upstream-headers')) {
    next();
    return;
  }
  if (req.method === 'OPTIONS') {
    res.statusCode = 204;
    res.end();
    return;
  }
  if (req.method !== 'POST') {
    res.statusCode = 405;
    res.end();
    return;
  }
  handleUpstreamHeadersPost(req, res);
}
