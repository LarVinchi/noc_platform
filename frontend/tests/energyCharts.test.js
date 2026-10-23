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

test('daily refill, usage and runtime bars touch edge to edge without overlap in every theme',()=>{
  for(const theme of ['excel','light','dark'])for(const kind of ['grid','gen'])for(const sessions of [1,5]){
    const site={id:'PROJN01',fuel:'Diesel',gridUsed:30,gridHours:6,genHours:6,dieselUsed:30,issues:[],
      records:Array.from({length:sessions},(_,i)=>({kind,row:i,start:`2026-10-17T${String(i+10).padStart(2,'0')}:00:00`,stop:'2026-10-17T20:00:00',active:true,hours:1,used:6,addition:10,additionConfirmed:true}))};
    const d=drawing();drawChart(d.canvas,site,kind,theme,{date:'2026-10-17',events:[]});
    assert.equal(d.texts.filter(t=>t==='17 Oct 2026').length,sessions,'each group includes its date');
    const colours=['#5b9bd5',theme==='excel'?'#ed7d31':theme==='dark'?'#ffb454':'#b45309',theme==='light'?'#15803d':'#4ade80'];
    const bars=colours.map(ink=>d.rects.filter(r=>r.ink===ink&&r.values[1]>120));
    for(let i=0;i<sessions;i++){
      for(let j=0;j<2;j++)assert.ok(Math.abs(bars[j][i].values[0]+bars[j][i].values[2]-bars[j+1][i].values[0])<1e-9,`${theme}/${kind}: grouped bars must share an edge without overlap`);
    }
  }
});

test('daily Excel category times clear the baseline and negative value labels',()=>{
  for(const fuel of ['Gas','Diesel']){
    const site={id:fuel==='Gas'?'ADEMP01':'PROJN01',fuel,genHours:3.5,dieselUsed:fuel==='Diesel'?29.5:null,issues:[],
      records:[{kind:'gen',row:1,start:'2026-10-17T17:00:00',stop:'2026-10-17T20:30:00',active:true,hours:3.5,used:fuel==='Diesel'?29.5:null}]};
    const d=drawing();drawChart(d.canvas,site,'gen','excel',{date:'2026-10-17',events:[]});
    const time=d.textPositions.find(t=>t.value==='17:00');
    const date=d.textPositions.find(t=>t.value==='17 Oct 2026');
    assert.equal(time.x,date.x,'date and time share the category centre');
    assert.equal(time.y-date.y,18,'date and time occupy separate lines');
    const baseline=d.strokes.find(s=>s.path.length===2).path[0][1];
    assert.ok(time.y-baseline>=30,'time label must be below the plot, never on the baseline');
    const usage=d.textPositions.find(t=>t.value==='-29.50');
    if(usage)assert.ok(time.y-usage.y>=18,'negative values need a separate row above category times');
  }
});

test('Excel keeps template colours; daily has one baseline and weekly has dual-axis horizontal guides',()=>{
  const site={id:'PROJN01',fuel:'Diesel',genHours:14,dieselUsed:84,averageGenHours:2,issues:[],
    records:[{kind:'gen',row:1,start:'2026-10-19T01:00:00',stop:'2026-10-19T03:00:00',active:true,hours:2,used:12}],
    days:Array.from({length:7},(_,i)=>({date:`2026-10-${19+i}`,genHours:2,dieselUsed:12+i}))};
  const report={date:'2026-10-19',weekStart:'2026-10-19',weekEnd:'2026-10-25',elapsed:true,averageDays:7,events:[]};
  const grids=(d,left=85,right=1115)=>d.strokes.filter(s=>s.path.length===2&&s.path[0][0]===left&&s.path[1][0]===right&&s.path[0][1]===s.path[1][1]);
  const daily=drawing();drawChart(daily.canvas,site,'gen','excel',report);
  assert.equal(grids(daily).length,1);
  const runtime=daily.rects.find(r=>r.ink==='#5b9bd5'&&r.values[2]>12);
  const consumption=daily.rects.find(r=>r.ink==='#ed7d31'&&r.values[2]>12);
  assert.equal(runtime.values[2],1030*.23,'keep grouped bars wide within calibrated axis margins');
  assert.ok(runtime.values[3]>consumption.values[3],'hours have an independent scale from litres');
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

test('daily runtime keeps its height when refill grows and both quantity directions use one scale',()=>{
  for(const mode of ['excel','light','dark']){
    const site={id:'PROJN01',fuel:'Diesel',genHours:6,dieselUsed:29.5,issues:[],
      records:[{kind:'gen',row:1,start:'2026-10-17T17:00:00',stop:'2026-10-17T23:00:00',active:true,hours:6,used:29.5,addition:50}]};
    const first=drawing();drawChart(first.canvas,site,'gen',mode,{date:'2026-10-17'});
    site.records[0].addition=5000;
    const second=drawing();drawChart(second.canvas,site,'gen',mode,{date:'2026-10-17'});
    const bars=(d,ink)=>d.rects.filter(r=>r.ink===ink&&r.values[1]>120&&r.values[2]>20);
    assert.equal(bars(first,'#5b9bd5')[0].values[3],bars(second,'#5b9bd5')[0].values[3]);
    assert.ok(first.texts.includes('HOURS')&&first.texts.includes('L · REFILL / USAGE'));
    const right=second.textPositions.filter(t=>t.x===1127);
    assert.ok(right.some(t=>Number(t.value)>=5000),'quantity ticks follow the largest daily reading');
    assert.ok(second.textPositions.some(t=>t.x===73&&Number(t.value)>=6),'left ticks reflect hours');
    if(mode==='excel'){
      const consumption=bars(first,'#ed7d31')[0],addition=bars(first,'#4ade80')[0];
      assert.ok(Math.abs(consumption.values[3]/addition.values[3]-29.5/50)<1e-10);
      assert.ok(right.some(t=>Number(t.value)<0));
    }
  }
});
