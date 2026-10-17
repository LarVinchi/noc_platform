const fmt = (v, digits=2) => v === null || v === undefined ? '\u2014' : Number(v).toLocaleString('en-GB',{minimumFractionDigits:digits,maximumFractionDigits:digits});
const dateText = day => new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'Africa/Lagos'}).format(new Date(day+'T12:00:00+01:00'));
const clock = value => value ? value.slice(11,19) : 'Open';
const shortStamp = value => value ? `${value.slice(8,10)} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(value.slice(5,7))-1]} ${clock(value)}` : 'Open';
export function drawChart(canvas,site,kind,mode,report){if(mode==='excel'){drawExcelChart(canvas,site,kind,report);return;}const ctx=canvas.getContext('2d');const W=1200,H=680;const dark=mode==='dark';const c={bg:dark?'#101820':'#ffffff',ink:dark?'#ecf3f6':'#223e50',muted:dark?'#99aebc':'#7a8f9c',line:dark?'#293c49':'#eaf0f3',grid:dark?'#62b6c3':'#14918b',gen:dark?'#e8aa5a':'#dea04b'};ctx.fillStyle=c.bg;ctx.fillRect(0,0,W,H);const text=(v,x,y,size=18,color=c.ink,weight=400,align='left')=>{ctx.font=`${weight} ${size}px "Segoe UI", Arial, sans-serif`;ctx.fillStyle=color;ctx.textAlign=align;ctx.fillText(v,x,y);};text('AFL  /  DAILY ENERGY REPORT',44,43,13,c.muted,600);text(`${site.id} · ${kind==='grid'?'EKEDC availability & consumption':site.fuel+' generator'}`,44,86,27,c.ink,650);text(dateText(report.date)+'  ·  Africa/Lagos',44,117,16,c.muted);text(kind==='grid'?`${fmt(site.gridHours)} hrs`:`${fmt(site.genHours)} hrs`,W-44,78,29,kind==='grid'?c.grid:c.gen,650,'right');text(kind==='grid'?'Total logged availability':'Total elapsed runtime',W-44,105,13,c.muted,400,'right');if(kind==='grid'&&site.gridUsed!==null)text(`${fmt(site.gridUsed)} kWh used${site.gridPartial?' (partial)':''}`,W-44,132,16,c.muted,500,'right');
 let data=site.records.filter(r=>r.kind===kind&&r.active&&r.hours>0);const overlap=site.issues.some(i=>i.message.startsWith('Overlapping '+kind));let aggregate=false;if(data.length>10||overlap){aggregate=true;data=[{hours:kind==='grid'?site.gridHours:site.genHours,used:kind==='grid'?site.gridUsed:site.dieselUsed,start:report.date+'T00:00:00',row:null}];}
 const plot={x:85,y:202,w:1030,h:292};const maxHours=Math.max(1,...data.map(r=>r.hours));const topHours=kind==='grid'?(maxHours>12?24:Math.ceil(maxHours/2)*2):Math.ceil(maxHours/2)*2;const showUsage=kind==='grid'?(site.id==='PROJN01'||data.some(r=>r.used!==null)):site.fuel==='Diesel';const topFuel=Math.max(5,Math.ceil(Math.max(0,...data.map(r=>r.used||0))/5)*5);
 text('HOURS',plot.x,174,12,c.muted,600);if(showUsage)text(kind==='grid'?'kWh':'LITRES',plot.x+plot.w,174,12,c.muted,600,'right');
 for(let i=0;i<=4;i++){const y=plot.y+plot.h-i/4*plot.h;ctx.strokeStyle=c.line;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(plot.x,y);ctx.lineTo(plot.x+plot.w,y);ctx.stroke();text(fmt(topHours*i/4,1),plot.x-14,y+5,13,c.muted,400,'right');if(showUsage)text(fmt(topFuel*i/4,1),plot.x+plot.w+12,y+5,13,c.muted);}
 if(!data.length){text('No completed operating sessions logged',W/2,340,23,c.muted,500,'center');text('No runtime is assumed for open or missing records.',W/2,373,15,c.muted,400,'center');}
 const step=plot.w/Math.max(1,data.length);data.forEach((r,i)=>{const center=plot.x+step*(i+.5);const width=Math.min(65,step*(showUsage?.27:.45));const h=Math.min(plot.h,r.hours/topHours*plot.h);const bx=showUsage?center-width-4:center-width/2;ctx.fillStyle=kind==='grid'?c.grid:c.gen;ctx.fillRect(bx,plot.y+plot.h-h,width,h);text(fmt(r.hours),bx+width/2,plot.y+plot.h-h-12,15,c.ink,600,'center');if(showUsage){if(r.used!==null){const fh=r.used/topFuel*plot.h;ctx.fillStyle=dark?'#8393ca':'#7789b7';ctx.fillRect(center+4,plot.y+plot.h-fh,width,fh);text(fmt(r.used),center+4+width/2,plot.y+plot.h-fh-12,14,c.ink,600,'center');}else{text('N/A',center+width/2+4,plot.y+plot.h-12,12,c.muted,400,'center');}}text(aggregate?'Daily total':clock(r.start).slice(0,5),center,plot.y+plot.h+28,14,c.muted,400,'center');});
 const ly=556;ctx.fillStyle=kind==='grid'?c.grid:c.gen;ctx.fillRect(44,ly-11,10,10);text(kind==='grid'?'EKEDC availability (hrs)':'Generator runtime (hrs)',65,ly,14,c.muted);if(showUsage){ctx.fillStyle=dark?'#8393ca':'#7789b7';ctx.fillRect(365,ly-11,10,10);text((kind==='grid'?'EKEDC used (kWh)':'Diesel used (L)')+' - right axis',386,ly,14,c.muted);}else if(kind==='gen'){text('Gas consumption: not tracked',365,ly,14,c.muted);}
 const partial=kind==='grid'?site.gridPartial:site.dieselPartial;let note=kind==='gen'&&site.fuel==='Gas'?'Runtime only · gas consumption is not tracked.':partial?'Partial consumption data · missing readings are not treated as zero.':'Usage = opening − closing balance · additions are reported separately.';if(site.issues.some(i=>i.message.includes('prorated')&&site.records.some(r=>r.row===i.row&&r.kind===kind)))note='Boundary-spanning usage is prorated by time · estimated consumption.';if(overlap)note='Overlapping sessions merged for hours · consumption requires review.';text(note,44,594,13,c.muted);ctx.strokeStyle=c.line;ctx.beginPath();ctx.moveTo(44,615);ctx.lineTo(W-44,615);ctx.stroke();text(`${shortStamp(report.start)} → ${shortStamp(report.end)} WAT`,44,645,12,c.muted);text('Local workbook snapshot · AFL NOC',W-44,645,12,c.muted,400,'right');}

function excelCategory(stamp){const [date,time]=stamp.split('T');const [y,m,d]=date.split('-').map(Number);const [h,min]=time.split(':').map(Number);return `${m}/${d}/${y}`+(h||min?` ${h}:${String(min).padStart(2,'0')}`:'');}
function excelSeries(site,kind){
 const groups=new Map();
 for(const r of site.records){
  if(r.kind!==kind||!r.active||r.hours<=0)continue;
  if(!groups.has(r.start))groups.set(r.start,{start:r.start,hours:0,used:0,measured:0,missing:false});
  const group=groups.get(r.start);
  // Power Query rounds each interval to two decimals before the pivot sums it.
  group.hours+=Math.round((r.hours+Number.EPSILON)*100)/100;
  if(r.used===null){group.missing=true;}else{group.used+=r.used;group.measured++;}
 }
 return [...groups.values()].sort((a,b)=>a.start.localeCompare(b.start));
}
function drawExcelChart(canvas,site,kind,report){
 const ctx=canvas.getContext('2d'),W=1200,H=552;
 ctx.fillStyle='#000000';ctx.fillRect(0,0,W,H);
 ctx.strokeStyle='#bfbfbf';ctx.lineWidth=1;ctx.strokeRect(.5,.5,W-1,H-1);
 const text=(value,x,y,size=18,align='center')=>{ctx.fillStyle='#ffffff';ctx.font=`700 ${size}px Arial, sans-serif`;ctx.textAlign=align;ctx.fillText(value,x,y);};
 const hasUsage=site.id==='PROJN01';
 let title,legend;
 if(kind==='grid'){
  title=hasUsage?`${site.id} - EKEDC DAILY AVAILABILITY HOURS & KWH UNITS`:`${site.id} - EKEDC Daily Power Availability Summary (Hours)`;
  legend=hasUsage?['EKEDC Availability Hrs','EKEDC kWh Units']:['EKEDC Availability Hrs'];
 }else{
  title=hasUsage?`${site.id} - GENERATOR DAILY RUNTIME HOURS & DIESEL USAGE`:
   site.id==='ADEMP01'?`${site.id} - Daily Generator Operational Runtime Hours Summary`:`${site.id} - GEN DAILY AVAILABILITY HOURS`;
  legend=hasUsage?['Generator Runtime Hrs','Diesel Usage Ltrs']:['Generator Runtime Hrs'];
 }
 ctx.font='700 26px Arial, sans-serif';const titleSize=Math.min(26,26*(W-64)/ctx.measureText(title).width);text(title,W/2,47,titleSize);
 const colors=['#5B9BD5','#ED7D31'];ctx.font='700 16px Arial, sans-serif';const widths=legend.map(l=>ctx.measureText(l).width+22);const legendWidth=widths.reduce((a,b)=>a+b,0)+(legend.length-1)*24;let lx=(W-legendWidth)/2;
 legend.forEach((l,i)=>{ctx.fillStyle=colors[i];ctx.fillRect(lx,84,10,10);text(l,lx+16,95,16,'left');lx+=widths[i]+24;});
 const data=excelSeries(site,kind);
 const positive=Math.max(0,...data.map(r=>r.hours));const negative=hasUsage?Math.max(0,...data.map(r=>r.measured?r.used:0)):0;
 const top=144,bottom=H-52,left=27,right=W-27,available=bottom-top;
 const total=(positive+negative)||1;
 const scale=available/(total*1.14);
 const zero=negative>0?top+positive*1.14*scale:bottom;
 ctx.strokeStyle='#d9d9d9';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,zero+.5);ctx.lineTo(right,zero+.5);ctx.stroke();
 if(!data.length){text('No completed operating sessions logged',W/2,285,21);text(excelCategory(report.date+'T00:00:00'),W/2,H-22,17);return;}
 const step=(right-left)/data.length;
 const labelSize=Math.max(11,Math.min(17,step/Math.max(...data.map(r=>excelCategory(r.start).length))/.57));
 data.forEach((r,i)=>{
  const center=left+step*(i+.5),width=step*(hasUsage?.23:.315);
  const blueX=hasUsage?center-width:center-width/2;
  const height=r.hours*scale;
  ctx.fillStyle=colors[0];ctx.fillRect(blueX,zero-height,width,height);
  text(fmt(r.hours),blueX+width/2,zero-height-15,17);
  if(hasUsage){
   if(r.measured){const usedHeight=r.used*scale;ctx.fillStyle=colors[1];ctx.fillRect(center,zero,width,usedHeight);text(fmt(-r.used),center+width/2,zero+usedHeight+25,17);}
   if(r.missing||!r.measured)text(r.measured?'Partial':'N/A',center+width/2,zero+(r.used||0)*scale+45,13);
  }
  text(excelCategory(r.start),center,H-22,labelSize);
 });
 // Keep important data qualifications inside copied images, without report UI chrome.
 const qualifications=[];
 if(site.issues.some(i=>i.message.startsWith('Overlapping '+kind)))qualifications.push('Overlapping records: review session values');
 if(site.issues.some(i=>i.message.includes('Open record')&&site.records.some(r=>r.row===i.row&&r.kind===kind)))qualifications.push('Open records excluded');
 if(site.issues.some(i=>i.message.includes('prorated')&&site.records.some(r=>r.row===i.row&&r.kind===kind)))qualifications.push('Boundary usage prorated');
 if(qualifications.length){text(qualifications.join(' · '),W/2,123,13);}
}
