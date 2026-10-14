import {createContext,useContext,useEffect} from 'react';

export const AssistantContext=createContext(null);
export function useAssistant() {return useContext(AssistantContext);}
export function useAssistantCase(kind,record) {
 const {register}=useAssistant();
 useEffect(()=>{if(record)return register(kind,record);},[register,kind,record]);
}
