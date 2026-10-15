'use strict';
const $ = id => document.getElementById(id);
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { worlds: [], campaigns: [], active: null, world: null, messages: [], busy: false, lastNarration: '', neuralAvailable: false, speechPaused: false, speaking: false, detailTab: 'scene' };

async function request(url, { method = 'GET', body, raw = false } = {}) {
  const options = {method};
  if(body !== undefined) {
    options.body = raw ? body : JSON.stringify(body);
    options.headers = raw ? {'Content-Type': 'application/zip'} : {'Content-Type': 'application/json'};
  }
  let response;
  try { response = await fetch(url, options); }
  catch(e) { throw new Error('Cannot connect to Storyforge. Is the server running?'); }
  let result;
  try { result = await response.json(); }
  catch(e) { throw new Error('Server returned an unreadable response.'); }
  if(!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function toast(text, fail = false) {
  const node = $('toast'); node.textContent = text; node.classList.remove('hidden'); node.classList.toggle('error', fail);
  clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.add('hidden'), 5000);
}
async function refreshLibrary() {
  const [a,b] = await Promise.all([request('/api/worlds'), request('/api/campaigns')]);
  state.worlds = a.worlds; state.campaigns = b.campaigns;
  $('library-count').textContent = state.worlds.length + ' worlds';
  $('worlds').innerHTML = state.worlds.map((w,i) => `<article class="world-card" data-world="${escapeHtml(w.id)}"><div class="card-art art-${i%5}"><span>✦</span></div><div class="world-card-body"><div class="eyebrow">${escapeHtml(w.section_count)} LORE ENTRIES</div><h3>${escapeHtml(w.title)}</h3><p>${escapeHtml(w.description || 'A world waiting for its story to begin.')}</p><div class="byline">Created by ${escapeHtml(w.author)}</div><button class="button secondary start-world" data-world="${escapeHtml(w.id)}">Start adventure →</button></div></article>`).join('');
  $('campaign-links').innerHTML = `<div class="rail-popup-title">SAVED ADVENTURES</div>` + (state.campaigns.map(c => `<button class="nav campaign-link ${state.active?.id===c.id?'active':''}" data-campaign="${escapeHtml(c.id)}"><span>✧</span><span class="truncate">${escapeHtml(c.title)}</span></button>`).join('') || '<div class="empty-side">No adventures yet</div>');
  $('campaign-cards').innerHTML = state.campaigns.map(c => `<article class="saved-adventure"><div><span class="eyebrow">CONTINUE ADVENTURE</span><h3>${escapeHtml(c.title)}</h3><p class="muted">Playing as ${escapeHtml(c.pc_name)}</p></div><button class="button secondary reopen-campaign" data-campaign="${escapeHtml(c.id)}">Continue story →</button></article>`).join('') || '<p class="muted">Your adventures will appear here after you create a character.</p>';
  document.querySelectorAll('.start-world').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); showCharacterModal(b.dataset.world); }));
  document.querySelectorAll('.campaign-link, .reopen-campaign').forEach(b => b.addEventListener('click', () => openCampaign(b.dataset.campaign)));
}
function toLibrary(){
  $('adventure').classList.add('hidden'); $('library').classList.remove('hidden');
  $('nav-worlds').classList.add('active'); $('nav-story').classList.remove('active');
  $('campaign-links').classList.add('hidden');document.querySelector('.details').classList.remove('show-on-mobile');
  $('breadcrumb').textContent='Your library / Worlds'; state.active=null; stopSpeech(); refreshLibrary().catch(e=>toast(e.message,true));
}
function showModal(eyebrow,title,content) {
  $('modal-eyebrow').textContent=eyebrow; $('modal-title').textContent=title;
  $('modal-content').innerHTML=content; $('modal').classList.remove('hidden');
}
function closeModal() { $('modal').classList.add('hidden'); }
const inp = (id,label,placeholder='',type='text',required=false) => `<label class="field"><span>${label}</span><input id="${id}" type="${type}" placeholder="${escapeHtml(placeholder)}" ${required?'required':''}></label>`;
function showImportModal() {
  showModal('A NEW STORY', 'Import a community world', `<p class="muted modal-intro">Bring in a world shared by its creator. We never scrape or automatically download content from Friends & Fables.</p><div class="tab-switch"><button class="tab active" id="text-tab">Paste world lore</button><button class="tab" id="zip-tab">Import creator ZIP</button></div><form id="import-form">
    ${inp('world-title','WORLD NAME','e.g. The Shadow Kingdom','text',true)}
    ${inp('world-author','ORIGINAL CREATOR','Name or username')}
    ${inp('world-url','ORIGINAL WORLD LINK (ATTRIBUTION)','https://play.fables.gg/worlds/...','url')}
    <div id="import-text-fields"><label class="field"><span>WORLD OVERVIEW / LORE</span><textarea id="world-lore" rows="8" placeholder="Paste the world description, lore, characters and locations that the creator has shared..." required></textarea></label></div>
    <div id="import-zip-fields" class="hidden"><label class="field"><span>CREATOR-PROVIDED WORLD EXPORT (.ZIP)</span><input id="world-zip" type="file" accept=".zip,application/zip"></label><p class="muted note">Supports Markdown and JSON in CDF-style archives. Images and specialised game rules are not yet imported.</p></div>
    <button class="button primary full" type="submit">Import world →</button></form><p class="muted note">A public world link is stored as attribution, not used to fetch private or copyrighted data.</p>`);
  let mode='text';
  for(const kind of ['text','zip']) $(kind+'-tab').onclick=()=>{
    mode=kind;
    $('text-tab').classList.toggle('active',kind==='text'); $('zip-tab').classList.toggle('active',kind==='zip');
    $('import-text-fields').classList.toggle('hidden',kind==='zip'); $('import-zip-fields').classList.toggle('hidden',kind==='text');
    $('world-lore').required=kind==='text';
  };
  $('import-form').onsubmit=async e=>{
    e.preventDefault();
    const title=$('world-title').value.trim(),author=$('world-author').value.trim(),source_url=$('world-url').value.trim();
    if(!title){toast('Enter a world name',true);return;}
    const submit=e.target.querySelector('button[type=submit]'); submit.disabled=true; submit.textContent='Importing...';
    try {
      if(mode==='text') await request('/api/worlds',{method:'POST',body:{title,author,source_url,description:$('world-lore').value.slice(0,4500),sections:[{title:'Shared world lore',kind:'lore',content:$('world-lore').value}]}});
      else {
        const file=$('world-zip').files[0]; if(!file) throw new Error('Choose a ZIP export first.');
        const params=new URLSearchParams({title,author,source:source_url});
        await request('/api/worlds/import-zip?'+params.toString(), {method:'POST',body:await file.arrayBuffer(),raw:true});
      }
      closeModal(); await refreshLibrary(); toast('World successfully added to your library');
    }catch(err){toast(err.message,true)}finally {submit.disabled=false;submit.textContent='Import world →';}
  };
}
const charText = (id, label, hint='', rows=2, value='') => `<label class="field"><span>${label}</span><textarea id="${id}" rows="${rows}" placeholder="${escapeHtml(hint)}">${escapeHtml(value)}</textarea></label>`;
const charField = (id, label, hint='', value='') => `<label class="field"><span>${label}</span><input id="${id}" type="text" placeholder="${escapeHtml(hint)}" value="${escapeHtml(value)}"></label>`;
function characterForm(world, campaign=null) {
  const pc=campaign?.pc_profile||{};
  const read=(key)=>pc[key]||'';
  const abilities=Array.isArray(pc.abilities)?pc.abilities.join('\n'):'';
  const t=campaign ? 'Save character changes' : 'Create adventure →';
  return `<div class="world-preview">${escapeHtml(world.description)}</div>
    <form id="character-form">
      ${!campaign?charField('campaign-title','ADVENTURE TITLE',`A Story in ${world.title}`):''}
      <div class="form-section"><div class="eyebrow">IDENTITY</div>
        <label class="field"><span>CHARACTER NAME</span><input id="pc-name" value="${escapeHtml(campaign?.pc_name||'')}" placeholder="Your character's name" required></label>
        <div class="form-grid">${charField('pc-pronouns','PRONOUNS','he/him, she/her, they/them',read('pronouns'))}${charField('pc-species','RACE / SPECIES','High Elf',read('species'))}</div>
        <div class="form-grid">${charField('pc-role','CLASS / ROLE','Monarch, sorcerer, wanderer',read('role'))}${charField('pc-alignment','ALIGNMENT / OUTLOOK','Lawful, pragmatic, merciful…',read('alignment'))}</div>
        ${charField('pc-aliases','ALIASES / TITLES','The Dark Monarch; King of Shadows',read('aliases'))}
      </div>
      <div class="form-section"><div class="eyebrow">CHARACTER PORTRAYAL</div>
        ${charText('pc-appearance','APPEARANCE','Physical appearance, clothing, features…',3,read('appearance')||read('description'))}
        ${charText('pc-personality','PERSONALITY','Beliefs, temperament, values, social behaviour…',3,read('personality'))}
        ${charText('pc-mannerisms','MANNERISMS','Gestures, recurring habits, speech patterns, expressions…',3,read('mannerisms'))}
      </div>
      <div class="form-section"><div class="eyebrow">YOUR STORY</div>
        ${charText('pc-background','BACKSTORY / HISTORY','Your history before this adventure…',3,read('background'))}
        ${charText('pc-motivation','MOTIVATIONS / GOALS','What does your character want?',2,read('motivation'))}
        ${charText('pc-weaknesses','FLAWS / WEAKNESSES','Meaningful vulnerabilities, fears, limitations…',2,read('weaknesses'))}
        <div class="form-grid">${charField('pc-faction','FACTIONS / CONNECTIONS','Allies, followers, enemies',read('faction'))}${charField('pc-starting_location','PREFERRED START','Optional location',read('starting_location'))}</div>
      </div>
      <div class="form-section"><div class="eyebrow">ABILITIES</div>
        ${charText('pc-abilities','ABILITIES & SPELLS — ONE PER LINE','Shadow manipulation\nRaise undead\nGravitational Grasp',4,abilities)}
      </div>
      <details class="optional-stats"><summary>Optional tabletop statistics (D&D-style)</summary>
        <div class="form-grid">${charField('pc-level','LEVEL','e.g. 4',read('level'))}${charField('pc-max_hp','HIT POINTS','e.g. 30',read('max_hp'))}</div>
        <div class="form-grid">${charField('pc-armor_class','ARMOUR CLASS','e.g. 15',read('armor_class'))}${charField('pc-move_speed','MOVEMENT SPEED','e.g. 30 ft',read('move_speed'))}</div>
        <div class="form-grid">${charField('pc-strength','STRENGTH','',read('strength'))}${charField('pc-dexterity','DEXTERITY','',read('dexterity'))}</div>
        <div class="form-grid">${charField('pc-constitution','CONSTITUTION','',read('constitution'))}${charField('pc-intelligence','INTELLIGENCE','',read('intelligence'))}</div>
        <div class="form-grid">${charField('pc-wisdom','WISDOM','',read('wisdom'))}${charField('pc-charisma','CHARISMA','',read('charisma'))}</div>
        ${charText('pc-skills','SKILLS / PROFICIENCIES','Optional skills and proficiencies',2,read('skills'))}
        ${charText('pc-starting_items','STARTING ITEMS — ONE PER LINE','Optional equipment and possessions',3,read('starting_items'))}
      </details>
      <button class="button primary full" type="submit">${t}</button>
    </form><p class="muted note">Your abilities inform the narrator but never limit what you can attempt. Your appearance, personality and mannerisms stay part of your character's identity.</p>`;
}
function readCharacterForm(){
  return {pc_name:$('pc-name').value,
    ...Object.fromEntries(['pronouns','species','role','alignment','aliases','appearance','personality','mannerisms','background','motivation','weaknesses','faction','starting_location','abilities','level','max_hp','armor_class','move_speed','strength','dexterity','constitution','intelligence','wisdom','charisma','skills','starting_items'].map(key=>[key,$('pc-'+key).value])),
    description:$('pc-appearance').value};
}
async function showCharacterModal(worldId) {
  try {
    const {world}=await request('/api/worlds/'+encodeURIComponent(worldId));
    showModal('CREATE YOUR CHARACTER', `Enter ${world.title}`, characterForm(world));
    $('character-form').onsubmit=async e=>{
      e.preventDefault(); const btn=e.target.querySelector('button[type=submit]');btn.disabled=true;
      try {
        const payload={world_id:worldId,title:$('campaign-title').value,...readCharacterForm()};
        const {campaign}=await request('/api/campaigns',{method:'POST',body:payload});
        closeModal();await openCampaign(campaign.id);toast('Adventure created. Begin when you are ready.');
      }catch(err){toast(err.message,true)}finally{btn.disabled=false;}
    };
  }catch(err){toast(err.message,true)}
}
function showEditCharacterModal() {
  const c=state.active;if(!c||!state.world)return;
  showModal('EDIT YOUR CHARACTER',c.pc_name,characterForm(state.world,c));
  $('character-form').onsubmit=async e=>{
    e.preventDefault();const btn=e.target.querySelector('button[type=submit]');btn.disabled=true;
    try {
      const {campaign}=await request('/api/campaigns/'+c.id+'/character',{method:'PATCH',body:readCharacterForm()});
      state.active=campaign;closeModal();renderCharacter(campaign);toast('Character saved. Existing adventure preserved.');
    }catch(err){toast(err.message,true)}finally{btn.disabled=false;}
  };
}
function renderCharacter(campaign) {
  const pc=campaign.pc_profile||{};
  $('char-name').textContent=campaign.pc_name;
  $('char-role-line').textContent=[pc.species,pc.role,pc.level?`Level ${pc.level}`:''].filter(Boolean).join(' · ');
  const hp=String(pc.max_hp||'').trim();
  const resources = [];
  if(hp) resources.push(`<div class="resource"><span>HIT POINTS</span><strong>${escapeHtml(hp)}</strong><div class="resource-meter"><i></i></div><small>Character sheet maximum; live HP tracking not implemented</small></div>`);
  if(pc.armor_class) resources.push(`<div class="resource"><span>ARMOUR</span><strong>${escapeHtml(pc.armor_class)}</strong></div>`);
  $('char-resources').innerHTML=resources.join('');
  $('char-description').textContent=pc.appearance||pc.description||pc.background||'Your story is yours to write.';
  const props=[['RACE',pc.species],['ROLE',pc.role],['PRONOUNS',pc.pronouns],['PERSONALITY',pc.personality],['MANNERISMS',pc.mannerisms],['MOTIVATION',pc.motivation]];
  $('char-traits').innerHTML=props.filter(x=>x[1]).map(([key,val])=>`<div><span class="detail-label">${key}</span><p>${escapeHtml(val)}</p></div>`).join('');
  $('char-abilities').innerHTML=(pc.abilities||[]).map(a=>`<span class="ability-pill">${escapeHtml(a)}</span>`).join('')||'<span class="muted">No abilities listed — improvise freely.</span>';
}
async function openCampaign(campaignId) {
  try {
    const [{campaign}, {messages}] = await Promise.all([request('/api/campaigns/'+campaignId),request('/api/campaigns/'+campaignId+'/messages')]);
    state.active=campaign; state.messages=messages; state.world=(await request('/api/worlds/'+campaign.world_id)).world;
    $('library').classList.add('hidden'); $('adventure').classList.remove('hidden'); $('nav-worlds').classList.remove('active'); $('nav-story').classList.add('active'); $('campaign-links').classList.add('hidden');
    $('breadcrumb').textContent=`${state.world.title} / ${campaign.title}`;
    $('story-world').textContent=state.world.title; $('story-title').textContent=campaign.title;
    renderCharacter(campaign); renderWorldDetails(state.world);
    renderMessages(); updateState(campaign.state); setDetailTab('scene'); await refreshLibrary();
  }catch(err){toast(err.message,true)}
}
function renderMessages() {
  const feed=$('story-feed');
  if(!state.messages.length){
    feed.innerHTML=`<div class="intro-scene"><div class="ornament">✧</div><h2>The story is not yet written.</h2><p>Your character stands at the edge of a new adventure. Let the Game Master set the scene.</p><button id="start-story" class="button primary">Begin the story →</button></div>`;
    state.lastNarration='';$('start-story').onclick=()=>sendAction('__START__');
  } else {
    feed.innerHTML=state.messages.map(m=>m.role==='gm'
      ? `<div class="gm-message"><div class="message-label"><span class="gold-dot">✦</span> GAME MASTER</div><div class="narrative">${escapeHtml(m.content).replace(/\n/g,'<br>')}</div><button class="speak-one" data-message="${m.id}" title="Read message aloud">▶ Listen</button></div>`
      : `<div class="player-message"><div class="message-label">YOUR ACTION</div><p>${escapeHtml(m.content).replace(/\n/g,'<br>')}</p></div>`).join('');
    document.querySelectorAll('.speak-one').forEach(b=>b.onclick=()=>{
      const m=state.messages.find(x=>String(x.id)===b.dataset.message); if(m) speak(m.content);
    });
    const last=state.messages.filter(m=>m.role==='gm').at(-1);state.lastNarration=last?.content||'';
  }
  feed.scrollTop=feed.scrollHeight;
  window.requestAnimationFrame(()=>feed.scrollTop=feed.scrollHeight);
}
function updateState(s) {
  $('current-location').textContent=s.location||'Unknown';
  $('scene-title').textContent=s.location||'Uncharted territory';
  $('scene-characters').innerHTML=state.active ? `<div class="scene-person"><span class="person-avatar">✦</span><div><strong>${escapeHtml(state.active.pc_name)}</strong><small>Your character</small></div></div><p class="muted note">Other characters will appear as the world develops. An automatic NPC presence tracker is planned.</p>` : '<p class="muted">No active character</p>';
  $('inventory').innerHTML=(s.inventory||[]).slice(-30).map(v=>`<li>${escapeHtml(v)}</li>`).join('')||'<li class="muted">Empty</li>';
  $('journal').innerHTML=(s.journal||[]).slice(-7).reverse().map(v=>`<li>${escapeHtml(v)}</li>`).join('')||'<li class="muted">The adventure has just begun</li>';
}
function renderWorldDetails(world) {
  $('world-detail-title').textContent=world.title;
  $('world-detail-description').textContent=world.description||'The world awaits discovery.';
  $('world-detail-author').textContent=world.author||'Unknown creator';
  $('world-lore-entries').innerHTML=(world.sections||[]).slice(0,60).map((entry,i)=>`<details class="lore-entry"><summary><span>${escapeHtml(entry.title||'World entry')}</span><small>${escapeHtml(entry.kind||'lore')}</small></summary><p>${escapeHtml((entry.content||'').slice(0,1800))}</p></details>`).join('')||'<p class="muted">No lore entries available</p>';
}
function revealDetailsOnMobile(){
  if(window.matchMedia('(max-width: 700px)').matches) document.querySelector('.details').classList.add('show-on-mobile');
}
function setDetailTab(tab) {
  if(!['scene','character','world'].includes(tab))return;
  state.detailTab=tab;
  for(const name of ['scene','character','world']) {
    const selected=name===tab;
    $('tab-'+name).classList.toggle('hidden',!selected);
    const button=$('select-'+name);
    button.classList.toggle('active',selected);
    button.setAttribute('aria-selected',selected?'true':'false');
    button.tabIndex=selected?0:-1;
  }
  $('details-panel')?.scrollTo?.({top:0,behavior:'smooth'});
}
function showAbilities(){
  if(!state.active){toast('Open an adventure to view abilities',true);return;}
  setDetailTab('character');revealDetailsOnMobile();
  $('char-abilities').scrollIntoView({block:'nearest',behavior:'smooth'});
}
function openAdventureOrNotice(){
  if(state.active)return;
  if(state.campaigns.length)openCampaign(state.campaigns[0].id);
  else toast('Start an adventure from the Worlds library first.');
}
async function sendAction(value) {
  if(state.busy || !state.active)return;
  const action=value||$('action').value.trim();if(!action)return;
  state.busy=true;$('send-action').disabled=true;$('send-action').textContent='Narrating...';
  const actionBox=$('action');const oldText=actionBox.value;
  if(action!=='__START__') actionBox.value='';
  let pending=null;
  try {
    pending=document.createElement('div'); pending.className='thinking';pending.textContent='✧ The Game Master is weaving the next scene…'; $('story-feed').appendChild(pending);pending.scrollIntoView({block:'end',behavior:'smooth'});
    const result=await request(`/api/campaigns/${state.active.id}/turn`,{method:'POST',body:{action,model:$('model').value.trim()||'qwen3:8b'}});
    state.messages=result.messages;state.active.state=result.state;renderMessages();updateState(result.state);
    if($('autoplay').checked) speak(result.narration);
  }catch(err){if(action!=='__START__')actionBox.value=oldText;toast(err.message,true)}finally{
    pending?.remove();state.busy=false;$('send-action').disabled=false;$('send-action').textContent='Send action →';
    await refreshLibrary().catch(()=>{});
  }
}
const neuralVoices = [
  ['bm_george','George · British male'],['bm_lewis','Lewis · British male'],
  ['bf_emma','Emma · British female'],['bf_isabella','Isabella · British female'],
  ['am_michael','Michael · American male'],['am_adam','Adam · American male'],
  ['af_heart','Heart · American female'],['af_bella','Bella · American female']
];
let speechSequence=0;
let activeAudio=null;
let activeUrl=null;
let activeController=null;
let cancelAudioWait=null;
function settingsGet(key, fallback) { try {return localStorage.getItem('sf_'+key)??fallback;}catch{return fallback;} }
function settingsPut(key, val) { try{localStorage.setItem('sf_'+key,String(val))}catch{} }
function availableVoices(){return ('speechSynthesis' in window)?speechSynthesis.getVoices():[];}
function populateVoices(){
  const engine=$('voice-engine').value;
  const saved=settingsGet('voice_'+engine,'');
  const options=engine==='kokoro'
     ? neuralVoices.map(([id,label])=>[id,label])
     : availableVoices().map((v,i)=>[String(i),v.name+' · '+v.lang]);
  $('voices').innerHTML=options.map(([id,label])=>`<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`).join('')||'<option value="">System default</option>';
  if(options.some(([id])=>id===saved)) $('voices').value=saved;
  else if(engine==='browser') {
    const i=availableVoices().findIndex(v=>v.lang==='en-GB');if(i>=0)$('voices').value=String(i);
  }
}
function narrationStatus(text){$('narration-status').textContent=text;}
function updatePlaybackButtons(){
  $('pause-voice').textContent=state.speechPaused?'▶ Resume':'⏸ Pause';
  $('pause-voice').disabled=!state.speaking;
  $('stop-voice-top').disabled=!state.speaking;
  $('stop-voice').disabled=!state.speaking;
}
function clearAudio(){
  if(cancelAudioWait){const cancel=cancelAudioWait;cancelAudioWait=null;cancel();}
  if(activeController){activeController.abort();activeController=null;}
  if(activeAudio){activeAudio.pause();activeAudio.removeAttribute('src');activeAudio.load();activeAudio=null;}
  if(activeUrl){URL.revokeObjectURL(activeUrl);activeUrl=null;}
}
function stopSpeech(){
  speechSequence++;clearAudio();
  if('speechSynthesis' in window) speechSynthesis.cancel();
  state.speechPaused=false;state.speaking=false;
  narrationStatus('Narration stopped');updatePlaybackButtons();
}
function toggleSpeechPause(){
  if(!state.speaking)return;
  state.speechPaused=!state.speechPaused;
  if($('voice-engine').value==='kokoro') {
    if(activeAudio) {
      if(state.speechPaused)activeAudio.pause();
      else activeAudio.play().catch(e=>toast('Audio cannot resume: '+e.message,true));
    }
  }else if('speechSynthesis' in window) {
    if(state.speechPaused)speechSynthesis.pause();else speechSynthesis.resume();
  }
  narrationStatus(state.speechPaused?'Narration paused':'Reading aloud');updatePlaybackButtons();
}
function speechChunks(text, limit=180){
  const parts=String(text).match(/[^.!?\n]+[.!?\n]*/g)||[String(text)];
  const chunks=[];let pending='';
  for(const part of parts){
    if((pending+part).length>limit&&pending){chunks.push(pending.trim());pending='';}
    if(part.length>limit){
      for(const word of part.split(/(\s+)/)) {
        if((pending+word).length>limit&&pending){chunks.push(pending.trim());pending='';}
        if(word.length>limit){
          for(let pos=0;pos<word.length;pos+=limit){
            const segment=word.slice(pos,pos+limit);
            if((pending+segment).length>limit&&pending){chunks.push(pending.trim());pending='';}
            pending+=segment;
          }
        }else pending+=word;
      }
    }else pending+=part;
  }
  if(pending.trim())chunks.push(pending.trim());
  return chunks.filter(Boolean);
}
function speechDone(seq){
  if(seq!==speechSequence)return;
  state.speaking=false;state.speechPaused=false;
  narrationStatus('Narration finished');updatePlaybackButtons();
}
function playBrowserSpeech(text,seq){
  if(!('speechSynthesis' in window)){stopSpeech();toast('Speech is unavailable in this browser',true);return;}
  const voiceIndex=Number($('voices').value),voices=availableVoices();
  const chunks=speechChunks(text,180);let index=0;
  function next(){
    if(seq!==speechSequence)return;
    if(index>=chunks.length){speechDone(seq);return;}
    const utterance=new SpeechSynthesisUtterance(chunks[index++]);
    if(Number.isInteger(voiceIndex)&&voices[voiceIndex])utterance.voice=voices[voiceIndex];
    utterance.rate=Number($('speed').value);utterance.pitch=0.93;
    utterance.volume=Number($('volume').value)/100;
    utterance.lang=utterance.voice?.lang||'en-GB';
    utterance.onend=()=>{if(seq===speechSequence)next()};
    utterance.onerror=e=>{if(seq===speechSequence){speechDone(seq);if(e.error!=='interrupted')toast('Browser speech stopped: '+e.error,true);}};
    speechSynthesis.speak(utterance);
    if(state.speechPaused)speechSynthesis.pause();
  }
  next();
}
async function playNeuralSpeech(text,seq){
  try{
    const chunks=speechChunks(text,950);
    for(const chunk of chunks){
      if(seq!==speechSequence)return;
      narrationStatus(state.speechPaused?'Narration paused':'Preparing natural voice…');
      const controller=new AbortController();activeController=controller;
      const response=await fetch('/api/tts/speech',{
        method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({text:chunk,voice:$('voices').value||'bm_george',speed:Number($('speed').value)})
      });
      if(seq!==speechSequence)return;
      if(!response.ok){let detail;try{detail=(await response.json()).error}catch{}throw new Error(detail||'Neural voice request failed');}
      const blob=await response.blob();
      if(seq!==speechSequence)return;
      activeController=null;
      const url=URL.createObjectURL(blob);activeUrl=url;
      const audio=new Audio(url);activeAudio=audio;audio.volume=Number($('volume').value)/100;
      await new Promise((resolve,reject)=>{
        cancelAudioWait=resolve;
        audio.onended=()=>{cancelAudioWait=null;resolve();};
        audio.onerror=()=>{cancelAudioWait=null;reject(new Error('Could not play generated narration audio'));};
        if(state.speechPaused)return;
        audio.play().then(()=>narrationStatus('Reading aloud')).catch(reject);
      // User can resume after initial pause; pause button changes state and plays audio.
      });
      cancelAudioWait=null;
      if(activeAudio===audio){audio.pause();audio.removeAttribute('src');audio.load();activeAudio=null;}
      if(activeUrl===url){URL.revokeObjectURL(url);activeUrl=null;}
    }
    speechDone(seq);
  }catch(err){
    if(seq!==speechSequence||err.name==='AbortError')return;
    stopSpeech();toast(err.message,true);
  }
}
function speak(text){
  if(!String(text||'').trim())return;
  stopSpeech();const seq=speechSequence;
  state.speaking=true;state.speechPaused=false;
  narrationStatus('Preparing narration…');updatePlaybackButtons();
  if($('voice-engine').value==='kokoro')playNeuralSpeech(text,seq);
  else playBrowserSpeech(text,seq);
}
async function checkNeural(){
  try{
    const data=await request('/api/tts/status');state.neuralAvailable=!!data.available;
    $('neural-status').textContent=data.available?'Kokoro neural voice server connected.':'Kokoro is not running yet — see README for setup.';
    if(settingsGet('engine','')===''){
      $('voice-engine').value=data.available?'kokoro':'browser';populateVoices();
    }
  }catch{$('neural-status').textContent='Unable to check Kokoro service.';}
}
// This updater never asks the browser to unpack or overwrite program files.
// The user chooses a trusted release ZIP and must explicitly approve installation.
function openUpdatesModal(){
  showModal('APPLICATION UPDATES', 'Update Storyforge', `
    <p class="muted modal-intro">Future verified GitHub releases can install automatically when Storyforge isn't being used. Saved campaigns are backed up before each installation.</p>
    <div class="world-preview"><strong>Installed:</strong> <span id="update-installed">Checking...</span><p class="muted note" id="update-prev-result"></p></div>
    <label class="toggle-line"><input type="checkbox" id="auto-updates" checked> Automatically install trusted updates when idle</label>
    <p class="muted note" id="update-channel">Checking GitHub release channel…</p>
    <button class="button secondary full" id="check-releases">Check GitHub for updates</button>
    <hr class="section-break">
    <p class="muted note">You can also install a trusted release ZIP manually, as in v0.3.0.</p>
    <label class="field"><span>NEW STORYFORGE RELEASE (.ZIP)</span><input id="update-file" type="file" accept=".zip,application/zip"></label>
    <p class="muted note">Only select an update ZIP you trust. Storyforge validates the release manifest and contents before installing. These checks do not prove who published the ZIP.</p>
    <button class="button secondary full" id="inspect-update">Verify selected update</button>
    <div class="hidden" id="update-confirmation"><p class="world-preview" id="update-summary"></p>
      <button class="button primary full" id="install-update">Install update & restart Storyforge</button></div>
    <p class="muted note" id="update-result" aria-live="polite"></p>`);
  let stagedToken=null;
  request('/api/updates').then(data=>{
    $('update-installed').textContent='Storyforge v'+data.version;
    const st=data.status||{};
    if(st.phase==='completed') $('update-prev-result').textContent='Last update installed successfully.';
    else if(st.phase==='rolled_back'||st.phase==='failed') $('update-prev-result').textContent='Previous update did not complete: '+(st.error||'See data/updates/updater.log');
    const ch=data.channel||{};updateIndicator(data);
    $('auto-updates').checked=!!ch.enabled;
    const msg=ch.phase==='queued'?`Release v${ch.latest} waiting until you're not playing.`:
      ch.phase==='downloading'?'Downloading and verifying the release…':
      ch.phase==='installing'?'Installing update and restarting…':
      ch.phase==='current'?"You're on the latest published release.":
      ch.error?ch.error:'No release check completed yet.';
    $('update-channel').textContent=`GitHub: ${ch.repository||'Not configured'} · ${msg}`;
  }).catch(e=>{ $('update-installed').textContent='Unavailable: '+e.message; });
  $('auto-updates').onchange=async()=>{
    try{
      const data=await request('/api/updates/auto',{method:'POST',body:{enabled:$('auto-updates').checked}});
      toast(data.enabled?'Automatic idle-time updates enabled':'Automatic updates disabled');
    }catch(e){$('auto-updates').checked=!$('auto-updates').checked;toast(e.message,true);}
  };
  $('check-releases').onclick=async()=>{
    $('check-releases').disabled=true;
    try{await request('/api/updates/check',{method:'POST',body:{}});
      $('update-channel').textContent='Checking the Storyforge GitHub release channel in the background…';
      toast('Release check started');setTimeout(refreshUpdateIndicator,2500);
    }catch(e){toast(e.message,true)}
    finally{$('check-releases').disabled=false;}
  };
  $('update-file').onchange=()=>{$('update-confirmation').classList.add('hidden');stagedToken=null;};
  $('inspect-update').onclick=async()=>{
    const file=$('update-file').files[0];
    if(!file){toast('Choose a Storyforge update ZIP',true);return;}
    if(file.size>30*1024*1024){toast('Update ZIP must be under 30 MB',true);return;}
    $('inspect-update').disabled=true; $('update-result').textContent='Checking package and file hashes…';
    $('update-confirmation').classList.add('hidden');
    try{
      const detail=await request('/api/updates/inspect',{method:'POST',body:await file.arrayBuffer(),raw:true});
      stagedToken=detail.token;
      $('update-summary').textContent=`Verified release v${detail.version} · ${detail.file_count} application files · saved stories will not be overwritten.`;
      $('update-confirmation').classList.remove('hidden');
      $('update-result').textContent='Ready to install. Approve below when you are ready.';
    }catch(e){stagedToken=null;$('update-result').textContent=e.message;toast(e.message,true);}
    finally{$('inspect-update').disabled=false;}
  };
  $('install-update').onclick=async()=>{
    if(!stagedToken)return;
    $('install-update').disabled=true;
    $('inspect-update').disabled=true;
    $('update-result').textContent='Backing up your database, then restarting Storyforge…';
    try{
      const target=$('update-summary').textContent.match(/v(\d+\.\d+\.\d+)/)?.[1];
      await request('/api/updates/install',{method:'POST',body:{token:stagedToken,confirm:'INSTALL'}});
      $('update-file').disabled=true;
      $('update-result').textContent='Installing… The server may be unreachable for a short time.';
      for(let attempt=0;attempt<110;attempt++){
        await new Promise(resolve=>setTimeout(resolve,1000));
        try{
          const data=await request('/api/updates');
          if(data.status?.phase==='rolled_back'||data.status?.phase==='failed'){
            throw new Error('Update failed and was rolled back: '+(data.status.error||'Check updater.log'));
          }
          if(data.version===target && data.status?.phase==='completed'){
            $('update-result').textContent='Update successful! Reloading…';
            location.reload();return;
          }
        }catch(e){if(e.message.startsWith('Update failed'))throw e;}
      }
      throw new Error('Update is still unavailable. Check data/updates/updater.log or restart Storyforge.');
    }catch(e){$('update-result').textContent=e.message;toast(e.message,true);$('install-update').disabled=false;}
  };
}
// Keep release status visible in the top bar without opening Settings.
// A queued release is available even if unattended installation is waiting for idle time.
function updateIndicator(data) {
  const version=String(data?.version||'0.5.0');
  $('app-version').textContent='v'+version;
  const channel=data?.channel||{};
  const available=!!(channel.latest && ['queued','downloading','installing'].includes(channel.phase) &&
    versionCompare(channel.latest,version)>0);
  const button=$('open-updates');
  button.classList.toggle('has-update',available);
  $('update-dot').classList.toggle('hidden',!available);
  $('update-label').textContent=available?'Update available':'Updates';
  if(available)button.title=`Storyforge v${channel.latest} available · ${channel.phase}`;
  else button.title='Storyforge updates · '+(channel.phase||'not checked');
  return available;
}
function versionCompare(a,b) {
  const parse=v=>/^\d+\.\d+\.\d+$/.test(String(v))?v.split('.').map(Number):null;
  const x=parse(a),y=parse(b);if(!x||!y)return 0;
  for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]>y[i]?1:-1;
  return 0;
}
async function refreshUpdateIndicator(){
  try{const data=await request('/api/updates');updateIndicator(data)}
  catch{/* Retain last known update state during a restart/offline period. */}
}
refreshUpdateIndicator();
setInterval(refreshUpdateIndicator,60000);
$('open-updates').onclick=openUpdatesModal;
$('new-world-sidebar').onclick=showImportModal;
$('import-world').onclick=showImportModal;
$('nav-worlds').onclick=toLibrary;
$('brand-home').onclick=toLibrary;
$('nav-story').onclick=openAdventureOrNotice;
$('nav-adventures').onclick=()=>{$('campaign-links').classList.toggle('hidden');};
$('nav-character').onclick=()=>{if(!state.active) return openAdventureOrNotice();setDetailTab('character');revealDetailsOnMobile();};
$('nav-world-lore').onclick=()=>{if(!state.active)return toLibrary();setDetailTab('world');revealDetailsOnMobile();};
$('nav-journal').onclick=()=>{if(!state.active)return openAdventureOrNotice();setDetailTab('scene');revealDetailsOnMobile();$('journal-card').scrollIntoView({block:'nearest',behavior:'smooth'});};
$('nav-settings').onclick=()=>{if(!state.active)return toast('Open an adventure to configure its narrator.');revealDetailsOnMobile();$('voice-settings').open=true;$('voice-settings').scrollIntoView({block:'nearest',behavior:'smooth'});};
$('composer-abilities').onclick=showAbilities;
$('show-details-mobile').onclick=()=>document.querySelector('.details').classList.toggle('show-on-mobile');
for(const name of ['scene','character','world']) $('select-'+name).onclick=()=>setDetailTab(name);
// Close the rail's campaign picker when clicking elsewhere.
document.addEventListener('click',e=>{if(!e.target.closest('#nav-adventures')&&!e.target.closest('#campaign-links'))$('campaign-links').classList.add('hidden');});
$('back-library').onclick=toLibrary;
$('new-demo').onclick=async()=>{try{const w=state.worlds.find(w=>w.title.includes('(Demo)'));if(w)showCharacterModal(w.id);else toast('Sample world not found',true)}catch(e){toast(e.message,true)}};
$('close-modal').onclick=closeModal;
$('modal').onclick=e=>{if(e.target===$('modal'))closeModal()};
$('send-action').onclick=()=>sendAction();
$('action').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendAction()}});
$('replay').onclick=()=>{if(state.lastNarration)speak(state.lastNarration)};
$('edit-character').onclick=showEditCharacterModal;
$('pause-voice').onclick=toggleSpeechPause;
$('stop-voice-top').onclick=stopSpeech;
$('stop-voice').onclick=stopSpeech;
$('speed').oninput=()=>{$('speed-value').textContent=Number($('speed').value).toFixed(2)+'×';settingsPut('speed',$('speed').value)};
$('volume').oninput=()=>{
  const level=Number($('volume').value)/100;$('volume-value').textContent=Math.round(level*100)+'%';
  if(activeAudio)activeAudio.volume=level;
  if('speechSynthesis' in window && state.speaking && $('voice-engine').value==='browser'){
    // Browser Web Speech can't change volume mid-utterance; apply to the next chunk.
  }
  settingsPut('volume',$('volume').value);
};
$('voice-engine').onchange=()=>{stopSpeech();settingsPut('engine',$('voice-engine').value);populateVoices();};
$('voices').onchange=()=>{settingsPut('voice_'+$('voice-engine').value,$('voices').value)};
$('speed').value=settingsGet('speed','1');$('speed').oninput();
$('volume').value=settingsGet('volume','85');$('volume').oninput();
$('voice-engine').value=settingsGet('engine','browser');
updatePlaybackButtons();checkNeural();
if('speechSynthesis' in window) speechSynthesis.onvoiceschanged=populateVoices;
populateVoices();
request('/api/models').then(result=>{
  const models=result.models||[];
  $('installed-models').innerHTML=models.map(name=>`<option value="${escapeHtml(name)}"></option>`).join('');
  if(models.length && !models.includes($('model').value)) {
    $('model').value=models.find(name=>name.includes('qwen3.5'))||models.find(name=>name.includes('qwen'))||models[0];
  }
  if(!models.length) toast('No local Ollama models detected. Start Ollama and install a model before playing.',true);
}).catch(()=>{});
refreshLibrary().catch(e=>toast(e.message,true));

// Keep an open, visible campaign safe from unattended application restarts.
function storyforgeActivity(){if(document.visibilityState==='visible')fetch('/api/updates/activity',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).catch(()=>{});}
setInterval(storyforgeActivity,30000); storyforgeActivity();
