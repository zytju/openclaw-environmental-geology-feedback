"use strict";
let session = null;
const $ = id => document.getElementById(id);
const labels = {problem_identification:"问题识别",evidence_extraction:"证据提取",reasoning_chain:"推理链完整性",hazard_chain:"灾害链分析",uncertainty:"不确定性表达",mitigation_match:"防治建议匹配"};
const states = {supported:"已有依据",partial:"需要修订",absent:"内容缺失",needs_verification:"待核查"};
const errors = {LOGIN_FAILED:"编号或口令有误，请使用教师发给本人的凭证。",LOGIN_REQUIRED:"会话已过期，请重新登录。",LOGIN_RATE_LIMIT:"登录尝试较多，请稍后再试。",REMOVE_PERSONAL_INFORMATION:"检测到可能的身份信息，请删除姓名、学号、联系方式后重试。",COURSE_SCOPE_REQUIRED:"请提交三峡库区滑坡及灾害链相关报告，题目或正文需说明对象与问题。",PLEASE_WAIT:"正在处理或刚完成请求，请稍候，不要重复点击。",SERVICE_BUSY:"当前请求较多，请稍后重试。",COURSE_CALL_LIMIT_CONTACT_TEACHER:"已达到本次课程调用上限，请联系教师。",INPUT_OR_OUTPUT_INVALID:"材料或模型反馈未通过格式核验，请联系教师；不要重复发送相同请求。"};
async function api(path, method="GET", data) {
  const response = await fetch(path,{method,credentials:"same-origin",headers:data?{"Content-Type":"application/json"}:{},body:data?JSON.stringify(data):undefined,cache:"no-store"});
  const value = await response.json();
  if (!response.ok) throw Error(errors[value.error]||"本次未完成，请联系教师确认服务状态。不要连续重复提交。");
  return value;
}
function message(s) { $("message").textContent=s; }
function showSession(s) {
  session=s; $("login").hidden=true; $("workspace").hidden=false; $("demo").hidden=!s.is_demo;
  $("identity").textContent="本人会话 · "+s.student_code+" · 仅当前账号可访问";
  $("secret").value="";
}
function showResult(value) {
  $("editor").open=false; $("report-title").textContent="报告题目："+value.report_title;
  $("summary").textContent=value.feedback.summary; $("warnings").replaceChildren(); $("dimensions").replaceChildren();
  for (const warning of value.material_check.warnings) {const li=document.createElement("li");li.textContent=warning;$("warnings").append(li);}
  for (const dimension of value.feedback.dimensions) {
    const section=document.createElement("article"), heading=document.createElement("h3");
    heading.textContent=labels[dimension.dimension]+" · "+states[dimension.status]+(value.feedback.priorities.includes(dimension.dimension)?" · 优先关注":"");
    section.append(heading);
    for (const text of [(dimension.quote?dimension.paragraph_id+" 原文："+dimension.quote:"报告中未见相应内容"),"判断："+dimension.observation,"行动："+dimension.action]) {const p=document.createElement("p");p.textContent=text;section.append(p);}
    $("dimensions").append(section);
  }
  $("notice").textContent=value.notice; $("result").hidden=false;
}
$("login-form").addEventListener("submit", async e=>{
  e.preventDefault(); message("正在登录……");
  try {showSession(await api("/api/login","POST",{student_code:$("code").value.trim(),secret:$("secret").value,consent:$("consent").checked}));message("已进入本人会话。请先去除报告封面的身份信息。");} catch(error){message(error.message);}
});
$("report-form").addEventListener("submit",async e=>{
  e.preventDefault(); $("submit-report").disabled=true; $("result").hidden=true; message("正在生成六维反馈，请保持页面打开，勿重复提交……");
  try {const value=await api("/api/feedback","POST",{conversation_id:session.conversation_id,report_title:$("title").value,report_text:$("report").value,feedback_request:$("focus").value,references:$("references").value,raw_analysis:$("analysis").value,evidence_cards:$("cards").value});showResult(value);message("已完成本轮反馈。请自行核对文献与修改建议。");}catch(error){message(error.message);}finally{$("submit-report").disabled=false;}
});
$("logout").addEventListener("click",async()=>{try{await api("/api/logout","POST",{});location.reload();}catch(error){message(error.message);}});
$("clear").addEventListener("click",async()=>{try{await api("/api/sessions/"+session.conversation_id,"DELETE");$("result").hidden=true;$("dimensions").replaceChildren();message("已清除服务内存中的反馈。模型服务商记录不由此按钮删除。");}catch(error){message(error.message);}});
api("/api/me").then(async s=>{showSession(s);const value=await api("/api/sessions/"+s.conversation_id);if(value.latest)showResult(value.latest);}).catch(()=>{});
