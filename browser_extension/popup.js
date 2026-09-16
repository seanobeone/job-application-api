const $=id=>document.getElementById(id);
async function assist(){const id=$('job').value.trim(); if(!id)throw new Error('Enter Job ID'); const r=await fetch(`http://127.0.0.1:8021/jobs/${id}/assist`); if(!r.ok)throw new Error(await r.text()); return r.json();}
$('info').onclick=async()=>{try{let a=await assist(); $('status').textContent=`Resume: ${a.recommended_resume || 'review'} | ${a.resume_path || 'path unavailable'}`;}catch(e){$('status').textContent=e.message}};
$('fill').onclick=async()=>{try{let a=await assist(); let [tab]=await chrome.tabs.query({active:true,currentWindow:true}); let res=await chrome.scripting.executeScript({target:{tabId:tab.id},func:fillPage,args:[a.answers]}); $('status').textContent=`Filled ${res[0].result.filled} known field(s). Resume: ${a.recommended_resume||'review'}`;}catch(e){$('status').textContent=e.message}};
function fillPage(ans){
 const auto=(s,k)=>{let x=ans?.[s]?.[k]; return x&&x.mode==='auto'?x.answer:null}; let filled=0;
 const set=(selectors,val)=>{if(val===null||val===undefined||val==='')return; for(const sel of selectors){for(const e of document.querySelectorAll(sel)){if(!e.disabled&&e.offsetParent!==null&&!e.value){e.focus();e.value=String(val);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));filled++;return}}}};
 const labelSet=(rx,val)=>{if(val===null||val===undefined||val==='')return; for(const e of document.querySelectorAll('input,textarea')){let id=e.id;let lab=id?document.querySelector(`label[for="${CSS.escape(id)}"]`):null;let text=(lab?.innerText||e.getAttribute('aria-label')||e.name||e.placeholder||'');if(rx.test(text)&&!e.value){e.focus();e.value=String(val);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));filled++;return}}};
 set(['input[type=email]','input[name*="email" i]'],auto('contact','email')); set(['input[type=tel]','input[name*="phone" i]'],auto('contact','phone')); set(['input[name*="linkedin" i]'],auto('contact','linkedin')); set(['input[name*="portfolio" i]','input[name*="website" i]'],auto('contact','portfolio')); labelSet(/salary|compensation/i,auto('compensation','desired_salary'));
 // Intentionally no automatic clicking of radio buttons, navigation, CAPTCHA, file upload, or Submit.
 return {filled};
}
