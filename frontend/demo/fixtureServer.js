import { resolveFixture } from './fixtures/workspace.js';

export const SCENARIO_COOKIE = 'noc_demo_scenario';
const SCENARIOS = new Set(['live', 'loading', 'empty', 'stale', 'error']);
const LOADING_DELAY_MS = 8000;

function readScenario(cookieHeader = '') {
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${SCENARIO_COOKIE}=([a-z]+)`));
  return match && SCENARIOS.has(match[1]) ? match[1] : 'live';
}

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-NOC-Demo', 'synthetic-fixtures');
  res.end(JSON.stringify(body));
}

function handleApi(req, res, url) {
  const scenario = readScenario(req.headers.cookie);
  const path = url.pathname.slice('/api'.length) || '/';
  const query = Object.fromEntries(url.searchParams);
  const isAuth = path.startsWith('/auth/');
  if (scenario === 'error' && !isAuth) {
    return send(res, 503, { detail: 'Demo scenario: the operations API is unavailable. This failure is simulated and no backend is connected.' });
  }
  const { status, body } = resolveFixture(req.method, path, query, scenario);
  if (scenario === 'loading' && !isAuth) {
    setTimeout(() => send(res, status, body), LOADING_DELAY_MS);
    return undefined;
  }
  return send(res, status, body);
}

export function demoFixtureServer() {
  return {
    name: 'noc-demo-fixture-server',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url, 'http://demo.invalid');
        if (url.pathname === '/api' || url.pathname.startsWith('/api/')) return handleApi(req, res, url);
        if (url.pathname.startsWith('/static/')) return send(res, 404, { detail: 'The design preview has no stored documents.' });
        const isPageNavigation = req.method === 'GET'
          && (req.headers.accept || '').includes('text/html')
          && !url.pathname.startsWith('/@')
          && !/\.[a-z0-9]+$/i.test(url.pathname);
        if (isPageNavigation) req.url = '/demo/index.html';
        return next();
      });
    },
  };
}
