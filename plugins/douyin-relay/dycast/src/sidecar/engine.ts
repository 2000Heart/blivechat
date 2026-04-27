import { EventEmitter } from 'events';
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { createRequire } from 'module';
import { chromium, type Browser, type Page } from 'playwright-core';
import { RelayCast } from '../core/relay';
interface DyLiveInfo {
  roomNum?: string;
  roomId: string;
  uniqueId: string;
  avatar: string;
  cover: string;
  nickname: string;
  title: string;
  status: number;
}

interface DyMessage {
  id?: string;
  method?: string;
  [key: string]: unknown;
}


type EngineState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error';

export interface EngineConnectPayload {
  roomNum: string;
  relayUrl: string;
  rawHeaders: string;
  autoReconnect: boolean;
}

export interface EngineSnapshot {
  state: EngineState;
  roomNum: string;
  relayUrl: string;
  autoReconnect: boolean;
  startedAt: number;
  updatedAt: number;
  lastMessageAt: number;
  lastError: string;
  connectStatus: 0 | 1 | 2 | 3;
  relayStatus: 0 | 1 | 2 | 3;
  relayConnected: boolean;
  previewBufferSize: number;
}

type EngineEvent =
  | { type: 'state_change'; payload: Record<string, unknown> }
  | { type: 'live_info'; payload: DyLiveInfo }
  | { type: 'messages'; payload: DyMessage[] };

type RuntimeDyCastCtor = new (roomNum: string) => {
  on: (event: string, listener: (...args: any[]) => void) => void;
  connect: () => Promise<void> | void;
  close: (code?: number, reason?: string) => void;
  getLiveInfo: () => DyLiveInfo;
};
type ModuleLoader = (id: string) => Promise<any>;
type BrowserConnectorEvent =
  | { type: 'open'; payload?: DyLiveInfo }
  | { type: 'reconnecting'; payload?: { count?: number; code?: number; reason?: string } }
  | { type: 'reconnect'; payload?: Record<string, unknown> }
  | { type: 'error'; payload?: { message?: string } }
  | { type: 'close'; payload?: { code?: number; reason?: string } }
  | { type: 'message'; payload?: DyMessage[] };

let runtimeReady = false;
let cachedCtor: RuntimeDyCastCtor | null = null;
const nodeRequire = createRequire(import.meta.url);
let moduleLoader: ModuleLoader | null = null;

export function setSidecarModuleLoader(loader: ModuleLoader | null): void {
  moduleLoader = loader;
}

function ensureNodeRuntime(origin: string): void {
  if (runtimeReady) return;
  const g = globalThis as any;
  const url = new URL(origin);
  const runtimeLocation = {
    origin: `${url.protocol}//${url.host}`,
    protocol: url.protocol,
    host: url.host,
    hostname: url.hostname,
    port: url.port,
    href: url.toString()
  };
  const runtimeNavigator = {
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    appVersion:
      '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    appCodeName: 'Mozilla'
  };
  const runtimeDocument = {
    cookie: '',
    referrer: '',
    visibilityState: 'visible',
    hidden: false,
    addEventListener: () => {},
    removeEventListener: () => {},
    createEvent: () => ({ initEvent: () => {} })
  };
  if (!g.WebSocket) {
    try {
      const wsMod = nodeRequire('ws');
      g.WebSocket = wsMod.WebSocket || wsMod;
    } catch {
      // Keep undefined and let upstream error message surface.
    }
  }
  const mssdkPath = path.join(process.cwd(), 'public', 'mssdk.js');
  const code = fs.readFileSync(mssdkPath, 'utf-8');
  const sandboxWindow = {
    byted_acrawler: undefined as any,
    location: runtimeLocation,
    navigator: runtimeNavigator,
    document: runtimeDocument,
    addEventListener: () => {},
    removeEventListener: () => {},
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval
  } as any;
  const sandbox = {
    window: sandboxWindow,
    self: sandboxWindow,
    document: runtimeDocument,
    location: runtimeLocation,
    navigator: runtimeNavigator,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    require: nodeRequire,
    module: { exports: {} },
    exports: {}
  } as any;
  vm.runInNewContext(code, sandbox, { filename: 'mssdk.js' });
  const bytedAcrawler =
    sandboxWindow?.byted_acrawler && typeof sandboxWindow.byted_acrawler.frontierSign === 'function'
      ? sandboxWindow.byted_acrawler
      : null;
  if (bytedAcrawler) {
    g.__dy_frontierSign = (payload: Record<string, unknown>) => bytedAcrawler.frontierSign(payload);
    g.byted_acrawler = bytedAcrawler;
    if (!g.window || typeof g.window !== 'object') g.window = {};
    g.window.byted_acrawler = bytedAcrawler;
  }
  runtimeReady = true;
}

async function getDyCastCtor(origin: string): Promise<RuntimeDyCastCtor> {
  ensureNodeRuntime(origin);
  if (cachedCtor) return cachedCtor;
  let mod: any;
  if (moduleLoader) {
    mod = await moduleLoader('/src/core/dycast.ts');
  } else {
    const loader = new Function('p', 'return import(p);') as (p: string) => Promise<any>;
    mod = await loader(new URL('../core/dycast.ts', import.meta.url).href);
  }
  cachedCtor = mod.DyCast as RuntimeDyCastCtor;
  return cachedCtor;
}

function resolveBrowserExecutablePath(): string | null {
  const g = globalThis as any;
  const envPath = String(g?.process?.env?.CHROME_PATH || '').trim();
  if (envPath && fs.existsSync(envPath)) return envPath;
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium'
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

class BrowserDycastConnector {
  private browser: Browser | null = null;
  private page: Page | null = null;
  private readonly sidecarOrigin: string;

  constructor(sidecarOrigin: string) {
    this.sidecarOrigin = sidecarOrigin;
  }

  public async start(roomNum: string, onEvent: (evt: BrowserConnectorEvent) => void): Promise<void> {
    const executablePath = resolveBrowserExecutablePath();
    if (!executablePath) {
      throw new Error('未找到可用浏览器可执行文件，请设置 CHROME_PATH');
    }
    this.browser = await chromium.launch({
      executablePath,
      headless: true
    });
    const context = await this.browser.newContext();
    this.page = await context.newPage();
    await this.page.exposeBinding('__dycastSidecarEvent', (_source, evt: BrowserConnectorEvent) => {
      onEvent(evt);
    });
    await this.page.goto(this.sidecarOrigin, { waitUntil: 'domcontentloaded' });
    await this.page.evaluate(async (targetRoomNum: string) => {
      const emit = (evt: BrowserConnectorEvent) => {
        const fn = (window as any).__dycastSidecarEvent;
        if (typeof fn === 'function') fn(evt);
      };
      const load = new Function('p', 'return import(p);') as (p: string) => Promise<any>;
      const mod = await load('/src/core/dycast.ts');
      const cast = new mod.DyCast(targetRoomNum);
      (window as any).__dycastSidecarCast = cast;
      cast.on('open', (_ev: Event, info?: DyLiveInfo) => emit({ type: 'open', payload: info }));
      cast.on('reconnecting', (count?: number, code?: number, reason?: string) =>
        emit({ type: 'reconnecting', payload: { count, code, reason } })
      );
      cast.on('reconnect', () => emit({ type: 'reconnect', payload: {} }));
      cast.on('error', (err: Error) => emit({ type: 'error', payload: { message: err?.message || 'cast error' } }));
      cast.on('close', (code: number, reason: string) => emit({ type: 'close', payload: { code, reason } }));
      cast.on('message', (msgs: DyMessage[]) => emit({ type: 'message', payload: msgs }));
      await cast.connect();
    }, roomNum);
  }

  public async stop(reason = 'disconnect by control'): Promise<void> {
    if (this.page) {
      try {
        await this.page.evaluate((r: string) => {
          const cast = (window as any).__dycastSidecarCast;
          if (cast && typeof cast.close === 'function') {
            cast.close(1000, r);
          }
        }, reason);
      } catch {
        // ignore
      }
    }
    if (this.browser) {
      try {
        await this.browser.close();
      } catch {
        // ignore
      }
    }
    this.page = null;
    this.browser = null;
  }
}

export class SidecarEngine extends EventEmitter {
  private readonly previewBufferLimit: number;
  private previewBuffer: EngineEvent[] = [];
  private cast: InstanceType<RuntimeDyCastCtor> | undefined;
  private browserConnector: BrowserDycastConnector | undefined;
  private relay: RelayCast | undefined;
  private snapshot: EngineSnapshot = {
    state: 'idle',
    roomNum: '',
    relayUrl: '',
    autoReconnect: true,
    startedAt: Date.now(),
    updatedAt: Date.now(),
    lastMessageAt: 0,
    lastError: '',
    connectStatus: 0,
    relayStatus: 0,
    relayConnected: false,
    previewBufferSize: 0
  };

  constructor(previewBufferLimit = 300) {
    super();
    this.previewBufferLimit = Math.max(50, previewBufferLimit);
  }

  public getSnapshot(): EngineSnapshot {
    return { ...this.snapshot };
  }

  public getPreviewBuffer(): EngineEvent[] {
    return this.previewBuffer.slice();
  }

  public async connect(payload: EngineConnectPayload, sidecarOrigin: string): Promise<EngineSnapshot> {
    const roomNum = String(payload.roomNum || '').trim();
    const relayUrl = String(payload.relayUrl || '').trim();
    if (!roomNum || !relayUrl) {
      throw new Error('roomNum and relayUrl are required');
    }
    this.snapshot.roomNum = roomNum;
    this.snapshot.relayUrl = relayUrl;
    this.snapshot.autoReconnect = payload.autoReconnect !== false;
    (globalThis as any).__dy_cookie = String(payload.rawHeaders || '');
    ensureNodeRuntime(sidecarOrigin);
    await this.ensureRelay(relayUrl);
    this.setState('connecting');

    if (this.cast) {
      this.cast.close(1000, 'switch room');
      this.cast = undefined;
    }
    if (this.browserConnector) {
      await this.browserConnector.stop('switch room');
      this.browserConnector = undefined;
    }

    this.browserConnector = new BrowserDycastConnector(sidecarOrigin);
    await this.browserConnector.start(roomNum, evt => this.handleBrowserEvent(evt));
    return this.getSnapshot();
  }

  public disconnect(reason = 'disconnect by control'): EngineSnapshot {
    if (this.cast) {
      this.cast.close(1000, reason);
      this.cast = undefined;
    }
    if (this.relay) {
      this.relay.close(1000, reason);
      this.relay = undefined;
    }
    if (this.browserConnector) {
      void this.browserConnector.stop(reason);
      this.browserConnector = undefined;
    }
    this.snapshot.connectStatus = 3;
    this.snapshot.relayStatus = 3;
    this.snapshot.relayConnected = false;
    this.setState('disconnected');
    return this.getSnapshot();
  }

  private async ensureRelay(relayUrl: string): Promise<void> {
    if (this.relay && this.snapshot.relayUrl === relayUrl && this.relay.isConnected()) {
      return;
    }
    if (this.relay) {
      this.relay.close(1000, 'replace relay');
      this.relay = undefined;
    }
    const relay = new RelayCast(relayUrl);
    relay.on('open', () => {
      this.snapshot.relayStatus = 1;
      this.snapshot.relayConnected = true;
      this.touch();
      this.emitStateEvent();
      if (this.cast) {
        relay.send(JSON.stringify(this.cast.getLiveInfo()));
      }
    });
    relay.on('close', () => {
      this.snapshot.relayStatus = 3;
      this.snapshot.relayConnected = false;
      this.touch();
      this.emitStateEvent();
    });
    relay.on('error', ev => {
      this.snapshot.relayStatus = 2;
      this.snapshot.relayConnected = false;
      this.snapshot.lastError = ev?.message || 'relay error';
      this.touch();
      this.setState('error');
    });
    relay.connect();
    this.relay = relay;
    this.snapshot.relayStatus = 1;
    this.snapshot.relayConnected = relay.isConnected();
    this.touch();
  }

  private bindCast(cast: InstanceType<RuntimeDyCastCtor>): void {
    cast.on('open', (_ev: Event, info?: DyLiveInfo) => {
      this.snapshot.connectStatus = 1;
      this.setState('connected');
      if (info) this.pushEvent({ type: 'live_info', payload: info });
    });
    cast.on('reconnecting', () => {
      this.snapshot.connectStatus = 1;
      this.setState('reconnecting');
    });
    cast.on('reconnect', () => {
      this.snapshot.connectStatus = 1;
      this.setState('connected');
    });
    cast.on('error', (err: Error) => {
      this.snapshot.connectStatus = 2;
      this.snapshot.lastError = err?.message || 'cast error';
      this.setState('error');
    });
    cast.on('close', (_code: number, reason: string) => {
      this.snapshot.connectStatus = 3;
      if (reason) this.snapshot.lastError = reason;
      this.setState('disconnected');
    });
    cast.on('message', (msgs: DyMessage[]) => {
      this.snapshot.lastMessageAt = Date.now();
      this.touch();
      this.pushEvent({ type: 'messages', payload: msgs });
      if (this.relay && this.relay.isConnected()) {
        this.relay.send(JSON.stringify(msgs));
      }
    });
  }

  private handleBrowserEvent(evt: BrowserConnectorEvent): void {
    switch (evt.type) {
      case 'open':
        this.snapshot.connectStatus = 1;
        this.setState('connected');
        if (evt.payload) this.pushEvent({ type: 'live_info', payload: evt.payload });
        break;
      case 'reconnecting':
        this.snapshot.connectStatus = 1;
        this.setState('reconnecting');
        break;
      case 'reconnect':
        this.snapshot.connectStatus = 1;
        this.setState('connected');
        break;
      case 'error':
        this.snapshot.connectStatus = 2;
        this.snapshot.lastError = evt.payload?.message || 'cast error';
        this.setState('error');
        break;
      case 'close':
        this.snapshot.connectStatus = 3;
        this.snapshot.lastError = evt.payload?.reason || '';
        this.setState('disconnected');
        break;
      case 'message': {
        const msgs = Array.isArray(evt.payload) ? evt.payload : [];
        this.snapshot.lastMessageAt = Date.now();
        this.touch();
        this.pushEvent({ type: 'messages', payload: msgs });
        if (this.relay && this.relay.isConnected()) {
          this.relay.send(JSON.stringify(msgs));
        }
        break;
      }
    }
  }

  private setState(state: EngineState): void {
    this.snapshot.state = state;
    this.touch();
    this.emitStateEvent();
  }

  private emitStateEvent(): void {
    this.pushEvent({
      type: 'state_change',
      payload: {
        state: this.snapshot.state,
        connectStatus: this.snapshot.connectStatus,
        relayStatus: this.snapshot.relayStatus,
        relayConnected: this.snapshot.relayConnected,
        roomNum: this.snapshot.roomNum,
        relayUrl: this.snapshot.relayUrl,
        lastError: this.snapshot.lastError,
        lastMessageAt: this.snapshot.lastMessageAt
      }
    });
  }

  private touch(): void {
    this.snapshot.updatedAt = Date.now();
    this.snapshot.previewBufferSize = this.previewBuffer.length;
  }

  private pushEvent(event: EngineEvent): void {
    this.previewBuffer.push(event);
    if (this.previewBuffer.length > this.previewBufferLimit) {
      this.previewBuffer.splice(0, this.previewBuffer.length - this.previewBufferLimit);
    }
    this.snapshot.previewBufferSize = this.previewBuffer.length;
    this.snapshot.updatedAt = Date.now();
    this.emit('event', event);
  }
}

