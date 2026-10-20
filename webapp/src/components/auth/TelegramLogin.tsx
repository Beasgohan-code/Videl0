"use client";
import { useEffect, useRef, useState } from "react";
type TelegramLoginUser={id:number;first_name:string;last_name?:string;username?:string;photo_url?:string;auth_date:number;hash:string};
declare global{interface Window{onTelegramAuth?:(user:TelegramLoginUser)=>void}}
export function TelegramLogin({botUsername,onAuth,cornerRadius=14}:{botUsername:string;onAuth:(user:TelegramLoginUser)=>void|Promise<void>;cornerRadius?:number}){
 const host=useRef<HTMLDivElement>(null);const callback=useRef(onAuth);const [loaded,setLoaded]=useState(false);callback.current=onAuth;
 useEffect(()=>{const username=botUsername.replace(/^@/,"");if(!username||!host.current)return;window.onTelegramAuth=user=>{void callback.current(user)};const script=document.createElement("script");script.src="https://telegram.org/js/telegram-widget.js?22";script.async=true;script.setAttribute("data-telegram-login",username);script.setAttribute("data-size","large");script.setAttribute("data-radius",String(cornerRadius));script.setAttribute("data-onauth","onTelegramAuth(user)");host.current.replaceChildren(script);setLoaded(true);return()=>{script.remove();delete window.onTelegramAuth};},[botUsername,cornerRadius]);
 return <div className="flex flex-col items-center gap-3"><div ref={host} className="flex min-h-[44px] items-center justify-center"/>{!loaded&&<p className="ios-caption">Loading Telegram sign-in…</p>}<p className="max-w-[320px] text-center ios-caption">Telegram verifies the account. Videl grants access only to the configured bot owner.</p></div>
}
