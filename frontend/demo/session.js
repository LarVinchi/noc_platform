import apiClient from '../src/api/client.js';

export const SCENARIOS = [
  ['live', 'Live data'],
  ['loading', 'Loading'],
  ['empty', 'Empty'],
  ['stale', 'Stale'],
  ['error', 'API error'],
];
const SCENARIO_COOKIE = 'noc_demo_scenario';
const OPENED_KEY = 'noc.demo.opened';

export function currentScenario() {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${SCENARIO_COOKIE}=([a-z]+)`));
  return match && SCENARIOS.some(([value]) => value === match[1]) ? match[1] : 'live';
}

export function changeScenario(value) {
  document.cookie = `${SCENARIO_COOKIE}=${value}; path=/; SameSite=Lax`;
  window.location.reload();
}

export const wasOpened = () => sessionStorage.getItem(OPENED_KEY) === '1';
export const forgetOpened = () => sessionStorage.removeItem(OPENED_KEY);

export async function openDemoSession() {
  const [config, me] = await Promise.all([apiClient.get('/auth/config'), apiClient.get('/auth/me')]);
  if (config.data?.mode !== 'demo' || me.data?.demo !== true) {
    throw new Error('The fixture server did not return the synthetic demo identity.');
  }
  sessionStorage.setItem(OPENED_KEY, '1');
  return me.data;
}
