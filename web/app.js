const $ = selector => document.querySelector(selector);
const labels = {hp:'체력',atk:'공격력',def:'방어력',spd:'속도',crit:'치명타'};
const grades = {normal:'일반',advanced:'고급',rare:'희귀',hero:'영웅',legend:'전설',relic:'유물',ancient:'고대'};
let player, catalog, busy = false, pending = null;
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, body) {
  const response = await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Shinsu-Client':'web'},...(body?{body:JSON.stringify(body)}:{})});
  const data = await response.json();
  if (!response.ok) {
    if(response.status===401 && path!=='/api/login') showLogin();
    const error = new Error(typeof data.detail==='string'?data.detail:'입력값을 확인해 주세요.');
    error.status=response.status; throw error;
  }
  return data;
}
function showLogin(){ $('#login').hidden=false; $('#game').hidden=true; $('#logout').hidden=true; player=null; pending=null; }
function button(title,action,fields={}){return `<button data-action="${action}" ${Object.entries(fields).map(([k,v])=>`data-${k}="${esc(v)}"`).join(' ')}>${esc(title)}</button>`;}
function render(){
  const pet=player.pet, inv=player.inventory;
  $('#greeting').textContent=`${player.nickname} 테이머의 정원`;
  $('#pet-art').textContent=pet.emoji || '🐾'; $('#pet-name').textContent=pet.name;
  $('#pet-role').textContent=`${pet.species_name} · ${pet.role}`;
  $('#pet-level').textContent=`Lv.${pet.level} · 경험치 ${pet.exp} / ${pet.max_exp} · ${pet.coins.toLocaleString()} 골드`;
  $('#pet-state').textContent=pet.is_sleeping?'지금은 꿈속을 여행 중이에요.':pet.is_sick?'몸이 좋지 않아요. 치료가 필요해요.':'오늘은 어떤 모험을 해볼까요?';
  $('#meters').innerHTML=[['포만감',pet.hunger,100],['청결',pet.cleanliness,100],['행복',pet.happiness,100],['건강',pet.health,100],['생활 에너지',pet.energy,player.max_energy],['모험 기력',pet.stamina,player.max_stamina]].map(([n,v,m])=>`<div class="meter"><label>${n}<span>${v}/${m}</span></label><progress aria-label="${n}" max="${m}" value="${v}"></progress></div>`).join('');
  $('#stats').innerHTML=Object.entries(labels).map(([k,label])=>`<span>${label}<strong>${player.stats[k==='hp'?'max_hp':k]}</strong>보석·각인 +${player.bonus[k]}</span>`).join('')+`<span>전투력<strong>${player.stats.combat_power}</strong></span>`;
  $('#coins').textContent=`보유 골드 ${pet.coins.toLocaleString()}G`;
  $('#equipment').innerHTML=`<p>장착 방어구: ${esc(inv.equipped_armor?.armor_id||'없음')} · 보물: ${esc(inv.equipped_relic?.species||'없음')}</p>`+inv.armors_inventory.map((a,i)=>`<div class="row"><span>${esc(a.armor_id)} +${a.level}</span>${button('장착','equip_armor',{index:i})}</div>`).join('')+inv.relics_inventory.map((a,i)=>`<div class="row"><span>${esc(a.species)} 보물 +${a.level}</span>${button('장착','equip_relic',{index:i})}</div>`).join('');
  $('#gems').innerHTML=Object.entries(inv.gems).map(([gem,levels])=>`<h4>${labels[gem]} · 장착 ${inv.equipped_gems[gem]?'Lv.'+inv.equipped_gems[gem]:'없음'}</h4>`+Object.entries(levels).filter(([,n])=>n>0).map(([level,n])=>`<div class="row"><span>Lv.${level} × ${n}</span>${button('장착','equip_gem',{gem,level})}${Number(level)<10?button('2개 합성','synthesize',{gem,level}):''}</div>`).join('')).join('');
  $('#items').innerHTML=Object.entries(inv.items).filter(([,n])=>n>0).map(([item,n])=>`<div class="row"><span>${esc(catalog.items[item]?.name||item)} × ${n}</span>${item.includes('candy')?button('사용','use',{item}):''}</div>`).join('');
  $('#engravings').innerHTML=['relic','armor'].map(kind=>`<h3>${kind==='relic'?'보물':'방어구'}</h3>`+inv[`${kind}_engravings`].map((row,slot)=>`<div class="row"><span>${row?esc(`${grades[row.grade]} · ${labels[row.option]||row.option} +${row.value}`):'빈 슬롯'}</span>${button(inv[`${kind}_engraving_locks`][slot]?'잠금 해제':'잠금','lock',{kind,slot})}${button('재설정','reroll',{kind,slot})}</div>`).join('')).join('');
}
async function enter(){
  [player,catalog]=await Promise.all([api('/api/me'),api('/api/catalog')]);
  $('#login').hidden=true; $('#game').hidden=false; $('#logout').hidden=false;
  $('#difficulty').innerHTML=Object.entries(catalog.difficulties).map(([id,d])=>`<option value="${id}">${esc(d.name)}</option>`).join('');
  $('#dungeons').innerHTML=Object.entries(catalog.dungeons).map(([id,d])=>`<div class="tile"><h3>${esc(d.emoji)} ${esc(d.name)}</h3><p>입장 레벨: ${Object.entries(d.req_lvl).map(([tier,l])=>`${esc(catalog.difficulties[tier]?.name||tier)} ${l}`).join(' / ')}</p>${button('1회 탐험','dungeon',{dungeon:id})}</div>`).join('');
  render();
}
async function action(data){
  if(busy)return;
  busy=true; $('#notice').textContent='';
  const signature=JSON.stringify(data);
  if(pending && pending.signature!==signature){busy=false;$('#notice').textContent='이전 요청 결과를 확인하지 못했어요. 같은 행동을 다시 눌러 확인해 주세요.';return;}
  pending ||= {signature,body:{...data,request_id:crypto.randomUUID()}};
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{const result=await api('/api/actions',pending.body);player=result.player;pending=null;render();$('#message').textContent=result.message;}
  catch(error){if(error.status && error.status<500)pending=null;$('#notice').textContent=error.message;}
  finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
$('#login-form').addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));try{await api('/api/login',data);event.target.code.value='';await enter();$('#notice').textContent='';}catch(error){$('#notice').textContent=error.message;}});
$('#logout').addEventListener('click',async()=>{try{await api('/api/logout',{});showLogin();}catch(error){$('#notice').textContent=error.message;}});
document.addEventListener('click',event=>{
  const tab=event.target.closest('[data-tab]');
  if(tab){document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b===tab)));document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==`panel-${tab.dataset.tab}`);return;}
  const target=event.target.closest('[data-action]');if(!target)return;
  const data={...target.dataset};for(const key of ['slot','level','index','dungeon'])if(key in data)data[key]=Number(data[key]);
  if(data.action==='dungeon')data.tier=Number($('#difficulty').value);
  if(data.action==='reroll')data.tier=Number($('#stone-tier').value);
  action(data);
});
// 접속 코드는 저장하지 않고 세션 쿠키만 사용한다. 비밀은 비밀답게!
if('serviceWorker' in navigator){navigator.serviceWorker.getRegistrations().then(registrations=>Promise.all(registrations.filter(r=>r.scope.endsWith('/assets/')).map(r=>r.unregister()))).then(()=>navigator.serviceWorker.register('/sw.js')).catch(()=>{});}
enter().catch(error=>{showLogin();if(error.status!==401)$('#notice').textContent=error.message;});
