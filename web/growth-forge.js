// 판정은 서버에 맡기고, 여기서는 진행도와 결과 공개만 담당한다.
const forgeMessages={};
const forgeActions=['enhance_relic','enhance_armor','ascend_armor'];
const statKey=k=>k==='max_hp'?'hp':k;
function renderPotential(){
  const tiers=['노말','하드','악몽','신화'],souls=['⚪ 일반 혼','🔵 고급 혼','🟣 전설 혼','🟡 신화 혼'];
  $('#potential-stats').innerHTML=Object.entries(labels).map(([key,label])=>{
    const step=Math.max(0,Math.min(20,Math.round((player.pet.potential_growth[key]||0)/.03))),max=step===20;
    const groups=tiers.map((tier,i)=>`<div class="potential-group tier-${i}"><div class="potential-cells">${Array.from({length:5},(_,j)=>`<i class="${i*5+j<step?'filled':''}"></i>`).join('')}</div><small>${tier}</small></div>`).join('');
    return `<section class="potential-row"><div class="potential-heading"><h4>${statIcon(key)}${label} <strong>+${step*3}%${max?' MAX':''}</strong></h4><button data-action="potential" data-gem="${key}" ${max?'disabled data-blocked="true"':''}>${max?'MAX':'잠재 +3%'}</button></div><div class="potential-track" role="progressbar" aria-label="${label} 잠재 성장" aria-valuenow="${step}" aria-valuemin="0" aria-valuemax="20">${groups}</div><div class="potential-caption"><span>${step} / 20단계</span><small>${max?'👑 잠재 성장 완료':`다음: ${souls[Math.floor(step/5)]} ${[1,4,9,16,25][step%5]}개`}</small></div></section>`;
  }).join('');
}
function forgeStats(before,after){
  return Object.keys(before).map(key=>`<div class="forge-stat">${statIcon(statKey(key))}<span>${statNames[statKey(key)]}</span><span>${before[key].toLocaleString()} → <b>${after[key].toLocaleString()}</b></span></div>`).join('');
}
function renderForge(){
  $('#forge-cards').innerHTML=forgeActions.map(action=>{
    const q=player.enhancements?.[action];if(!q)return '';
    const star=action==='ascend_armor',level=star?q.stars:q.level,prefix=star?'★':'+';
    const risk=q.rate<=.2?'high':q.rate<=.5?'medium':'low';
    const grade=q.level>=11?'gold':q.level>=8?'bright':q.level>=5?'soft':'base';
    const materials=q.materials.map(m=>`<div class="forge-material ${m.owned<m.required?'shortage':''}"><span>${esc(m.name)}</span><b>${m.owned.toLocaleString()} / ${m.required.toLocaleString()}${m.name==='골드'?'G':'개'}</b></div>`).join('');
    const retry=pending?.body.action===action;
    return `<article class="forge-card grade-${grade} risk-${risk}" id="forge-${action}"><small>${star?'🌌 고대 각성':action==='enhance_relic'?'🎴 보물 강화':'🛡️ 방어구 강화'}</small><h3>${esc(q.name)} <b>+${q.level}${star||q.stars?` ★${q.stars}`:''}</b></h3>${q.before?`<p class="forge-next">${prefix}${level} → <strong>${prefix}${level+1}</strong></p>${star?`<p>각성 보너스 +${q.bonus_before}% → +${q.bonus_after}%</p>`:''}<p class="forge-label">현재 → 성공 후 내 전투 스탯</p>${forgeStats(q.before,q.after)}<div class="forge-rate"><label>성공 확률 <b>${Math.round(q.rate*100)}%${star?' · 확정':''}</b></label><progress value="${q.rate*100}" max="100" aria-label="강화 성공 확률"></progress></div><h4>필요 재료</h4>${materials}`:`<p>${esc(q.reason)}</p>`}<div class="forge-stage" role="status" aria-live="polite">${forgeMessages[action]||''}</div><button class="primary" data-action="${action}" ${!q.available&&!retry?'disabled data-blocked="true"':''}>${retry?'요청 결과 다시 확인':q.available?`${star?'⭐':'🔨'} ${prefix}${level+1} ${star?'각성':'강화'} 도전`:esc(q.reason)}</button></article>`;
  }).join('');
}
function forgeAnimation(action){
  const card=$(`#forge-${action}`),box=card.querySelector('.forge-stage');
  card.classList.add('forging');
  const star=action==='ascend_armor',duration=player.enhancements[action].rate<=.2?1800:1400;
  box.innerHTML=`<b>${star?'🌌 고대의 힘을 깨우는 중…':'🔨 강화 준비 중…'}</b><progress max="100" value="10" aria-label="강화 연출 진행도"></progress>`;
  const update=(text,value)=>{box.querySelector('b').textContent=text;box.querySelector('progress').value=value;};
  const timers=[setTimeout(()=>update('⚒️ 강화 중…',50),400),setTimeout(()=>update('✨ 힘이 응축되고 있습니다…',85),900)];
  return {promise:new Promise(resolve=>setTimeout(resolve,duration)),stop(){timers.forEach(clearTimeout);card.classList.remove('forging');}};
}
function showForgeResult(action,result){
  if(!result)return;
  const star=action==='ascend_armor',prefix=star?'★':'+',before=star?result.stars:result.level;
  const spent=result.materials.map(m=>`${esc(m.name)} ${m.required.toLocaleString()}${m.name==='골드'?'G':'개'}`).join(' · ');
  forgeMessages[action]=`<div class="forge-result ${result.success?'success':'failure'}"><strong>${result.success?'✨ '+(star?'각성':'강화')+' 성공!':'💥 강화 실패…'}</strong><p>${esc(result.name)} ${prefix}${before} ${result.success?`→ ${prefix}${result.result_level}`:'유지'}</p>${result.success?forgeStats(result.before,result.after):'<p>장비는 파괴되지 않습니다.</p>'}<small>소모: ${spent}</small></div>`;
}
