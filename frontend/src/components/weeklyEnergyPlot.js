// Separate runtime and quantity bands keep labels readable in copied email images.
export function renderWeeklyPlot(canvas,report,site,kind,theme,helpers) {
  const {weeklyFields,weeklyDate,weeklyNumber,weeklyAverage,weeklyCoverageNote}=helpers;
  const ctx=canvas.getContext('2d'),dark=theme!=='light',signed=theme==='excel',field=weeklyFields(site,kind);
  const c={bg:signed?'#000':dark?'#101e2b':'#fff',ink:dark?'#f1f6fb':'#203c50',muted:dark?'#b3c4d2':'#526979',line:dark?'#2b4050':'#dbe5ed',bar:'#5b9bd5',usage:dark?'#ffb454':'#b45309',addition:dark?'#4ade80':'#15803d'};
  const text=(value,x,y,size=15,ink=c.ink,bold=false,align='left')=>{ctx.font=`${bold?700:400} ${size}px Arial`;ctx.fillStyle=ink;ctx.textAlign=align;ctx.fillText(String(value),x,y);};
  const pill=(value,x,y,ink)=>{ctx.font='700 14px Arial';const width=ctx.measureText(value).width+10;ctx.fillStyle=c.bg;ctx.fillRect(x-width/2,y-16,width,22);ctx.strokeStyle=ink;ctx.lineWidth=1;ctx.strokeRect(x-width/2,y-16,width,22);text(value,x,y,14,ink,true,'center');};
  ctx.fillStyle=c.bg;ctx.fillRect(0,0,1200,650);
  text(`${site.id} · ${field.name.toUpperCase()}`,40,42,26,c.ink,true);
  text(`${weeklyDate(report.weekStart)} – ${weeklyDate(report.weekEnd)} ${report.weekEnd.slice(0,4)} · Lagos / WAT${!report.elapsed?' · WEEK TO DATE':''}`,40,76,16,c.muted);
  [[c.bar,`${field.name} (hrs)`],[c.usage,`Usage (${field.unit}) · ${signed?'downward':'lower band'}`],[c.addition,kind==='grid'?'Top-ups · upward':'Refills · upward']].slice(0,field.measured?3:1).forEach(([ink,label],i)=>{ctx.fillStyle=ink;ctx.fillRect(40+i*370,101,11,11);text(label,60+i*370,112,14,c.muted);});
  const x=85,w=1030,step=w/7,y=155,h=190;
  const hourMax=Math.max(2,Math.ceil(Math.max(0,...site.days.map(r=>r[field.hours]||0))/2)*2);
  text('HOURS',x,y-18,12,c.muted,true);
  for(let i=0;i<=4;i++){
    const yy=y+h-h*i/4;ctx.strokeStyle=c.line;ctx.beginPath();ctx.moveTo(x,yy);ctx.lineTo(x+w,yy);ctx.stroke();
    text((hourMax*i/4).toFixed(1),x-12,yy+4,12,c.muted,false,'right');
  }
  site.days.forEach((row,i)=>{
    const cx=x+step*(i+.5),value=row[field.hours];
    if(value!=null){const height=value/hourMax*h;ctx.fillStyle=c.bar;ctx.fillRect(cx-28,y+h-height,56,height);pill(weeklyNumber(value),cx,y+h-height-10,c.ink);}
    else text(row.future?'Upcoming':'No entry',cx,y+h-10,12,c.muted,false,'center');
    text(weeklyDate(row.date),cx,y+h+29,14,c.muted,false,'center');
  });
  const added=kind==='grid'?'gridAdded':'dieselAdded';
  if(field.measured){
    text(`${kind==='grid'?'EKEDC':'DIESEL'} · ${field.unit} · consumption and additions`,85,402,13,c.muted,true);
    const maximum=Math.max(5,...site.days.flatMap(row=>[row[field.usage]||0,row[added]||0]));
    const baseline=signed?466:522,quantityHeight=signed?39:88;
    ctx.strokeStyle=c.line;ctx.beginPath();ctx.moveTo(x,baseline);ctx.lineTo(x+w,baseline);ctx.stroke();
    site.days.forEach((row,i)=>{
      if(row.future)return;
      const cx=x+step*(i+.5),used=row[field.usage],addition=row[added]||0;
      if(used!=null){const size=used/maximum*quantityHeight;ctx.fillStyle=c.usage;ctx.fillRect(cx-47,signed?baseline:baseline-size,28,size);pill(weeklyNumber(signed&&used?-used:used),cx-33,signed?baseline+size+21:baseline-size-9,c.usage);}
      else text('Review',cx-33,baseline-8,12,c.muted,false,'center');
      if(addition){const size=addition/maximum*quantityHeight;ctx.fillStyle=c.addition;ctx.fillRect(cx+19,baseline-size,28,size);pill('+'+weeklyNumber(addition)+(row[kind==='grid'?'gridAdditionInferred':'dieselAdditionInferred']?'*':''),cx+33,baseline-size-9,c.addition);}
    });
  }else text('Gas consumption is not tracked.',85,440,15,c.muted);
  text(`Logged total: ${weeklyNumber(site[field.hours])} hrs · Daily average: ${weeklyAverage(site,kind)} hrs`,40,564,17,c.ink,true);
  if(field.measured)text(`Usage: ${weeklyNumber(site[field.usage])} ${field.unit}${field.usagePartial?' · partial':''} · ${kind==='grid'?'Top-ups':'Refills'}: +${weeklyNumber(site[added]||0)} ${field.unit}`,40,592,15,c.muted);
  ctx.font='13px Arial';ctx.fillStyle=c.muted;ctx.textAlign='left';ctx.fillText(weeklyCoverageNote(report,site,kind),40,628,1120);
}
