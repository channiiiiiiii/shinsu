const userId = localStorage.getItem("shisuUserId") || crypto.randomUUID();
localStorage.setItem("shisuUserId", userId);
let player;

async function request(path, options = {}) {
  const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "요청에 실패했습니다.");
  return data;
}

function renderSlots(kind) {
  const rows = player[`${kind}_engravings`];
  const locks = player[`${kind}_engraving_locks`];
  document.querySelector(`#${kind}`).innerHTML = rows.map((row, slot) => `
    <div class="slot"><span>${row ? `${row.grade} · ${row.option} +${row.value}` : "빈 각인 슬롯"}</span>
    <button onclick="reroll('${kind}',${slot})">${locks[slot] ? "🔒" : "재설정"}</button></div>`).join("");
}

function render() {
  document.querySelector("#status").textContent = `Stage ${player.growth_stage} · ${player.role}`;
  document.querySelector("#stats").innerHTML = Object.entries(player.stat_bonus).map(([key,value]) => `<div class="stat"><small>${key.toUpperCase()}</small><b>+${value}</b></div>`).join("");
  renderSlots("relic"); renderSlots("armor");
}

async function reroll(kind, slot) {
  try {
    const data = await request(`/api/players/${userId}/engravings/reroll`, {method:"POST", body:JSON.stringify({kind,slot,tier:1})});
    player = data.player; render();
  } catch (error) { alert(error.message); }
}

async function load() {
  player = await request(`/api/players/${userId}`); render();
  document.querySelector("#status").textContent += " · 온라인";
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/assets/sw.js");
load().catch(error => document.querySelector("#status").textContent = error.message);

