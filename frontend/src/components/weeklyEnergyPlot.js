// One combined chart: runtime bars, consumption line and upward refill bars.
export function smoothEnergySegments(points) {
  const groups=[];let current=[];
  for(const point of points){
    if(!point){if(current.length)groups.push(current);current=[];}else current.push(point);
  }
  if(current.length)groups.push(current);
  return groups.map(group=>{
    const slopes=group.slice(1).map((point,i)=>(point.y-group[i].y)/(point.x-group[i].x));
    const tangents=group.map((_,i)=>{
      if(i===0)return slopes[0]||0;
      if(i===group.length-1)return slopes.at(-1)||0;
      const a=slopes[i-1],b=slopes[i];
      return a*b>0?2*a*b/(a+b):0;
    });
    return {start:group[0],curves:group.slice(1).map((end,i)=>{
      const start=group[i],dx=(end.x-start.x)/3;
      return {cp1:{x:start.x+dx,y:start.y+tangents[i]*dx},cp2:{x:end.x-dx,y:end.y-tangents[i+1]*dx},end};
    })};
  });
}

export function renderWeeklyPlot(canvas,report,site,kind,theme,helpers) {
  const {weeklyFields,weeklyDate,weeklyNumber,weeklyAverage,weeklyCoverageNote}=helpers;
  const ctx=canvas.getContext('2d'),dark=theme!=='light',signed=theme==='excel',field=weeklyFields(site,kind);
  const c={bg:signed?'#000':dark?'#101e2b':'#fff',ink:dark?'#fff':'#203c50',muted:signed?'#fff':dark?'#b3c4d2':'#526979',line:signed?'#d9d9d9':dark?'#2b4050':'#dbe5ed',bar:'#5b9bd5',usage:signed?'#ed7d31':dark?'#ffb454':'#b45309',addition:dark?'#4ade80':'#15803d'};
  const text=(value,x,y,size=15,ink=c.ink,bold=false,align='left')=>{ctx.font=`${bold?700:400} ${size}px Arial`;ctx.fillStyle=ink;ctx.textAlign=align;ctx.fillText(String(value),x,y);};
  const label=(value,x,y,ink,consumption=false)=>{ctx.font='700 15px Arial';const width=ctx.measureText(value).width+12;ctx.fillStyle=consumption?'#000':c.bg;ctx.fillRect(x-width/2,y-17,width,24);text(value,x,y,15,consumption?'#fff':signed?c.ink:ink,true,'center');};
  ctx.fillStyle=c.bg;ctx.fillRect(0,0,1200,650);
  text(`${site.id} · ${field.name.toUpperCase()}${field.measured?' & '+(kind==='grid'?'EKEDC':'DIESEL')+' USAGE':''}`,40,42,25,c.ink,true);
  text(`${weeklyDate(report.weekStart)} – ${weeklyDate(report.weekEnd)} ${report.weekEnd.slice(0,4)} · Lagos / WAT${!report.elapsed?' · WEEK TO DATE':''}`,40,76,16,c.muted);
  const added=kind==='grid'?'gridAdded':'dieselAdded',hasAdditions=(site[added]||0)>0;
  const legend=[[c.bar,`${field.name} (hrs)`]];
  if(field.measured)legend.push([c.usage,`${kind==='grid'?'EKEDC':'Diesel'} ${signed?'balance change':'consumption'} (${field.unit})`]);
  if(field.measured&&hasAdditions)legend.push([c.addition,kind==='grid'?'Top-ups':'Refills']);
  legend.forEach(([ink,name],i)=>{ctx.fillStyle=ink;ctx.fillRect(40+i*370,101,11,11);text(name,60+i*370,112,14,c.muted);});
  const x=85,w=1030,step=w/7,y=180,h=310;
  const hourMax=Math.max(2,Math.ceil(Math.max(0,...site.days.map(r=>r[field.hours]||0))/2)*2);
  const quantityMax=Math.max(5,...site.days.flatMap(r=>[r[field.usage]||0,r[added]||0]));
  text(kind==='grid'?'EKEDC AVAILABILITY · HRS':'GENERATOR RUNTIME · HRS',x,y-38,12,c.muted,true);
  if(field.measured)text(field.unit+' · '+(signed?'BALANCE CHANGE':'CONSUMPTION'),x+w,y-38,12,c.muted,true,'right');
  for(let i=0;i<=4;i++){
    const yy=y+h-h*i/4;
    if(i>0){ctx.strokeStyle=signed?'#292929':c.line;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,yy);ctx.lineTo(x+w,yy);ctx.stroke();}
    text((hourMax*i/4).toFixed(1),x-12,yy+4,12,c.muted,false,'right');
    if(field.measured)text((signed?-quantityMax*(1-i/4):quantityMax*i/4).toFixed(1),x+w+12,yy+4,12,c.muted);
  }
  // Weekly uses horizontal guides only. Daily Excel charts keep their grid-free template.
  ctx.strokeStyle=c.line;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,y+h);ctx.lineTo(x+w,y+h);ctx.stroke();
  site.days.forEach((row,i)=>{
    const cx=x+step*(i+.5),value=row[field.hours],addition=row[added]||0,barX=hasAdditions?cx-41:cx-28;
    if(value!=null){const height=value/hourMax*h;ctx.fillStyle=c.bar;ctx.fillRect(barX,y+h-height,hasAdditions?40:56,height);label(weeklyNumber(value),barX+(hasAdditions?20:28),y+h-height-10,c.ink);}
    else text(row.future?'Upcoming':'No entry',cx,y+h-10,12,c.muted,false,'center');
    if(field.measured&&addition&&!row.future){const height=addition/quantityMax*h;ctx.fillStyle=c.addition;ctx.fillRect(cx+14,y+h-height,30,height);label('+'+weeklyNumber(addition)+(row[kind==='grid'?'gridAdditionInferred':'dieselAdditionInferred']?'*':''),cx+29,y+h-height-10,c.addition);}
    text(weeklyDate(row.date),cx,y+h+29,14,c.muted,false,'center');
  });
  if(field.measured){
    const points=site.days.map((row,i)=>row[field.usage]==null||row.future?null:{x:x+step*(i+.5),y:signed?y+row[field.usage]/quantityMax*h:y+h-row[field.usage]/quantityMax*h,value:row[field.usage]});
    // Background halo separates the original orange line from blue bars without changing its colour.
    const segments=smoothEnergySegments(points);
    for(const [ink,width] of [['#000',9],[c.usage,4]]){
      ctx.strokeStyle=ink;ctx.lineWidth=width;ctx.beginPath();
      for(const segment of segments){ctx.moveTo(segment.start.x,segment.start.y);for(const curve of segment.curves)ctx.bezierCurveTo(curve.cp1.x,curve.cp1.y,curve.cp2.x,curve.cp2.y,curve.end.x,curve.end.y);}
      ctx.stroke();
    }
    points.forEach((point,i)=>{
      if(!point)return;
      ctx.fillStyle=c.usage;ctx.beginPath();ctx.arc(point.x,point.y,5,0,Math.PI*2);ctx.fill();
      let yy=point.y+(signed?24:-12);
      const hours=site.days[i][field.hours]||0,barLabel=y+h-hours/hourMax*h-10;
      if(Math.abs(yy-barLabel)<28)yy=barLabel>y+h-38?barLabel-32:point.y+25;
      yy=Math.max(y+14,Math.min(y+h-8,yy));
      label(weeklyNumber(signed&&point.value?-point.value:point.value),point.x,yy,c.usage,true);
    });
  }
  text(`Logged total: ${weeklyNumber(site[field.hours])} hrs · Daily average: ${weeklyAverage(site,kind)} hrs`,40,572,17,c.ink,true);
  if(!field.measured&&kind==='gen')text('Gas consumption is not tracked.',40,602,15,c.muted);
  ctx.font='13px Arial';ctx.fillStyle=c.muted;ctx.textAlign='left';ctx.fillText(weeklyCoverageNote(report,site,kind),40,628,1120);
}
