const $ = selector => document.querySelector(selector);
const labels = {hp:'체력',atk:'공격력',def:'방어력',spd:'속도',crit:'치명타'};
const grades = {normal:'일반',advanced:'고급',rare:'희귀',hero:'영웅',legend:'전설',relic:'유물',ancient:'고대'};
const effectLabels={basic_dmg:'기본기 피해',unique_dmg:'고유기 피해',ultimate_dmg:'궁극기 피해',crit_dmg:'치명타 피해',boss_dmg:'보스 피해',first3_dmg:'첫 3턴 피해',high_hp_dmg:'HP 50% 이상 피해',low_hp_dmg:'HP 30% 이하 피해',spd_adv_dmg:'속도 우위 피해',lifesteal:'흡혈량',extra_hit:'추가타 확률',gold_gain:'골드 획득',train_exp:'훈련 경험치',happiness_gain:'행복 획득',dmg_red:'피해 감소',boss_dmg_red:'보스 피해 감소',low_hp_dmg_red:'저체력 피해 감소',first3_dmg_red:'첫 3턴 피해 감소',heal_bonus:'회복량',turn_regen:'턴 종료 회복',shield_bonus:'보호막 효과',crit_dmg_red:'치명타 피해 감소',half_dmg_chance:'피해 반감 확률',hunger_slow:'포만감 감소 완화',clean_slow:'청결 감소 완화',energy_save:'생활 에너지 절약'};
const speciesAssets = {'호랑이':'tiger','사자':'lion','늑대':'wolf','드래곤':'dragon','불사조':'phoenix','현무':'turtle','구미호':'fox','그리핀':'griffin','기린':'kirin','바하무트':'bahamut'};
const statColors={hp:'#155b3a',atk:'#d94841',def:'#3478c5',spd:'#7651b5',crit:'#d6a514'};
const statNames={hp:'HP',atk:'ATK',def:'DEF',spd:'SPD',crit:'CRIT'};
const gemNames={hp:'체력의 에메랄드',atk:'공격의 루비',def:'수호의 사파이어',spd:'신속의 자수정',crit:'치명의 토파즈'};
function statIcon(kind,heart=false){
  // SVG는 기기에 이모지 글꼴이 없어도 같은 모양으로 보인다.
  const paths={hp:'M12 21 3 12C-3 4 7-1 12 6 17-1 27 4 21 12Z',atk:'m15 2 7 0 0 7-10 10-7-7Z M3 16l5 5 M2 22l4-4',def:'M12 2 22 6 20 15 12 22 4 15 2 6Z',spd:'M14 1 3 14h8l-1 9 11-14h-8Z',crit:'m12 1 3 7 7-4-4 8 5 4-8 1-3 6-3-7-8 2 5-7-4-6 8 3Z'};
  return `<svg class="stat-icon icon-${heart?kind:kind==='hp'?'heart':kind}" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[heart?'hp':kind]}"/></svg>`;
}
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
async function loadAccountNames(){
  try{
    const names=await api('/api/account-names');
    $('#account-select').innerHTML=Object.entries(names).map(([account,name])=>`<option value="${esc(account)}">${esc(name)}</option>`).join('');
  }catch(error){/* 접속 전 이름 조회 실패 시 HTML 기본 이름으로 로그인한다. */}
}
async function loadSignupStatus(){
  try{const status=await api('/api/signup-status');$('#signup-open').hidden=!status.available;}
  catch(error){$('#signup-open').hidden=true;}
}
function showLogin(){ $('#login').hidden=false; $('#game').hidden=true; $('#logout').hidden=true; player=null; pending=null; }
function button(title,action,fields={}){return `<button data-action="${action}" ${Object.entries(fields).map(([k,v])=>`data-${k}="${esc(v)}"`).join(' ')}>${esc(title)}</button>`;}
function battleSummary(){const s=player.stats;return `<strong>내 전투 정보 · CP ${s.combat_power.toLocaleString()}</strong><span>Lv.${player.pet.level}</span>${Object.entries(labels).map(([k,label])=>`<span style="--stat-color:${statColors[k]}">${label} ${s[k==='hp'?'max_hp':k].toLocaleString()}</span>`).join('')}`;}
function statPentagon(){
  const s=player.stats, raw=[s.max_hp/4,s.atk,s.def,s.spd,s.crit], peak=Math.max(...raw,1);
  const point=(i,r)=>{const a=-Math.PI/2+i*Math.PI*2/5;return `${100+Math.cos(a)*r},${100+Math.sin(a)*r}`;};
  const rings=[24,48,72].map(r=>`<polygon points="${[0,1,2,3,4].map(i=>point(i,r)).join(' ')}"/>`).join('');
  const shape=raw.map((v,i)=>point(i,24+48*v/peak)).join(' ');
  const axes=[0,1,2,3,4].map(i=>{const [x,y]=point(i,72).split(',');return `<line x1="100" y1="100" x2="${x}" y2="${y}"/>`;}).join('');
  const values=Object.entries(labels).map(([k,label])=>`<div class="stat-value" aria-label="${label}">${statIcon(k)}<span>${statNames[k]}</span><strong>${s[k==='hp'?'max_hp':k].toLocaleString()}</strong></div>`).join('');
  const captions=Object.keys(labels).map((k,i)=>{const [x,y]=point(i,89).split(',');return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle">${statNames[k]}</text>`;}).join('');
  return `<div class="combat-power">전투력 <strong>${s.combat_power.toLocaleString()}</strong></div><div class="stat-layout"><div class="stat-radar"><svg viewBox="0 0 220 210" role="img" aria-label="5대 전투 스탯 오각형"><g transform="translate(10 5)"><g class="radar-grid">${rings}${axes}</g><polygon class="radar-value" points="${shape}"/>${captions}</g></svg></div><div class="stat-values">${values}</div></div>`;
}
function render(){
  const pet=player.pet, inv=player.inventory;
  $('#greeting').textContent=`${player.nickname} 테이머의 정원`;
  const portrait=$('#pet-art'), slug=speciesAssets[pet.species_key], stage=Math.max(1,Math.min(4,Number(pet.stage)||1));
  $('#pet-fallback').textContent=pet.emoji || '🐾';
  portrait.alt=`${pet.species_name} ${stage}단계 ${pet.name}`;
  portrait.hidden=!slug;
  if(slug) portrait.src=`/assets/game-assets/species/${slug}/stage${stage}.webp`;
  portrait.onerror=()=>{portrait.hidden=true;};
  $('#pet-name').textContent=pet.name;
  $('#rename-input').value=pet.name;
  $('#rename-count').textContent=`${[...pet.name].length} / 15`;
  $('#pet-role').textContent=`${pet.species_name} · ${pet.role}`;
  $('#pet-level').textContent=`Lv.${pet.level} · 경험치 ${pet.exp} / ${pet.max_exp} · ${pet.coins.toLocaleString()} 골드`;
  $('#pet-state').textContent=pet.is_sleeping?'지금은 꿈속을 여행 중이에요.':pet.is_sick?'몸이 좋지 않아요. 치료가 필요해요.':'오늘은 어떤 모험을 해볼까요?';
  const rerollsUsed=Number(player.initial_rerolls_used)||0;
  $('#initial-reroll').hidden=pet.level!==1||rerollsUsed>=3;
  $('#initial-reroll').textContent=`🎲 초기 신수 무료 다시 뽑기 · ${3-rerollsUsed}회 남음`;
  $('#meters').innerHTML=[['포만감',pet.hunger,100],['청결',pet.cleanliness,100],['행복',pet.happiness,100],['건강',pet.health,100],['생활 에너지',pet.energy,player.max_energy],['모험 기력',pet.stamina,player.max_stamina]].map(([n,v,m])=>`<div class="meter"><label>${n}<span>${v}/${m}</span></label><progress aria-label="${n}" max="${m}" value="${v}"></progress></div>`).join('');
  $('#stats').innerHTML=statPentagon();
  for(const panel of ['adventure','raid']){let summary=$(`#${panel}-my-stats`);if(!summary){summary=document.createElement('div');summary.id=`${panel}-my-stats`;summary.className='battle-summary';$(`#panel-${panel} h2`).insertAdjacentElement('afterend',summary);}summary.innerHTML=battleSummary();}
  $('#coins').textContent=`보유 골드 ${pet.coins.toLocaleString()}G`;
  $('#equipment').innerHTML=`<p>장착 방어구: ${esc(inv.equipped_armor?.armor_id||'없음')} · 보물: ${esc(inv.equipped_relic?.species||'없음')}</p>`+inv.armors_inventory.map((a,i)=>`<div class="row"><span>${esc(a.armor_id)} +${a.level}</span>${button('장착','equip_armor',{index:i})}</div>`).join('')+inv.relics_inventory.map((a,i)=>`<div class="row"><span>${esc(a.species)} 보물 +${a.level}</span>${button('장착','equip_relic',{index:i})}</div>`).join('');
  $('#gems').innerHTML=Object.keys(labels).map(gem=>`<section class="gem-group"><h4>${statIcon(gem,true)}<span>${gemNames[gem]}</span><b aria-label="장착 보석 레벨">Lv.${inv.equipped_gems[gem]||0}</b></h4>`+Object.entries(inv.gems[gem]||{}).filter(([,n])=>n>0).map(([level,n])=>`<div class="row"><span><b>Lv.${level}</b> · ${n}개</span>${button('장착','equip_gem',{gem,level})}${Number(level)<10?button('2개 합성','synthesize',{gem,level}):''}</div>`).join('')+`</section>`).join('');
  $('#items').innerHTML=Object.entries(inv.items).filter(([,n])=>n>0).map(([item,n])=>`<div class="row"><span>${esc(catalog.items[item]?.name||item)} × ${n}</span>${catalog.items[item]?.exp || ['holy_water','primordial_heart'].includes(item)?button('사용','use',{item}):''}</div>`).join('');
  $('#engravings').innerHTML=['relic','armor'].map(kind=>`<h3>${kind==='relic'?'보물':'방어구'}</h3>`+inv[`${kind}_engravings`].map((row,slot)=>`<div class="row"><span>${row?esc(`${grades[row.grade]} · ${labels[row.option]||effectLabels[row.option]||row.option} +${row.value}${labels[row.option]?'':'%'}`):'빈 슬롯'}</span>${button(inv[`${kind}_engraving_locks`][slot]?'잠금 해제':'잠금','lock',{kind,slot})}${button('재설정','reroll',{kind,slot})}</div>`).join('')).join('');
  $('#growth-gate').textContent=player.level_cap[1];
  $('#growth-skills').innerHTML=Object.values(player.skills).map(s=>`<div class="tile"><h3>${esc(s.name)}</h3><p>${esc(s.desc)}</p></div>`).join('');
  $('#potential-stats').innerHTML=Object.entries(labels).map(([gem,label])=>{const step=Math.round((pet.potential_growth[gem]||0)/0.03);return `<div class="row"><span>${label} +${Math.round((pet.potential_growth[gem]||0)*100)}%${step<20?` · ${['일반','고급','전설','신화'][Math.floor(step/5)]} 혼 ${[1,4,9,16,25][step%5]}개 필요`:''}</span>${step<20?button('잠재 +3%','potential',{gem}):'최대 성장'}</div>`;}).join('');
  $('#forge-summary').textContent=`보물 강화 상한 +${player.relic_cap} · 장착 보물 +${inv.equipped_relic?.level||0} · 방어구 +${inv.equipped_armor?.level||0} / ★${inv.equipped_armor?.stars||0} · 종족 정수 ${inv.species_essences?.[pet.species_key]||0}개`;
  $('#dismantle-list').innerHTML=inv.relics_inventory.map((r,index)=>`<div class="row"><span>${esc(r.species)} 보물 +${r.level}</span>${button('분해','dismantle_relic',{index})}</div>`).join('');
  $('#shop-items').innerHTML=Object.entries(catalog.items).filter(([,item])=>item.price>0).map(([item,value])=>`<div class="tile"><h3>${esc(value.name)}</h3><p>${esc(value.desc)}</p>${button(`${value.price.toLocaleString()}G · 1개 구매`,'buy',{item})}</div>`).join('');
  $('#battle-log').textContent=player.last_battle?player.last_battle.message+'\n\n'+player.last_battle.log.join('\n'):'아직 전투 기록이 없습니다.';
  renderRaids();
}
function renderRaids(){
  if(!player)return;
  const tier=Number($('#raid-tier').value)||1, cleared=player.pet.raid_clears[String(tier)]||[];
  $('#raid-gates').innerHTML=`<strong>입장 레벨 Lv.${catalog.raid_levels[tier]}</strong> · 내 레벨 Lv.${player.pet.level} · 토벌 ${cleared.length}/${tier===5?5:4}<br>${esc(player.level_cap[1])}`;
  $('#raid-bosses').innerHTML=Object.entries(catalog.bosses).filter(([id])=>Number(id)!==5||tier===5).map(([boss,b])=>`<div class="tile"><img class="boss-art" loading="lazy" src="/assets/game-assets/bosses/${['ancient_ent','crystal_dragon','ifrit','nebula','omega'][Number(boss)-1]}.webp" alt="${esc(b.name)}"><h3>${esc(b.emoji)} ${esc(b.name)} ${cleared.includes(Number(boss))?'✓':''}</h3><p>${esc(b.desc)}</p><p>기본 기력 ${b.energy_cost}</p>${button('혼자 도전','raid',{boss,tier})}${button('협동 방 만들기','raid_create',{boss,tier})}</div>`).join('');
}
async function loadRooms(){
  if(!player)return;
  try{const rooms=await api('/api/raids');$('#raid-rooms').innerHTML=rooms.filter(r=>r.status==='waiting' && r.created>Date.now()/1000-900).map(r=>`<div class="row"><span>${esc(catalog.bosses[r.boss].name)} · ${esc(catalog.raid_difficulties[r.tier].name)}</span>${button(r.host===player.account?'방 취소':'참가하여 전투 시작',r.host===player.account?'raid_cancel':'raid_join',{room:r.id})}</div>`).join('')||'<p>대기 중인 방이 없습니다.</p>';}catch(error){$('#notice').textContent=error.message;}
}
async function enter(){
  [player,catalog]=await Promise.all([api('/api/me'),api('/api/catalog')]);
  $('#login').hidden=true; $('#game').hidden=false; $('#logout').hidden=false;
  $('#difficulty').innerHTML=Object.entries(catalog.difficulties).map(([id,d])=>`<option value="${id}">${esc(d.name)}</option>`).join('');
  $('#raid-tier').innerHTML=Object.entries(catalog.raid_difficulties).map(([id,d])=>`<option value="${id}">${esc(d.name)}</option>`).join('');
  $('#dungeons').innerHTML=Object.entries(catalog.dungeons).map(([id,d])=>`<div class="tile"><h3>${esc(d.emoji)} ${esc(d.name)}</h3><p>입장 레벨: ${Object.entries(d.req_lvl).map(([tier,l])=>`${esc(catalog.difficulties[tier]?.name||tier)} ${l}`).join(' / ')}</p>${button('1회 탐험','dungeon',{dungeon:id})}</div>`).join('');
  render();
  await loadRooms();
}
async function action(data){
  if(busy)return;
  busy=true; $('#notice').textContent='';
  const signature=JSON.stringify(data);
  if(pending && pending.signature!==signature){busy=false;$('#notice').textContent='이전 요청 결과를 확인하지 못했어요. 같은 행동을 다시 눌러 확인해 주세요.';return;}
  pending ||= {signature,body:{...data,request_id:crypto.randomUUID()}};
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{const result=await api('/api/actions',pending.body);player=result.player;pending=null;render();$('#message').textContent=result.message;if(data.action.startsWith('raid'))await loadRooms();}
  catch(error){if(error.status && error.status<500)pending=null;$('#notice').textContent=error.message;}
  finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
$('#login-form').addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));try{await api('/api/login',data);event.target.code.value='';await enter();$('#notice').textContent='';}catch(error){$('#notice').textContent=error.message;}});
$('#signup-open').addEventListener('click',()=>{$('#login-form').hidden=true;$('#signup-open').hidden=true;$('#signup-form').hidden=false;$('#signup-form').nickname.focus();});
$('#signup-cancel').addEventListener('click',()=>{$('#signup-form').hidden=true;$('#login-form').hidden=false;$('#signup-open').hidden=false;});
$('#signup-form').addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));try{await api('/api/signup',data);event.target.reset();await loadAccountNames();await enter();$('#notice').textContent='';}catch(error){$('#notice').textContent=error.message;}});
$('#logout').addEventListener('click',async()=>{try{await api('/api/logout',{});showLogin();}catch(error){$('#notice').textContent=error.message;}});
$('#rename-open').addEventListener('click',()=>{$('#rename-form').hidden=false;$('#rename-input').focus();$('#rename-input').select();});
$('#rename-cancel').addEventListener('click',()=>{$('#rename-form').hidden=true;$('#rename-input').value=player.pet.name;});
$('#rename-input').addEventListener('input',event=>{$('#rename-count').textContent=`${[...event.target.value].length} / 15`;});
$('#rename-form').addEventListener('submit',event=>{event.preventDefault();action({action:'rename',name:$('#rename-input').value});});
$('#reincarnate-form').addEventListener('submit',event=>{event.preventDefault();action({action:'reincarnate',confirmation:event.target.confirmation.value});});
$('#raid-tier').addEventListener('change',renderRaids);
$('#raid-refresh').addEventListener('click',loadRooms);
document.addEventListener('click',event=>{
  const tab=event.target.closest('[data-tab]');
  if(tab){document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b===tab)));document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==`panel-${tab.dataset.tab}`);return;}
  const target=event.target.closest('[data-action]');if(!target)return;
  const data={...target.dataset};for(const key of ['slot','level','index','dungeon','boss','tier','times'])if(key in data)data[key]=Number(data[key]);
  if(data.action==='pet_reroll'&&!confirm('새 신수를 무료로 다시 뽑을까요? Lv.1에서 최대 3회 가능합니다.'))return;
  if(data.action==='dismantle_relic'&&!confirm('이 보물을 분해하고 종족 정수를 얻을까요?'))return;
  if(data.action==='dungeon')data.tier=Number($('#difficulty').value);
  if(data.action==='reroll')data.tier=Number($('#stone-tier').value);
  action(data);
});
// 접속 코드는 저장하지 않고 세션 쿠키만 사용한다. 비밀은 비밀답게!
if('serviceWorker' in navigator){navigator.serviceWorker.getRegistrations().then(registrations=>Promise.all(registrations.filter(r=>r.scope.endsWith('/assets/')).map(r=>r.unregister()))).then(()=>navigator.serviceWorker.register('/sw.js')).catch(()=>{});}
Promise.all([loadAccountNames(),loadSignupStatus()]).finally(()=>enter().catch(error=>{showLogin();if(error.status!==401)$('#notice').textContent=error.message;}));
// 두 사람만 접속하므로 짧은 상태 조회로 협동 결과를 함께 확인한다.
setInterval(async()=>{if(!player||busy||document.hidden)return;try{const next=await api('/api/me');if(!busy&&player&&next.account===player.account&&next.revision>player.revision){player=next;render();$('#message').textContent=next.last_battle?.message||'상태가 갱신되었습니다.';}await loadRooms();}catch(error){if(error.status===401)showLogin();}},5000);
