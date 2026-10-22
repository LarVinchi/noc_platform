const fmt = value => value == null ? '—' : Number(value).toLocaleString('en-GB',{minimumFractionDigits:2,maximumFractionDigits:2});
const dateText = day => new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'Africa/Lagos'}).format(new Date(day+'T12:00:00+01:00'));

export function energyEmptyLabel(site,kind) {
  const incomplete = site.records.some(r => r.kind===kind && !r.stop);
  return [kind==='grid'?'No EKEDC supply recorded':'No generator runtime recorded', incomplete ? 'An incomplete source record needs review.' : 'Reported runtime: 0 hours for this day.'];
}

export function dailyChartSeries(site,kind,report) {
  const groups = new Map();
  for (const r of site.records) {
    if (r.kind!==kind || (!(r.active && r.hours>0) && !r.addition)) continue;
    if(!groups.has(r.start))groups.set(r.start,{start:r.start,hours:0,used:0,measured:0,missing:false,addition:0,inferred:false});
    const group=groups.get(r.start);
    group.hours+=Math.round((r.hours+Number.EPSILON)*100)/100;
    if(r.active&&r.hours>0){if(r.used==null)group.missing=true;else{group.used+=r.used;group.measured++;}}
    group.addition+=r.addition||0;group.inferred ||= r.additionConfirmed===false;
  }
  for(const event of report.events||[]) {
    if(event.site!==site.id||event.kind!==kind||site.records.some(r=>r.row===event.row&&r.kind===kind&&r.addition))continue;
    if(!groups.has(event.time))groups.set(event.time,{start:event.time,hours:0,used:0,measured:0,missing:false,addition:0,inferred:false});
    groups.get(event.time).addition+=event.amount;groups.get(event.time).inferred ||= !event.confirmed;
  }
  let values=[...groups.values()].sort((a,b)=>a.start.localeCompare(b.start));
  if(values.length>10||site.issues.some(i=>i.message.startsWith('Overlapping '+kind))){
    const used=kind==='grid'?site.gridUsed:site.dieselUsed;
    values=[{start:null,hours:kind==='grid'?site.gridHours:site.genHours,used:used||0,measured:used==null?0:1,
      missing:values.some(v=>v.missing),addition:values.reduce((n,v)=>n+v.addition,0),inferred:values.some(v=>v.inferred)}];
  }
  return values;
}

export function drawChart(canvas,site,kind,mode,report) {
  const ctx=canvas.getContext('2d'), W=1200, H=mode==='excel'?552:680, dark=mode!=='light', signed=mode==='excel';
  const color={bg:signed?'#000':dark?'#101820':'#fff',ink:dark?'#f2f7fb':'#183345',muted:dark?'#b2c2cf':'#526979',line:dark?'#2d4050':'#dce5ec',hours:'#5b9bd5',usage:dark?'#ffb454':'#b45309',addition:dark?'#4ade80':'#15803d'};
  const text=(value,x,y,size=16,ink=color.ink,weight=400,align='left')=>{ctx.font=`${weight} ${size}px Arial,sans-serif`;ctx.fillStyle=ink;ctx.textAlign=align;ctx.fillText(String(value),x,y);};
  const pill=(value,x,y,ink)=>{ctx.font='700 15px Arial';const width=ctx.measureText(value).width+12;ctx.fillStyle=color.bg;ctx.fillRect(x-width/2,y-17,width,23);ctx.strokeStyle=ink;ctx.lineWidth=1;ctx.strokeRect(x-width/2,y-17,width,23);text(value,x,y,15,ink,700,'center');};
  ctx.fillStyle=color.bg;ctx.fillRect(0,0,W,H);
  const measured=kind==='grid'?(site.id==='PROJN01'||site.gridUsed!=null):site.fuel==='Diesel';
  const unit=kind==='grid'?'kWh':'L', name=kind==='grid'?'EKEDC availability':'Generator runtime';
  text(`${site.id} · ${name.toUpperCase()}${measured?' & '+(kind==='grid'?'EKEDC':'DIESEL')+' USAGE':''}`,40,44,25,color.ink,700);
  text(`${dateText(report.date)} · Lagos / WAT`,40,77,16,color.muted);
  [[color.hours,`${name} (hrs)`],[color.usage,`Consumption (${unit})${signed?' · downward':''}`],[color.addition,kind==='grid'?'Top-up · upward':'Refill · upward']].slice(0,measured?3:1).forEach(([ink,label],i)=>{ctx.fillStyle=ink;ctx.fillRect(40+i*365,102,12,12);text(label,62+i*365,114,14,color.muted);});
  const data=dailyChartSeries(site,kind,report), x=85,w=1030,y=160,h=signed?270:330;
  const overlap=site.issues.some(issue=>issue.message.startsWith('Overlapping '+kind));
  const partial=kind==='grid'?site.gridPartial:site.dieselPartial;
  if(!data.length){const [label,note]=energyEmptyLabel(site,kind);text(label,W/2,280,25,color.ink,700,'center');text(note,W/2,315,16,color.muted,400,'center');return;}
  const hourMax=Math.max(2,Math.ceil(Math.max(...data.map(v=>v.hours))/2)*2);
  const quantityMax=Math.max(5,Math.ceil(Math.max(...data.map(v=>Math.max(v.used,v.addition)))/5)*5);
  const zero=signed?y+h*.50:y+h, quantityHeight=signed?h*.45:h, hourHeight=signed?h*.45:h;
  text('HOURS',x,y-18,13,color.muted,700);if(measured)text(unit+' · RIGHT AXIS',x+w,y-18,13,color.muted,700,'right');
  for(let i=0;i<=4;i++){
    const yy=zero-hourHeight*i/4;ctx.strokeStyle=color.line;ctx.beginPath();ctx.moveTo(x,yy);ctx.lineTo(x+w,yy);ctx.stroke();
    text((hourMax*i/4).toFixed(1),x-12,yy+5,12,color.muted,400,'right');
    if(measured)text((quantityMax*i/4).toFixed(1),x+w+12,yy+5,12,color.muted);
    if(measured&&signed&&i>0)text((-quantityMax*i/4).toFixed(1),x+w+12,zero+quantityHeight*i/4+5,12,color.muted);
  }
  const step=w/data.length;
  data.forEach((r,i)=>{
    const cx=x+step*(i+.5), width=Math.min(55,step/(measured?4:2)), bx=measured?cx-width*1.6:cx-width/2;
    const height=r.hours/hourMax*hourHeight;ctx.fillStyle=color.hours;ctx.fillRect(bx,zero-height,width,height);pill(fmt(r.hours),bx+width/2,zero-height-10,color.ink);
    if(measured){
      if(r.measured){const q=r.used/quantityMax*quantityHeight;ctx.fillStyle=color.usage;ctx.fillRect(cx-width*.4,signed?zero:zero-q,width,q);pill((signed?'-'+fmt(r.used):fmt(r.used))+(r.missing?'*':''),cx+width*.1,signed?zero+q+23:zero-q-10,color.usage);}
      else if(r.missing)text('Review',cx+width*.1,zero+(signed?25:-10),12,color.usage,600,'center');
      if(r.addition){const q=r.addition/quantityMax*quantityHeight;ctx.fillStyle=color.addition;ctx.fillRect(cx+width*.8,zero-q,width,q);pill('+'+fmt(r.addition)+(r.inferred?'*':''),cx+width*1.3,zero-q-10,color.addition);}
    }
    text(r.start?.slice(11,16)||'Daily total',cx,signed?H-45:y+h+30,14,color.muted,400,'center');
  });
  const footer=signed?H-14:565;
  text(`Logged runtime: ${fmt(kind==='grid'?site.gridHours:site.genHours)} hrs${measured?' · Consumption: '+fmt(kind==='grid'?site.gridUsed:site.dieselUsed)+' '+unit:''}${overlap?' · Overlap: review usage':partial?' · Partial usage':''}${signed&&data.some(r=>r.inferred)?' · * Inferred net refill; review consumption.':''}`,40,footer,15,color.ink,600);
  if(!signed){
    const added=data.reduce((n,r)=>n+r.addition,0);
    text(added?`${kind==='grid'?'Top-ups':'Diesel refills'}: +${fmt(added)} ${unit} · green bars show additions separately.`:kind==='gen'&&!measured?'Gas consumption is not tracked.':'No additions recorded.',40,600,14,color.muted);
    text(overlap?'Overlapping sessions merged for hours; consumption may be duplicated. Review source records.':data.some(r=>r.inferred)?'* Net level increase; actual refill and consumption require review.':'Consumption = opening + stated in-session addition − closing. Missing readings remain unresolved.',40,637,13,color.muted);
  }
}
