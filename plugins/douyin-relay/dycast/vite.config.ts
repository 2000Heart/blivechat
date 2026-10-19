import { fileURLToPath, URL } from 'node:url';

import { defineConfig, type Plugin } from 'vite';
import vue from '@vitejs/plugin-vue';
import {
  applyPastedCookieToProxyReq,
  douyinUpstreamCookieApiMiddleware,
  setSidecarSsrModuleLoader,
  socketProxyTarget
} from './vite.douyin-proxy-cookie';

// import vueDevTools from 'vite-plugin-vue-devtools';

function douyinUpstreamCookiePlugin(): Plugin {
  return {
    name: 'douyin-upstream-cookie',
    configureServer(server) {
      setSidecarSsrModuleLoader((id: string) => server.ssrLoadModule(id));
      server.middlewares.use(douyinUpstreamCookieApiMiddleware);
    }
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    douyinUpstreamCookiePlugin()
    // vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0', // 允许局域网访问
    proxy: {
      '/dylive': {
        target: 'https://live.douyin.com',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/dylive/, ''),
        // 重要：允许接收 Set-Cookie
        configure: proxy => {
          // 拦截请求
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader(
              'User-Agent',
              'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
            );
            proxyReq.setHeader('Referer', 'https://live.douyin.com/');
            applyPastedCookieToProxyReq(proxyReq);
          });
          // 拦截响应
          proxy.on('proxyRes', proxyRes => {
            // 确保 set-cookie 能正常设置到当前域下
            const setCookie = proxyRes.headers['set-cookie'];
            if (setCookie) {
              // 移除 Domain 或替换为当前域
              const newCookie = setCookie.map(cookie =>
                cookie
                  .replace(/; Domain=[^;]+/i, '')
                  .replace(/; SameSite=None/, '')
                  .replace(/; Secure=true/i, '')
              );
              proxyRes.headers['set-cookie'] = newCookie;
            }
          });
        }
      },
      '/socket': {
        target: 'wss://webcast100-ws-web-lq.douyin.com',
        router: () => socketProxyTarget(),
        changeOrigin: true, // 保持原始 Host，利于服务端识别 Cookie
        secure: true,
        ws: true, // 启用 WebSocket 代理
        rewrite: path => path.replace(/^\/socket/, ''),
        configure: proxy => {
          proxy.on('proxyReqWs', (proxyReq, req) => {
            // sidecar Node WS 没有浏览器 UA，强制补齐更接近浏览器握手。
            proxyReq.setHeader(
              'User-Agent',
              'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0'
            );
            proxyReq.setHeader('Referer', 'https://live.douyin.com/');
            proxyReq.setHeader('Origin', 'https://live.douyin.com');
            applyPastedCookieToProxyReq(proxyReq);
          });
        }
      }
    }
  }
});
