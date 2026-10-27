'use strict';
const form=document.getElementById('login-form');
const errorMessage=document.getElementById('login-error');
const submitButton=document.getElementById('login-submit');
form.addEventListener('submit',async event=>{
 event.preventDefault();
 if(submitButton.disabled)return;
 errorMessage.textContent='';submitButton.disabled=true;submitButton.textContent='로그인 확인 중…';
 try{
  const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json','X-Shinsu-Client':'web'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:'로그인하지 못했어요. 입력 내용을 확인해 주세요.');}
  form.elements.code.value='';
  // 잡지식: 돌아갈 주소를 내부 경로로 고정하면 로그인 뒤 엉뚱한 사이트로 새지 않아요.
  window.location.replace('/sikangi'+window.location.hash);
 }catch(error){errorMessage.textContent=error instanceof TypeError?'서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.':error.message;}
 finally{submitButton.disabled=false;submitButton.textContent='로그인하고 학습 시작하기 →';}
});
