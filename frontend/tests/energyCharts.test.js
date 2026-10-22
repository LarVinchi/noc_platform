import test from 'node:test';
import assert from 'node:assert/strict';
import { drawChart,dailyChartSeries,energyEmptyLabel } from '../src/components/energyChartRendering.js';
import { weeklyCoverageNote,drawWeeklyChart } from '../src/components/weeklyEnergyCharts.js';
import { smoothEnergySegments } from '../src/components/weeklyEnergyPlot.js';

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

test('smoothed consumption stays within neighbouring values and breaks at missing days',()=>{
  const source=[{x:0,y:10},{x:1,y:60},{x:2,y:15},{x:3,y:15},null,{x:5,y:20}];
  const pieces=smoothEnergySegments(source);
  assert.equal(pieces.length,2);assert.equal(pieces[1].curves.length,0);
  let previous=pieces[0].start;
  for(const curve of pieces[0].curves){
    const low=Math.min(previous.y,curve.end.y),high=Math.max(previous.y,curve.end.y);
    assert.ok(curve.cp1.y>=low&&curve.cp1.y<=high);
    assert.ok(curve.cp2.y>=low&&curve.cp2.y<=high);
    previous=curve.end;
  }
});

function drawing(){
  const strokes=[],rects=[],texts=[],textPositions=[];
  const ctx={path:[],measureText:value=>({width:String(value).length*8}),
    fillRect(...values){rects.push({ink:this.fillStyle,values});},strokeRect(){},
    fillText(value,x,y){texts.push(String(value));textPositions.push({value:String(value),x,y});},beginPath(){this.path=[];},
    moveTo(x,y){this.path.push([x,y]);},lineTo(x,y){this.path.push([x,y]);},
    bezierCurveTo(...values){this.path.push(values);},arc(){},fill(){},
    stroke(){strokes.push({ink:this.strokeStyle,path:[...this.path]});}};
  return {canvas:{getContext:()=>ctx},strokes,rects,texts,textPositions};
}

test('Excel keeps template colours; daily has one baseline and weekly has dual-axis horizontal guides',()=>{
  const site={id:'PROJN01',fuel:'Diesel',genHours:14,dieselUsed:84,averageGenHours:2,issues:[],
    records:[{kind:'gen',row:1,start:'2026-10-19T01:00:00',stop:'2026-10-19T03:00:00',active:true,hours:2,used:12}],
    days:Array.from({length:7},(_,i)=>({date:`2026-10-${19+i}`,genHours:2,dieselUsed:12+i}))};
  const report={date:'2026-10-19',weekStart:'2026-10-19',weekEnd:'2026-10-25',elapsed:true,averageDays:7,events:[]};
  const grids=(d,left=85,right=1115)=>d.strokes.filter(s=>s.path.length===2&&s.path[0][0]===left&&s.path[1][0]===right&&s.path[0][1]===s.path[1][1]);
  const daily=drawing();drawChart(daily.canvas,site,'gen','excel',report);
  assert.equal(grids(daily,27,1173).length,1);
  const runtime=daily.rects.find(r=>r.ink==='#5b9bd5'&&r.values[2]>12);
  const consumption=daily.rects.find(r=>r.ink==='#ed7d31'&&r.values[2]>12);
  assert.equal(runtime.values[2],1146*.23,'restore full-width category bars');
  assert.ok(Math.abs(consumption.values[3]/runtime.values[3]-6)<1e-10,'original shared Excel scale');
  assert.ok(consumption.values[1]>runtime.values[1],'daily consumption still descends from the baseline');
  assert.ok(daily.rects.some(r=>r.ink==='#ed7d31'));
  const weekly=drawing();drawWeeklyChart(weekly.canvas,report,site,'gen','excel');
  assert.equal(grids(weekly).length,5);
  assert.ok(weekly.rects.some(r=>r.ink==='#5b9bd5'));
  assert.ok(weekly.strokes.some(s=>s.ink==='#ed7d31'&&s.path.some(p=>p.length===6)));
  const curve=weekly.strokes.find(s=>s.ink==='#ed7d31').path;
  assert.ok(curve[0][1]>curve.at(-1).at(-1),'larger consumption plots higher on the inverted negative axis');
  const rightAxis=weekly.textPositions.filter(t=>t.x===1127);
  assert.deepEqual(rightAxis.map(t=>t.value),['0.0','-4.5','-9.0','-13.5','-18.0']);
  assert.ok(rightAxis[0].y>rightAxis.at(-1).y,'right axis starts at zero at the bottom');
  assert.ok(weekly.texts.includes('GENERATOR RUNTIME · HRS'));
  assert.ok(weekly.texts.includes('L · BALANCE CHANGE'));
  assert.ok(!weekly.texts.some(t=>/lower band|consumption and additions|^Usage:/.test(t)));
});
