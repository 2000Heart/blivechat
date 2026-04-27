/**
 * 开发/预览服务器：将用户粘贴的请求头中的 Cookie 注入到对抖音的代理请求（HTTP + WS）。
 * 仅存在于 Node 进程内存，不写 env、不写磁盘。
 */
import type { ClientRequest } from 'node:http';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { SidecarEngine, setSidecarModuleLoader } from './src/sidecar/engine';

let pastedCookie = '';
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

function mergeCookieString(existing: string, extra: string): string {
  const a = existing.trim();
  const b = extra.trim();
  if (!b) return a;
  if (!a) return b;
  return `${a}; ${b}`;
}

export function applyPastedCookieToProxyReq(proxyReq: ClientRequest): void {
  const extra = pastedCookie;
  if (!extra) return;
  const prev = proxyReq.getHeader('cookie');
  const prevStr = Array.isArray(prev) ? prev.join('; ') : (prev as string | undefined) || '';
  proxyReq.setHeader('Cookie', mergeCookieString(prevStr, extra));
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

/** Connect 中间件：POST /__api/dycast/upstream-headers */
export function douyinUpstreamCookieApiMiddleware(
  req: IncomingMessage,
  res: ServerResponse,
  next: () => void
): void {
  const url = req.url || '';
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
