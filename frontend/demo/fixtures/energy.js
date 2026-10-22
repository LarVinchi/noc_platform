const siteDefinitions=[['PROJN01','Project office','Diesel'],['LEKKP01','Lekki','Gas'],['ADEMP01','Ademola','Gas']];
export function dailyEnergy(day='2026-10-17',source='workbook') {
  const empty=day.endsWith('-18');
  const events=empty?[]:[{site:'PROJN01',kind:'gen',row:13,time:`${day}T23:00:00`,amount:50,confirmed:true,evidence:'Synthetic comment: refill of 50 litres',comment:'Synthetic refill of 50 litres',inSession:true}];
  return {mode:source,date:day,start:`${day}T00:00:00`,end:`${day}T23:59:59`,source:'DEMO · RawData-example.xlsx',events,sites:siteDefinitions.map(([id,name,fuel],i)=>({
    id,name,fuel,gridHours:empty?0:[16.5,18.25,19][i],gridUsed:empty?null:[96.4,58.2,74.5][i],genHours:empty?0:[6,4,3.5][i],dieselUsed:empty?null:i===0?29.5:null,gridAdded:0,dieselAdded:empty?0:i===0?50:0,unaccountedHours:empty?24:[1.5,1.75,1.5][i],gridPartial:false,dieselPartial:false,issues:[],
    records:empty?[]:[{row:12+i*2,kind:'grid',active:true,status:'ON',start:`${day}T00:00:00`,stop:`${day}T16:30:00`,hours:[16.5,18.25,19][i],opening:520,closing:520-[96.4,58.2,74.5][i],used:[96.4,58.2,74.5][i],operator:'Demo engineer',comment:'Synthetic workbook example'},
      {row:13+i*2,kind:'gen',active:true,status:'ON',start:`${day}T17:00:00`,stop:`${day}T23:00:00`,hours:[6,4,3.5][i],opening:i===0?160:null,closing:i===0?180.5:null,used:i===0?29.5:null,addition:i===0?50:0,additionConfirmed:true,operator:'Demo engineer',comment:fuel==='Gas'?'Gas consumption not tracked':'Synthetic refill of 50 litres'}],
  }))};
}
export function weeklyEnergy(weekStart='2026-10-05',source='workbook') {
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Africa/Lagos',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const days=Array.from({length:7},(_,i)=>new Date(Date.parse(`${weekStart}T12:00:00Z`)+i*86400000).toISOString().slice(0,10));
  const averageDays=days.filter(day=>day<=today).length,elapsed=days[6]<today;
  return {mode:source,source:'DEMO · RawData-example.xlsx',elapsed,averageDays,zeroForUnrecordedDays:true,weekStart,weekEnd:days[6],sites:siteDefinitions.map(([id,name,fuel],i)=>{
    const daily=days.map((date,n)=>({date,future:date>today,zeroAssumed:n===2,gridHours:date>today?null:n===2?0:16+i,genHours:date>today?null:n===2?0:6-i,gridUsed:date>today?null:n===2?0:90-i*12,dieselUsed:date>today?null:i===0?(n===2?0:29.5):null,gridAdded:0,dieselAdded:i===0&&n===1?50:0}));
    const total=key=>daily.reduce((n,row)=>n+(row.future?0:row[key]||0),0),mean=key=>averageDays?total(key)/averageDays:null;
    return {id,name,fuel,days:daily,averageDays,zeroDays:averageDays>2?1:0,gridHours:total('gridHours'),genHours:total('genHours'),averageGridHours:mean('gridHours'),averageGenHours:mean('genHours'),gridUsed:total('gridUsed'),averageGridUsed:mean('gridUsed'),dieselUsed:i===0?total('dieselUsed'):null,averageDieselUsed:i===0?mean('dieselUsed'):null,gridAdded:0,dieselAdded:i===0?total('dieselAdded'):0,dieselLitresPerHour:i===0?29.5/6:null,gridAvailabilityPercent:(mean('gridHours')||0)/24*100,daysWithGridRecords:averageDays-(averageDays>2?1:0),daysWithRecords:averageDays-(averageDays>2?1:0),gridPartial:false,genPartial:false,gridUsagePartial:false,dieselUsagePartial:false,issues:[],meterNumbers:[`DEMO-${id}`],generatorCapacity:'Not recorded'};
  })};
}
