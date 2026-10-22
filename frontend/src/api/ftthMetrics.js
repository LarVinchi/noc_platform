export const PARTNERS=['MetroReach Retail','MTNN','MANGONET','TELEWYZ'];
export const STAGES=['REQUESTED','SCHEDULED','IN_PROGRESS','PENDING_ACCEPTANCE','MONITORED'];
export const stageName=value=>({REQUESTED:'Requested',SCHEDULED:'Scheduled',IN_PROGRESS:'In progress',PENDING_ACCEPTANCE:'Pending acceptance',MONITORED:'NOC accepted'}[value]||value);

export function lagosDay(value=new Date()){
  const raw=typeof value==='string'&&!/([zZ]|[+-]\d\d:\d\d)$/.test(value)&&value.includes('T')?value+'Z':value;
  const date=new Date(raw);
  return Number.isNaN(date.getTime())?null:new Intl.DateTimeFormat('en-CA',{timeZone:'Africa/Lagos',year:'numeric',month:'2-digit',day:'2-digit'}).format(date);
}

export function networkTotals(snapshot,zone='',partner=''){
  const index=partner===''?null:Number(partner),pick=counts=>index===null?counts.reduce((a,b)=>a+b,0):counts[index];
  const areas=(snapshot?.areas||[]).filter(a=>!zone||a.zone===zone);
  const outside=(snapshot?.outside||[]).filter(a=>!zone||a.zone===zone);
  const homes=areas.reduce((sum,a)=>sum+a.homes,0),connected=areas.reduce((sum,a)=>sum+pick(a.counts),0),waiting=outside.reduce((sum,a)=>sum+pick(a.counts),0);
  return {areas,homes,connected,outside:waiting,takeUp:homes?connected/homes*100:null,
    partners:PARTNERS.map((name,i)=>({name,count:areas.reduce((sum,a)=>sum+a.counts[i],0)}))};
}

export function activityDays(orders,start,days){
  return Array.from({length:days},(_,i)=>{
    const date=new Date(start+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+i);const day=date.toISOString().slice(0,10);
    return {day,requested:orders.filter(o=>o.created_at&&lagosDay(o.created_at)===day),
      planned:orders.filter(o=>o.planned_install_date&&lagosDay(o.planned_install_date)===day),
      completed:orders.filter(o=>o.completion_date&&lagosDay(o.completion_date)===day)};
  });
}

export function csvText(rows){
  return '\ufeff'+rows.map(row=>row.map(value=>{
    let text=String(value??'');if(/^\s*[=+\-@]/.test(text)||/^[\t\r]/.test(text))text="'"+text;
    return '"'+text.replaceAll('"','""')+'"';
  }).join(',')).join('\r\n');
}

export function downloadCsv(filename,rows){
  const url=URL.createObjectURL(new Blob([csvText(rows)],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
