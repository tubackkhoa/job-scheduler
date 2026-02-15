var k=Object.create;var l=Object.defineProperty;var m=Object.getOwnPropertyDescriptor;var v=Object.getOwnPropertyNames;var E=Object.getPrototypeOf,f=Object.prototype.hasOwnProperty;var d=(e,t)=>()=>(t||e((t={exports:{}}).exports,t),t.exports);var P=(e,t,s,r)=>{if(t&&typeof t=="object"||typeof t=="function")for(let o of v(t))!f.call(e,o)&&o!==s&&l(e,o,{get:()=>t[o],enumerable:!(r=m(t,o))||r.enumerable});return e};var u=(e,t,s)=>(s=e!=null?k(E(e)):{},P(t||!e||!e.__esModule?l(s,"default",{value:e,enumerable:!0}):s,e));var c=d(i=>{"use strict";var x=Symbol.for("react.transitional.element"),F=Symbol.for("react.fragment");function p(e,t,s){var r=null;if(s!==void 0&&(r=""+s),t.key!==void 0&&(r=""+t.key),"key"in t){s={};for(var o in t)o!=="key"&&(s[o]=t[o])}else s=t;return t=s.ref,{$$typeof:x,type:e,key:r,ref:t!==void 0?t:null,props:s}}i.Fragment=F;i.jsx=p;i.jsxs=p});var n=d((b,_)=>{"use strict";_.exports=c()});var a=u(n(),1),{useEffect:R,useState:T}=React,{LoadingSkeleton:g,DynamicField:y}=Components,{jinjaEvaluate:D}=Utils,w=({formData:e,...t})=>{let[s,r]=T();return R(()=>{(async()=>{let j=await D(e.package,`
{% set stats = fetch_stats_running_models() %}
{% set models = get_running_models() | pick ("identity", "currentConfig") %}
{% set identities = stats | map(attribute="identity") | list %}
{% set job_list = dao.get_jobs_by_model_keys(identities) | pick ("active", "description", "config.model_key") %}
{
  "models": {{ models | tojson }},
  "jobList": {{ job_list | tojson }},
  "stats": {{ stats | tojson }}
}`,{},!0);r(j)})()},[e.package]),s?(0,a.jsx)(y,{formData:s,...t,schema:{url:import.meta.env.DEV?"PnlPreview.tsx":"{base_url}/assets/{package}/pnl_preview.js"}}):(0,a.jsx)(g,{size:3})};export{w as default};
