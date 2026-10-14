import {useCallback,useMemo,useState} from 'react';
import {AssistantContext} from './AssistantContext';

export default function AssistantProvider({children}) {
 const [activeCase,setActiveCase]=useState(null);
 const [open,setOpen]=useState(false);
 const register=useCallback((kind,record)=>{
  const token=Symbol('assistant-case');
  setActiveCase({kind,record,token});
  return ()=>setActiveCase(current=>current?.token===token?null:current);
 },[]);
 const value=useMemo(()=>({activeCase,open,setOpen,register}),[activeCase,open,register]);
 return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}
