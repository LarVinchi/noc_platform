import test from 'node:test';
import assert from 'node:assert/strict';
import { networkTotals,activityDays,lagosDay,csvText } from '../src/api/ftthMetrics.js';

test('outside-RFS orders are excluded from completed connections and take-up',()=>{
  const data={areas:[{id:'a',zone:'one',homes:100,counts:[5,10,2,1]},{id:'b',zone:'two',homes:100,counts:[1,2,0,0]}],outside:[{zone:'one',counts:[0,6,0,0]}]};
  assert.equal(networkTotals(data).connected,21);
  assert.equal(networkTotals(data).takeUp,10.5);
  assert.equal(networkTotals(data).outside,6);
  const filtered=networkTotals(data,'one','1');assert.equal(filtered.connected,10);assert.equal(filtered.homes,100);assert.equal(filtered.takeUp,10);
  assert.equal(networkTotals({areas:[{homes:0,zone:'one',counts:[0,0,0,0]}]}).takeUp,null);
});

test('Lagos date boundaries and legacy UTC timestamps are counted by work day',()=>{
  assert.equal(lagosDay('2026-10-20T23:30:00Z'),'2026-10-21');
  assert.equal(lagosDay('2026-10-20T23:30:00'),'2026-10-21');
  const days=activityDays([{created_at:'2026-10-20T23:30:00Z',planned_install_date:'2026-10-21T08:00:00Z',completion_date:'2026-10-21T09:00:00Z'},{completion_date:null}], '2026-10-20',7);
  assert.equal(days[0].completed.length,0);assert.equal(days[1].completed.length,1);assert.equal(days[1].requested.length,1);assert.equal(days[1].planned.length,1);
});

test('CSV quotes content and neutralizes formula-like customer values',()=>{
  const text=csvText([['=HYPERLINK("bad")','  +cmd','Normal, customer','line\nbreak']]);
  assert.ok(text.includes('"\'=HYPERLINK(""bad"")"'));assert.ok(text.includes('"\'  +cmd"'));assert.ok(text.includes('"Normal, customer"'));assert.ok(text.includes('"line\nbreak"'));
});
