import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyChartSeries,energyEmptyLabel } from '../src/components/energyChartRendering.js';
import { weeklyCoverageNote } from '../src/components/weeklyEnergyCharts.js';

test('refill-only cycle markers appear as additions without invented runtime or consumption',()=>{
  const site={id:'PROJN01',records:[],issues:[]};
  const values=dailyChartSeries(site,'gen',{events:[{site:'PROJN01',kind:'gen',row:4,time:'2026-10-21T12:00:00',amount:50,confirmed:true}]});
  assert.equal(values[0].hours,0);assert.equal(values[0].addition,50);assert.equal(values[0].measured,0);
  site.records=[{row:4,kind:'gen',start:'2026-10-21T12:00:00',active:false,hours:0,used:null,addition:50}];
  assert.equal(dailyChartSeries(site,'gen',{events:[{site:'PROJN01',kind:'gen',row:4,time:'2026-10-21T12:00:00',amount:50}]}).length,1);
});
test('no-supply labels distinguish incomplete records from zero logged time',()=>{
  assert.equal(energyEmptyLabel({records:[]},'grid')[0],'No EKEDC supply recorded');
  assert.equal(energyEmptyLabel({records:[]},'gen')[0],'No generator runtime recorded');
  assert.match(energyEmptyLabel({records:[{kind:'gen',stop:null}]},'gen')[1],/incomplete/);
});
test('copied weekly image qualifications disclose the actual calendar denominator',()=>{
  assert.match(weeklyCoverageNote({elapsed:false,averageDays:4},{id:'PROJN01',fuel:'Diesel'},'gen'),/4 calendar days/);
  assert.match(weeklyCoverageNote({elapsed:false,averageDays:4},{id:'PROJN01',fuel:'Diesel'},'gen'),/future days excluded/);
});
