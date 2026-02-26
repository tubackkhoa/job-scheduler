var{useEffect:a,useState:n}=React,{LoadingSkeleton:l,DynamicField:r}=Components,{jinjaEvaluate:d}=Utils,p=({formData:t,...s})=>{let[e,o]=n();return a(()=>{(async()=>{let i=await d(t.package,`
{% set stats = fetch_stats_running_models() %}
{% set models = get_running_models() | pick ("identity", "currentConfig") %}
{% set identities = stats | map(attribute="identity") | list %}
{% set job_list = dao.get_jobs_by_model_keys(identities) | pick ("active", "description", "config.model_key") %}
{
  "models": {{ models | tojson }},
  "jobList": {{ job_list | tojson }},
  "stats": {{ stats | tojson }}
}`,{},!0);o(i)})()},[t.package]),e?React.createElement(r,{formData:e,...s,schema:{url:import.meta.env.DEV?"PnlPreview.tsx":"{base_url}/assets/{package}/pnl_preview.js"}}):React.createElement(l,{size:3})};export{p as default};
