'use strict';
const $ = id => document.getElementById(id);
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { worlds: [], campaigns: [], characters: [], active: null, world: null, messages: [], busy: false, lastNarration: '', neuralAvailable: false, speechPaused: false, speaking: false, detailTab: 'scene', portraitRev: 0, sceneLocation: '', sceneRecord: null, artStatus: null, codexTab: 'sheet' };

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
  const [a,b,c] = await Promise.all([request('/api/worlds'), request('/api/campaigns'), request('/api/characters')]);
  state.worlds = a.worlds; state.campaigns = b.campaigns; state.characters=c.characters;
  $('home-character-count').textContent=state.characters.length+' reusable characters · '+state.worlds.length+' worlds';
  $('recent-count').textContent=state.campaigns.length+' adventures';
  $('library-count').textContent = state.worlds.length + ' worlds';
  $('worlds').innerHTML = state.worlds.map((w,i) => `<article class="world-card" data-world="${escapeHtml(w.id)}"><div class="card-art art-${i%5}"><span>✦</span></div><div class="world-card-body"><div class="eyebrow">${escapeHtml(w.section_count)} LORE ENTRIES</div><h3>${escapeHtml(w.title)}</h3><p>${escapeHtml(w.description || 'A world waiting for its story to begin.')}</p><div class="byline">Created by ${escapeHtml(w.author)}</div><button class="button secondary start-world" data-world="${escapeHtml(w.id)}">Start adventure →</button><button class="button ghost small research-world" data-world="${escapeHtml(w.id)}">◈ Discover lore</button></div></article>`).join('');
  $('campaign-links').innerHTML = `<div class="rail-popup-title">SAVED ADVENTURES</div>` + (state.campaigns.map(c => `<button class="nav campaign-link ${state.active?.id===c.id?'active':''}" data-campaign="${escapeHtml(c.id)}"><span>✧</span><span class="truncate">${escapeHtml(c.title)}</span></button>`).join('') || '<div class="empty-side">No adventures yet</div>');
  $('campaign-cards').innerHTML = state.campaigns.slice(0,8).map((c,i) => `<article class="recent-campaign-card"><div class="recent-campaign-cover art-${i%5}" data-cover="${escapeHtml(c.id)}"><img class="recent-cover-image hidden" alt="Scene from ${escapeHtml(c.title)}"><span class="recent-card-badge">✦ FANTASY</span><span class="recent-card-character">${escapeHtml(c.pc_name)}</span></div><div class="recent-campaign-info"><h3>${escapeHtml(c.title)}</h3><p class="muted">Last played ${escapeHtml(new Date(c.updated_at).toLocaleDateString())}</p><button class="button secondary reopen-campaign" data-campaign="${escapeHtml(c.id)}">▷ Continue</button></div></article>`).join('') || '<div class="home-empty">No campaigns yet. Choose a world below and begin your first story.</div>';
  for(const c of state.campaigns.slice(0,8)) {
    request('/api/artwork/scene?campaign_id='+encodeURIComponent(c.id)).then(data=>{
      if(!data.scene?.url)return;
      const cover=[...document.querySelectorAll('[data-cover]')].find(e=>e.dataset.cover===c.id);
      if(!cover)return;
      const img=cover.querySelector('img');img.src=data.scene.url;img.onload=()=>img.classList.remove('hidden');
    }).catch(()=>{});
  }
  document.querySelectorAll('.research-world').forEach(b=>b.addEventListener('click', e=>{e.stopPropagation();showLoreResearch(b.dataset.world)}));
  document.querySelectorAll('.start-world').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); showCharacterModal(b.dataset.world); }));
  document.querySelectorAll('.campaign-link, .reopen-campaign').forEach(b => b.addEventListener('click', () => openCampaign(b.dataset.campaign)));
}
function toLibrary(){
  $('adventure').classList.add('hidden'); $('library').classList.remove('hidden');
  document.querySelector('.app-shell').classList.add('home-view');
  $('nav-worlds').classList.add('active'); $('nav-story').classList.remove('active');
  $('campaign-links').classList.add('hidden');document.querySelector('.details').classList.remove('show-on-mobile');
  $('breadcrumb').textContent='Home / Your worlds';stopArtPolling();closeCodex();stopSpeech(); refreshLibrary().catch(e=>toast(e.message,true));
}
function showModal(eyebrow,title,content) {
  $('modal-eyebrow').textContent=eyebrow; $('modal-title').textContent=title;
  $('modal-content').innerHTML=content; $('modal').classList.remove('hidden');
}
function closeModal() { $('modal').classList.add('hidden'); }
const inp = (id,label,placeholder='',type='text',required=false) => `<label class="field"><span>${label}</span><input id="${id}" type="${type}" placeholder="${escapeHtml(placeholder)}" ${required?'required':''}></label>`;
function showImportModal() {
  showModal('A NEW STORY', 'Import a community world', `<p class="muted modal-intro">Bring in a world shared by its creator. We never scrape or automatically download content from Friends & Fables.</p><button type="button" class="button secondary full" id="research-during-create">◈ Discover universe lore online</button><div class="tab-switch"><button class="tab active" id="text-tab">Paste world lore</button><button class="tab" id="zip-tab">Import creator ZIP</button></div><form id="import-form">
    ${inp('world-title','WORLD NAME','e.g. The Shadow Kingdom','text',true)}
    ${inp('world-author','ORIGINAL CREATOR','Name or username')}
    ${inp('world-url','ORIGINAL WORLD LINK (ATTRIBUTION)','https://play.fables.gg/worlds/...','url')}
    <div id="import-text-fields"><label class="field"><span>WORLD OVERVIEW / LORE</span><textarea id="world-lore" rows="8" placeholder="Paste the world description, lore, characters and locations that the creator has shared..." required></textarea></label></div>
    <div id="import-zip-fields" class="hidden"><label class="field"><span>CREATOR-PROVIDED WORLD EXPORT (.ZIP)</span><input id="world-zip" type="file" accept=".zip,application/zip"></label><p class="muted note">Supports Markdown and JSON in CDF-style archives. Images and specialised game rules are not yet imported.</p></div>
    <button class="button primary full" type="submit">Import world →</button></form><p class="muted note">A public world link is stored as attribution, not used to fetch private or copyrighted data.</p>`);
  $('research-during-create').onclick=()=>showLoreResearch(null,$('world-title').value);
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
// Opt-in open-encyclopedia research; no Friends & Fables or fan-wiki scraping.
async function showLoreResearch(worldId=null,prefill='') {
  const current=worldId?state.worlds.find(w=>w.id===worldId):null;
  const universe=prefill||current?.title||state.world?.title||'';
  showModal('UNIVERSE RESEARCH','Discover & import world lore',`<p class="muted modal-intro">Search public Wikipedia summaries for places, characters, creatures and history. Review entries before importing. This is not a complete canon archive and won't copy Friends & Fables worlds.</p>
    <label class="field"><span>UNIVERSE / SERIES NAME</span><input id="lore-query" placeholder="Harry Potter / Wizarding World" value="${escapeHtml(universe)}"></label>
    <label class="field"><span>RELATED SERIES (OPTIONAL, COMMA-SEPARATED)</span><input id="lore-related" placeholder="Fantastic Beasts, Hogwarts"></label>
    ${worldId?`<p class="muted note">Add lore to: <strong>${escapeHtml(current?.title||'selected world')}</strong></p>`:'<label class="field"><span>NEW WORLD TITLE</span><input id="lore-world-title" placeholder="Wizarding World" value="${escapeHtml(universe)}"></label>'}
    <button class="button primary full" id="lore-search">Search public lore →</button>
    <div id="lore-search-results" aria-live="polite"></div><div class="note muted">Source: Wikipedia · CC BY-SA 4.0. Reference summaries may be incomplete or differ from a particular book or adaptation. Attribution is saved with each entry.</div>`);
  const results=$('lore-search-results');
  let entries=[];
  $('lore-search').onclick=async()=>{
    const query=$('lore-query').value.trim();
    if(!query)return toast('Enter the universe you want to research',true);
    const btn=$('lore-search');btn.disabled=true;btn.textContent='Searching...';
    results.innerHTML='<p class="muted">Searching the public encyclopedia…</p>';
    try{
      const data=await request('/api/lore/discover',{method:'POST',body:{query,related:$('lore-related').value}});
      entries=data.entries||[];
      results.innerHTML=entries.length?`<p class="muted note">${entries.length} reference articles found. Check the lore you want to keep, then import.</p><div class="lore-result-list">${entries.map((e,i)=>`<label class="lore-research-item"><input type="checkbox" class="lore-choose" value="${i}" checked><span><strong>${escapeHtml(e.title)}</strong><small>${escapeHtml(e.kind)} · <a href="${escapeHtml(e.url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">Source ↗</a></small><span>${escapeHtml(e.summary.slice(0,330))}${e.summary.length>330?'…':''}</span></span></label>`).join('')}</div><button class="button primary full" id="lore-import">${worldId?'Add selected lore to world':'Create world with selected lore'} →</button>`:'<p class="muted">No public lore found. Try the franchise name or add a related series.</p>';
      if(entries.length)$('lore-import').onclick=async()=>{
        const selected=[...document.querySelectorAll('.lore-choose:checked')].map(x=>entries[Number(x.value)]).filter(Boolean);
        if(!selected.length)return toast('Select at least one lore entry',true);
        const title=worldId?'':$('lore-world-title').value.trim();
        if(!worldId&&!title)return toast('Enter a world title',true);
        const submit=$('lore-import');submit.disabled=true;submit.textContent='Importing lore...';
        try{
          const data=await request('/api/lore/import',{method:'POST',body:{world_id:worldId,title,entries:selected}});
          closeModal();await refreshLibrary();
          if(state.world?.id===worldId){state.world=data.world;renderWorldDetails(data.world);if(!$('codex-overlay').classList.contains('hidden'))renderCodexWorld();}
          toast(`Imported ${data.world.added??selected.length} lore entries with attribution`);
        }catch(e){toast(e.message,true)}finally{submit.disabled=false;submit.textContent='Import selected lore →';}
      };
      if(data.warnings?.length)toast('Some research queries failed; available results are shown.',true);
    }catch(e){results.innerHTML='';toast(e.message,true)}finally{btn.disabled=false;btn.textContent='Search public lore →';}
  };
}
const charText = (id, label, hint='', rows=2, value='') => `<label class="field"><span>${label}</span><textarea id="${id}" rows="${rows}" placeholder="${escapeHtml(hint)}">${escapeHtml(value)}</textarea></label>`;
const charField = (id, label, hint='', value='') => `<label class="field"><span>${label}</span><input id="${id}" type="text" placeholder="${escapeHtml(hint)}" value="${escapeHtml(value)}"></label>`;
function characterForm(world, campaign=null, libraryOnly=false) {
  const pc=campaign?.pc_profile||{};
  const read=(key)=>pc[key]||'';
  const abilities=Array.isArray(pc.abilities)?pc.abilities.join('\n'):'';
  const t=campaign ? 'Save character changes' : libraryOnly ? 'Save to character library' : 'Create adventure →';
  return `<div class="world-preview">${escapeHtml(libraryOnly?'Create a reusable character for any world.':world.description)}</div>
    <form id="character-form">
      ${!campaign&&!libraryOnly?charField('campaign-title','ADVENTURE TITLE',`A Story in ${world.title}`):''}
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
      <div class="form-section"><div class="eyebrow">CHARACTER ARTWORK</div><label class="field"><span>UPLOAD A CHARACTER PORTRAIT (PNG, JPEG OR WEBP)</span><input id="pc-portrait-upload" type="file" accept="image/png,image/jpeg,image/webp"></label></div>
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
    await refreshLibrary();
    showModal('BEGIN A CAMPAIGN', `Enter ${world.title}`, `<p class="muted">Choose one of your saved characters, or make a new one.</p><label class="field"><span>ADVENTURE NAME</span><input id="chosen-campaign-title" placeholder="${escapeHtml('A Story in '+world.title)}"></label><div class="character-picker">${state.characters.map(c=>`<button class="character-pick" data-character="${escapeHtml(c.id)}"><img src="/api/characters/${encodeURIComponent(c.id)}/portrait" alt="" onerror="this.style.visibility='hidden'"><span><strong>${escapeHtml(c.name)}</strong><small>${escapeHtml([c.profile.species,c.profile.role].filter(Boolean).join(' · ')||'Your character')}</small></span><span>Play →</span></button>`).join('')||'<p class="muted">No saved characters yet.</p>'}</div><button class="button primary full" id="create-fresh-character">＋ Create a new character</button>`);
    document.querySelectorAll('[data-character]').forEach(btn=>btn.onclick=async()=>{
      btn.disabled=true;
      try {
        const {campaign}=await request('/api/campaigns',{method:'POST',body:{world_id:worldId,character_id:btn.dataset.character,title:$('chosen-campaign-title').value}});
        closeModal();await openCampaign(campaign.id);toast('Adventure ready with your saved character.');
      }catch(err){toast(err.message,true);btn.disabled=false;}
    });
    $('create-fresh-character').onclick=()=>showNewCampaignCharacterForm(world);
  }catch(err){toast(err.message,true)}
}
function showNewCampaignCharacterForm(world){
  showModal('CREATE YOUR CHARACTER', `Enter ${world.title}`, characterForm(world));
  $('character-form').onsubmit=async e=>{
    e.preventDefault();const btn=e.target.querySelector('button[type=submit]');btn.disabled=true;
    try {
      const payload={world_id:world.id,title:$('campaign-title').value,...readCharacterForm()};
      const {campaign}=await request('/api/campaigns',{method:'POST',body:payload});
      if($('pc-portrait-upload').files[0]) await uploadPortrait(campaign.id,$('pc-portrait-upload').files[0]);
      closeModal();await openCampaign(campaign.id);toast('Your character has also been saved to your library.');
    }catch(err){toast(err.message,true)}finally{btn.disabled=false}
  };
}
async function uploadLibraryPortrait(id,file){
  if(file.size>8*1024*1024||!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Choose a PNG, JPEG or WebP under 8 MB');
  const r=await fetch('/api/characters/'+encodeURIComponent(id)+'/portrait',{method:'POST',headers:{'Content-Type':file.type},body:file});
  if(!r.ok)throw Error((await r.json()).error||'Upload failed');
}
async function showCharacterLibrary(){
  try{await refreshLibrary();renderCharacterLibrary()}catch(e){toast(e.message,true)}
}
function renderCharacterLibrary(){
  $('codex-eyebrow').textContent='YOUR COLLECTION';$('codex-title').textContent='Character Library';
  $('codex-overlay').classList.remove('hidden');$('codex-overlay').setAttribute('aria-hidden','false');
  $('codex-body').innerHTML=`<div class="library-header"><p>Reusable characters for every adventure. Creating a campaign keeps its own story progress.</p><button class="button primary" id="library-create-character">＋ New character</button></div><div class="character-library-grid">${state.characters.map(c=>`<button class="library-character" data-library-id="${escapeHtml(c.id)}"><div class="library-portrait"><img src="/api/characters/${encodeURIComponent(c.id)}/portrait" alt="" onerror="this.style.display='none'"></div><h3>${escapeHtml(c.name)}</h3><p>${escapeHtml([c.profile.species,c.profile.role].filter(Boolean).join(' · '))}</p></button>`).join('')||'<p class="muted">Your library is empty. Create a character or start an adventure.</p>'}</div>`;
  $('library-create-character').onclick=()=>showLibraryCharacterForm();
  document.querySelectorAll('[data-library-id]').forEach(b=>b.onclick=()=>renderLibraryCharacterDetail(b.dataset.libraryId));
  $('codex-close').focus();
}
function showLibraryCharacterForm(existing=null){
  const mockWorld={title:'Your characters',description:'Build a character to reuse in any Storyforge world.'};
  const mockCampaign=existing?{pc_name:existing.name,pc_profile:existing.profile}:null;
  showModal('CHARACTER LIBRARY',existing?'Edit '+existing.name:'New reusable character',characterForm(mockWorld,mockCampaign,!existing));
  $('character-form').onsubmit=async e=>{
    e.preventDefault();const btn=e.target.querySelector('button[type=submit]');btn.disabled=true;
    try{
      const form=readCharacterForm();const r=existing?
        await request('/api/characters/'+encodeURIComponent(existing.id)+'/profile',{method:'PATCH',body:form}):
        await request('/api/characters',{method:'POST',body:form});
      const pic=$('pc-portrait-upload').files[0];if(pic)await uploadLibraryPortrait(r.character.id,pic);
      closeModal();await refreshLibrary();renderCharacterLibrary();toast('Reusable character saved.');
    }catch(err){toast(err.message,true)}finally{btn.disabled=false}
  };
}
function renderLibraryCharacterDetail(id){
  const c=state.characters.find(x=>x.id===id);if(!c)return;
  const pc=c.profile;
  $('codex-title').textContent=c.name;
  $('codex-body').innerHTML=`<div class="library-profile"><img src="/api/characters/${encodeURIComponent(c.id)}/portrait" alt="Portrait of ${escapeHtml(c.name)}" onerror="this.style.display='none'"><h2>${escapeHtml(c.name)}</h2><p>${escapeHtml([pc.level?'Level '+pc.level:'',pc.species,pc.role,pc.alignment].filter(Boolean).join(' · '))}</p><div class="library-profile-actions"><button class="button ghost" id="library-back">← All characters</button><button class="button primary" id="library-edit">✎ Edit character</button></div></div><div class="codex-grid">${codexSection('Appearance',paragraph(pc.appearance||pc.description))}${codexSection('Personality & mannerisms',paragraph([pc.personality,pc.mannerisms].filter(Boolean).join('\n\n')))}${codexSection('History',paragraph(pc.background))}${codexSection('Abilities & spells',spellLibraryMarkup(pc,c.id))}</div>`;
  $('library-back').onclick=renderCharacterLibrary;$('library-edit').onclick=()=>showLibraryCharacterForm(c);
  wireSpellButtons('characters', c.id, pc);
}
function showEditCharacterModal() {
  const c=state.active;if(!c||!state.world)return;
  showModal('EDIT YOUR CHARACTER',c.pc_name,characterForm(state.world,c));
  $('character-form').onsubmit=async e=>{
    e.preventDefault();const btn=e.target.querySelector('button[type=submit]');btn.disabled=true;
    try {
      const {campaign}=await request('/api/campaigns/'+c.id+'/character',{method:'PATCH',body:readCharacterForm()});
      if($('pc-portrait-upload').files[0]) await uploadPortrait(c.id,$('pc-portrait-upload').files[0]);
      state.active=campaign;closeModal();renderCharacter(campaign);toast('Character saved. Existing adventure preserved.');
    }catch(err){toast(err.message,true)}finally{btn.disabled=false;}
  };
}
function renderCharacter(campaign) {
  const pc=campaign.pc_profile||{};
  $('char-name').textContent=campaign.pc_name;
  renderPortraitThumb(campaign.id);
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
    state.sceneLocation='';stopArtPolling();closeCodex();state.active=campaign; state.messages=messages; state.world=(await request('/api/worlds/'+campaign.world_id)).world;
    document.querySelector('.app-shell').classList.remove('home-view');
    $('library').classList.add('hidden'); $('adventure').classList.remove('hidden'); $('nav-worlds').classList.remove('active'); $('nav-story').classList.add('active'); $('campaign-links').classList.add('hidden');
    $('breadcrumb').textContent=`${state.world.title} / ${campaign.title}`;
    $('story-world').textContent=state.world.title; $('story-title').textContent=campaign.title;
    renderCharacter(campaign); renderWorldDetails(state.world);
    renderMessages(); updateState(campaign.state); setDetailTab('scene'); await refreshLibrary();
  }catch(err){toast(err.message,true)}
}
function renderNarration(raw){
  // Escape HTML first. Then allow only simple bounded, paired emphasis spans.
  // The Game Master uses *italics* for written words and **bold** for shouting.
  let safe=escapeHtml(raw);
  safe=safe.replace(/\*\*([^*\n]{1,900})\*\*/g,'<strong>$1</strong>');
  safe=safe.replace(/(?<!\*)\*([^*\n]{1,900})\*(?!\*)/g,'<em>$1</em>');
  safe=safe.replace(/^(\[[^\]\n]{3,230}\])(?=\n|$)/, '<span class="scene-line">$1</span>');
  return safe.replace(/\n/g,'<br>');
}
function renderMessages() {
  const feed=$('story-feed');
  if(!state.messages.length){
    feed.innerHTML=`<div class="intro-scene"><div class="ornament">✧</div><h2>The story is not yet written.</h2><p>Your character stands at the edge of a new adventure. Let the Game Master set the scene.</p><button id="start-story" class="button primary">Begin the story →</button></div>`;
    state.lastNarration='';$('start-story').onclick=()=>sendAction('__START__');
  } else {
    feed.innerHTML=state.messages.map(m=>m.role==='gm'
      ? `<div class="gm-message" data-story-message="${m.id}"><div class="message-label"><span class="gold-dot">✦</span> GAME MASTER</div><div class="narrative">${renderNarration(m.content)}</div><div class="story-message-tools"><button class="speak-one" data-message="${m.id}" title="Read message aloud">▶ Listen</button><button class="message-command" data-message="${m.id}" data-operation="retry" aria-label="Retry GM message with feedback">↻ Retry / Feedback</button><button class="message-command danger" data-message="${m.id}" data-operation="delete" aria-label="Delete GM reply from this point">✕ Delete</button></div></div>`
      : `<div class="player-message" data-story-message="${m.id}"><div class="message-label">YOUR ACTION</div><p>${escapeHtml(m.content).replace(/\n/g,'<br>')}</p><div class="story-message-tools"><button class="message-command" data-message="${m.id}" data-operation="retry" aria-label="Resend this player action">↻ Resend / Feedback</button><button class="message-command danger" data-message="${m.id}" data-operation="delete" aria-label="Delete this action and following story">✕ Delete</button></div></div>`).join('');
    document.querySelectorAll('.speak-one').forEach(b=>b.onclick=()=>{
      const m=state.messages.find(x=>String(x.id)===b.dataset.message); if(m) speak(m.content);
    });
    document.querySelectorAll('.message-command').forEach(b=>b.onclick=()=>openStoryMessageAction(Number(b.dataset.message),b.dataset.operation));
    const last=state.messages.filter(m=>m.role==='gm').at(-1);state.lastNarration=last?.content||'';
  }
  feed.scrollTop=feed.scrollHeight;
  window.requestAnimationFrame(()=>feed.scrollTop=feed.scrollHeight);
}
function updateState(s) {
  $('current-location').textContent=s.location||'Unknown';
  if(ambient.playing&&$('ambient-mood').value==='auto')ambientStartMood();
  $('scene-title').textContent=s.location||'Uncharted territory';
  if(state.active && state.sceneLocation !== (s.location||'Unknown')) {
    state.sceneLocation=s.location||'Unknown';state.sceneRecord=null;$('adventure').classList.remove('has-scene-background');$('adventure').style.removeProperty('--story-scene-art');
    refreshSceneArtwork(true).catch(e=>toast(e.message,true));
  }
  $('scene-characters').innerHTML=state.active ? `<div class="scene-person"><span class="person-avatar">✦</span><div><strong>${escapeHtml(state.active.pc_name)}</strong><small>Your character</small></div></div><p class="muted note">Other characters will appear as the world develops. An automatic NPC presence tracker is planned.</p>` : '<p class="muted">No active character</p>';
  $('inventory').innerHTML=(s.inventory||[]).slice(-30).map(v=>`<li>${escapeHtml(v)}</li>`).join('')||'<li class="muted">Empty</li>';
  $('journal').innerHTML=(s.journal||[]).map((text,index)=>({text,index})).slice(-7).reverse().map(({text,index})=>`<li class="development-entry"><span>${escapeHtml(text)}</span><button type="button" class="remove-development" data-index="${index}" title="Remove inaccurate story development" aria-label="Remove this development">✕</button></li>`).join('')||'<li class="muted">The adventure has just begun</li>';
  wireJournalRemoval($('journal'));
}
function wireJournalRemoval(container){
  container.querySelectorAll('.remove-development').forEach(button=>{
    button.onclick=async()=>{
      if(!state.active||state.busy)return;
      const index=Number(button.dataset.index);
      const text=state.active.state?.journal?.[index];
      if(!Number.isInteger(index)||text===undefined)return;
      if(!window.confirm('Remove this Story Development? This only removes the journal note; it does not rewrite previous dialogue.'))return;
      button.disabled=true;
      try{
        const reply=await request('/api/campaigns/'+encodeURIComponent(state.active.id)+'/journal/remove',{
          method:'POST',body:{index,text}});
        state.active.state=reply.state;
        updateState(reply.state);
        if(!$('codex-overlay').classList.contains('hidden')&&$('nav-journal').classList.contains('active'))renderCodexJournal();
        toast('Story Development removed');
      }catch(error){toast(error.message,true);button.disabled=false;}
    };
  });
}
function renderWorldDetails(world) {
  $('world-detail-title').textContent=world.title;
  $('world-detail-description').textContent=world.description||'The world awaits discovery.';
  $('world-detail-author').textContent=world.author||'Unknown creator';
  if(!$('world-lore-research')){
    const button=document.createElement('button');button.id='world-lore-research';button.className='button secondary small';button.textContent='◈ Discover lore';
    $('world-detail-description').insertAdjacentElement('afterend',button);
  }
  $('world-lore-research').onclick=()=>showLoreResearch(world.id,world.title);
  if(!$('world-gm-context')){
    const button=document.createElement('button');button.id='world-gm-context';button.className='button secondary small';button.textContent='◎ What lore does the GM see?';
    $('world-lore-research').insertAdjacentElement('afterend',button);
  }
  $('world-gm-context').onclick=showGmLoreContext;
  $('world-lore-entries').innerHTML=(world.sections||[]).slice(0,60).map((entry,i)=>`<details class="lore-entry"><summary><span>${escapeHtml(entry.title||'World entry')}</span><small>${escapeHtml(entry.kind||'lore')}</small></summary><p>${escapeHtml((entry.content||'').slice(0,1800))}</p></details>`).join('')||'<p class="muted">No lore entries available</p>';
}
async function showGmLoreContext(){
  if(!state.active){toast('Open an adventure to inspect GM lore',true);return;}
  try{
    const data=await request('/api/campaigns/'+encodeURIComponent(state.active.id)+'/lore-context');
    const lore=data.lore;
    const entries=(lore.selected_entries||[]).map(e=>`<details class="lore-entry"><summary><span>${escapeHtml(e.title)}</span><small>${escapeHtml(e.kind)}</small></summary><p>${escapeHtml(e.content)}</p>${e.source?`<p class="muted">Source: ${escapeHtml(e.source)}</p>`:''}</details>`).join('');
    showModal('GAME MASTER CONTEXT','Lore supplied to the GM',
      `<p class="muted">${escapeHtml(lore.notice)}</p><h3>${escapeHtml(lore.world_title)}</h3><div class="detail-label">WORLD PREMISE — ALWAYS INCLUDED</div><p>${escapeHtml(lore.premise||'No world overview saved.')}</p><details class="lore-entry"><summary>Show full GM scenario guidance</summary><p>${escapeHtml(lore.scenario_guidance||'')}</p></details><div class="detail-label">SELECTED LORE: ${(lore.selected_entries||[]).length} OF ${Number(lore.total_saved_entries)||0} SAVED ENTRIES</div>${entries||'<p class="muted">No detailed lore entries are saved. Use Discover lore to add them.</p>'}`);
  }catch(e){toast(e.message,true);}
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
  if(state.active){openCampaign(state.active.id);return;}
  if(state.campaigns.length)openCampaign(state.campaigns[0].id);
  else toast('Start an adventure from the Worlds library first.');
}
function openStoryMessageAction(messageId, operation) {
  if(state.busy||!state.active){toast('Wait for the current Game Master reply first.',true);return;}
  const message=state.messages.find(m=>m.id===messageId);
  if(!message||!['retry','delete'].includes(operation))return;
  const later=state.messages.filter(m=>m.id>messageId).length;
  const isReply=message.role==='gm';
  const actionName=operation==='delete'?'Delete and rewind':isReply?'Retry Game Master':'Resend my action';
  const warn=later?`<p class="rewind-warning">This also removes ${later} later message${later===1?'':'s'} so the story remains consistent. This cannot be undone.</p>`:'';
  const legacy=isReply && !message.has_checkpoint;
  const legacyNotice=legacy?`<p class="rewind-warning">This reply predates state checkpoints. Storyforge can change its text and later messages, but cannot reliably reverse its older inventory, journal or location effects. The current state will be preserved.</p>`:'';
  showModal('STORY CORRECTIONS',actionName,`<p class="muted modal-intro">${operation==='delete'?'Remove this message and any dependent story that follows.':'Get another response to the same action without duplicating your original message.'}</p>
    <div class="correction-excerpt">${escapeHtml(message.content.slice(0,480))}${message.content.length>480?'…':''}</div>
    ${warn}${legacyNotice}
    <label class="field"><span>WHAT WENT WRONG? (OPTIONAL)</span><textarea id="story-correction-reason" rows="4" maxlength="750" placeholder="e.g. The GM spoke for Xeminas, ignored a spell limit, or contradicted established lore."></textarea></label>
    <p class="muted note">Your feedback is saved locally and used to guide future GM replies. It does not automatically retrain the AI model.</p>
    <div class="story-confirm-actions"><button class="button secondary" type="button" id="cancel-story-correction">Cancel</button><button class="button ${operation==='delete'?'secondary':'primary'}" type="button" id="confirm-story-correction">${escapeHtml(actionName)}</button></div>
    <div class="muted" id="story-correction-status" role="status"></div>`);
  $('cancel-story-correction').onclick=closeModal;
  $('story-correction-reason').focus();
  $('confirm-story-correction').onclick=async()=>{
    if(state.busy)return;
    const feedback=$('story-correction-reason').value.trim();const btn=$('confirm-story-correction');
    btn.disabled=true;state.busy=true;$('send-action').disabled=true;
    $('story-correction-status').textContent=operation==='delete'?'Rewinding story…':'Asking the Game Master to rewrite this turn…';
    try {
      const result=await request(`/api/campaigns/${state.active.id}/messages/${messageId}/${operation}`,{
        method:'POST',body:{feedback,model:$('model').value.trim()||'qwen3:8b',confirm:operation==='delete'?'REWIND':undefined}});
      stopSpeech();state.messages=result.messages;state.active.state=result.state;
      closeModal();renderMessages();updateState(result.state);
      if(result.legacy_state_warning)toast('Older turn adjusted; earlier campaign state could not be fully rewound.',true);
      else toast(operation==='delete'?'Messages removed. You can now resend your action.':'GM response replaced successfully.');
      if(operation==='retry'&&$('autoplay').checked)speak(result.narration);
      await refreshLibrary();
    }catch(err){$('story-correction-status').textContent=err.message;toast(err.message,true)}
    finally {state.busy=false;$('send-action').disabled=false;if(document.contains(btn))btn.disabled=false;}
  };
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
// Fables-inspired navigation pattern: left rail opens full library panels;
// the right sidebar continues to show a compact live scene/character snapshot.
function closeCodex() {
  $('codex-overlay').classList.add('hidden');$('codex-overlay').setAttribute('aria-hidden','true');
  $('nav-character').classList.remove('active');$('nav-world-lore').classList.remove('active');$('nav-journal').classList.remove('active');
}
function showCodex(mode='character') {
  if(!state.active || !state.world)return;
  const pc=state.active.pc_profile||{};
  const title=mode==='character'?state.active.pc_name:mode==='world'?state.world.title:'Adventure Journal';
  $('codex-eyebrow').textContent=mode==='character'?'CHARACTER RECORD':mode==='world'?'WORLD ATLAS':'YOUR STORY SO FAR';
  $('codex-title').textContent=title;
  $('codex-overlay').classList.remove('hidden');$('codex-overlay').setAttribute('aria-hidden','false');
  for(const x of ['character','world-lore','journal'])$('nav-'+x).classList.toggle('active',x===(mode==='world'?'world-lore':mode));
  if(mode==='character') renderCodexCharacter();
  else if(mode==='world')renderCodexWorld();
  else renderCodexJournal();
  $('codex-close').focus();
}
function paragraph(value){return escapeHtml(value||'Not recorded yet.').replace(/\n/g,'<br>')}
function codexSection(title,content){return `<section class="codex-section"><h3>${escapeHtml(title)}</h3><div class="codex-prose">${content}</div></section>`}
function renderCodexCharacter(){
  const pc=state.active.pc_profile||{};
  const tabs=[['sheet','Character Sheet'],['inventory','Inventory'],['spellbook','Spellbook'],['progression','Progression'],['relationships','Relationships'],['memories','Memories']];
  $('codex-body').innerHTML=`<div class="codex-character-hero">
    <div class="codex-portrait"><img id="codex-portrait-image" class="hidden" alt="Portrait of ${escapeHtml(state.active.pc_name)}"><span id="codex-portrait-placeholder">✦</span></div>
    <div class="codex-profile-heading"><h2>${escapeHtml(state.active.pc_name)}</h2><p>${escapeHtml([pc.level?'Level '+pc.level:'',pc.species,pc.role,pc.alignment].filter(Boolean).join(' · '))}</p><p class="codex-profile-summary">${escapeHtml((pc.appearance||pc.personality||'Your story begins here.').slice(0,320))}</p></div>
    <div class="codex-art-actions"><label class="button secondary small upload-label">Upload image<input type="file" id="codex-upload" accept="image/png,image/jpeg,image/webp" hidden></label><button class="button ghost small" id="codex-generate-portrait">✧ Generate portrait</button><button class="button ghost small" id="codex-edit">✎ Edit character</button><p class="muted note" id="codex-art-status">Portraits are saved on this computer.</p></div>
  </div><div class="codex-tabs" role="tablist">${tabs.map(([key,label])=>`<button class="codex-tab ${state.codexTab===key?'active':''}" data-codex-tab="${key}" role="tab" aria-selected="${state.codexTab===key}">${label}</button>`).join('')}</div><div id="codex-tab-content" class="codex-tab-content"></div>`;
  renderCodexTab();loadPortraitInCodex();
  document.querySelectorAll('[data-codex-tab]').forEach(b=>b.onclick=()=>{state.codexTab=b.dataset.codexTab;renderCodexTab();document.querySelectorAll('[data-codex-tab]').forEach(x=>{x.classList.toggle('active',x.dataset.codexTab===state.codexTab);x.setAttribute('aria-selected',String(x.dataset.codexTab===state.codexTab))})});
  $('codex-edit').onclick=()=>showEditCharacterModal();
  $('codex-upload').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{$('codex-art-status').textContent='Saving portrait…';await uploadPortrait(state.active.id,file);loadPortraitInCodex();renderPortraitThumb(state.active.id);$('codex-art-status').textContent='Portrait saved.';}catch(err){$('codex-art-status').textContent=err.message;toast(err.message,true)}};
  $('codex-generate-portrait').onclick=()=>generateArt('portrait',true);
}
function renderCodexTab(){
  const pc=state.active.pc_profile||{},s=state.active.state||{};
  const rows=[['Species',pc.species],['Role',pc.role],['Alignment',pc.alignment],['Pronouns',pc.pronouns],['Titles',pc.aliases],['Level',pc.level],['Armour',pc.armor_class],['Hit points (maximum)',pc.max_hp]];
  const t=state.codexTab;let html='';
  if(t==='sheet')html=`<div class="codex-grid">${codexSection('Details',rows.filter(x=>x[1]).map(([k,v])=>`<div class="codex-data"><span>${k}</span><strong>${escapeHtml(v)}</strong></div>`).join('')||'<p class="muted">No details recorded.</p>')}${codexSection('Appearance',paragraph(pc.appearance))}${codexSection('Personality & Mannerisms',paragraph([pc.personality,pc.mannerisms].filter(Boolean).join('\n\n')))}${codexSection('History & Motivations',paragraph([pc.background,pc.motivation,pc.weaknesses].filter(Boolean).join('\n\n')))}</div>`;
  else if(t==='inventory')html=codexSection('Inventory',(s.inventory||[]).length?`<ul>${s.inventory.map(v=>`<li>${escapeHtml(v)}</li>`).join('')}</ul>`:'<p class="muted">Your inventory is empty.</p>');
  else if(t==='spellbook')html=codexSection('Abilities and Spells',spellLibraryMarkup(pc,state.active.id));
  else if(t==='progression')html=codexSection('Character progression',`<p>Level: ${escapeHtml(pc.level||'Not specified')}</p><p class="muted">There is no automatic XP or levelling system yet. Your character changes through the story.</p>`);
  else if(t==='relationships')html=codexSection('Relationships', '<p class="muted">Automatic relationship tracking is not implemented yet. The Game Master may still remember relationships described in your narrative.</p>');
  else html=codexSection('Memories',(s.journal||[]).length?`<ol>${s.journal.map(v=>`<li>${escapeHtml(v)}</li>`).join('')}</ol>`:'<p class="muted">No memories recorded yet.</p>');
  $('codex-tab-content').innerHTML=html;
  if(t==='spellbook')wireSpellButtons('campaigns',state.active.id,pc);
}
function renderCodexWorld(){
  const w=state.world;
  $('codex-body').innerHTML=`<div class="codex-world-header"><h2>${escapeHtml(w.title)}</h2><p>${escapeHtml(w.description||'Explore this world through your story.')}</p><span class="muted">Created by ${escapeHtml(w.author||'Unknown')}</span><br><button class="button secondary small" id="codex-research-lore">◈ Discover lore</button> <button class="button secondary small" id="codex-gm-context">◎ GM lore context</button></div><div class="codex-grid">${(w.sections||[]).slice(0,150).map(e=>codexSection(e.title||'Lore',`<div class="eyebrow">${escapeHtml(e.kind||'lore')}</div>${paragraph((e.content||'').slice(0,10000))}`)).join('')}</div>`;
  $('codex-research-lore')?.addEventListener('click',()=>showLoreResearch(w.id,w.title));
  $('codex-gm-context')?.addEventListener('click',showGmLoreContext);
}
function renderCodexJournal(){
  const journal=state.active.state?.journal||[];
  $('codex-body').innerHTML=codexSection('Story developments',journal.length?`<ol class="codex-journal">${journal.map((text,index)=>`<li class="development-entry"><span>${escapeHtml(text)}</span><button class="remove-development" data-index="${index}" aria-label="Remove this development" title="Remove inaccurate story development">✕</button></li>`).join('')}</ol>`:'<p class="muted">Your adventure is just beginning.</p>');
  wireJournalRemoval($('codex-body'));
}
async function uploadPortrait(id,file){
  if(file.size>8*1024*1024)throw new Error('Portrait must be smaller than 8 MB');
  if(!['image/png','image/jpeg','image/webp'].includes(file.type))throw new Error('Choose PNG, JPEG or WebP');
  const response=await fetch('/api/campaigns/'+encodeURIComponent(id)+'/portrait',{method:'POST',headers:{'Content-Type':file.type},body:file});
  let data;try{data=await response.json()}catch{throw new Error('Could not upload image')}
  if(!response.ok)throw new Error(data.error||'Image upload failed');
  state.portraitRev=Date.now();return data;
}
function loadPortraitInCodex(){
  const img=$('codex-portrait-image');if(!img||!state.active)return;
  img.onload=()=>{img.classList.remove('hidden');$('codex-portrait-placeholder').classList.add('hidden')};
  img.onerror=()=>{img.classList.add('hidden');$('codex-portrait-placeholder').classList.remove('hidden')};
  img.src='/api/artwork/portraits/'+encodeURIComponent(state.active.id)+'?v='+state.portraitRev;
}
function renderPortraitThumb(id){
  const img=$('side-character-image');if(!img)return;
  img.onload=()=>{img.classList.remove('hidden');$('character-emblem-symbol').classList.add('hidden')};
  img.onerror=()=>{img.classList.add('hidden');$('character-emblem-symbol').classList.remove('hidden')};
  img.src='/api/artwork/portraits/'+encodeURIComponent(id)+'?v='+state.portraitRev;
}
let artPolling=null;
function stopArtPolling(){if(artPolling){clearInterval(artPolling);artPolling=null}}
function showSceneArt(data){
  if(!data||!state.active)return;
  if((data.location||'Unknown')!==state.sceneLocation)return;
  state.sceneRecord=data;
  const img=$('scene-image'),art=$('scene-art-placeholder');
  $('scene-expand').disabled=!data.url;
  const story=$('adventure');
  if(data.url && /^\/api\/artwork\/scenes\/[a-zA-Z0-9%_-]+\/[a-zA-Z0-9%_-]+$/.test(data.url)){
    // Keep the background tied to the same cached artwork as the Scene card.
    story.style.setProperty('--story-scene-art', `url("${data.url}")`);
    story.classList.add('has-scene-background');
  }else{
    story.classList.remove('has-scene-background');
    story.style.removeProperty('--story-scene-art');
  }
  if(data.url){img.onload=()=>{img.classList.remove('hidden');art.classList.add('hidden')};img.onerror=()=>{img.classList.add('hidden');art.classList.remove('hidden')};img.src=data.url+'?v='+encodeURIComponent(data.key||'')+(data.job?.status==='ready'?'&stamp='+Date.now():'')}
  else {img.removeAttribute('src');img.classList.add('hidden');art.classList.remove('hidden')}
  $('scene-lock').textContent=data.locked?'♢ Unlock':'♧ Lock';$('scene-lock').disabled=!data.url;
  $('scene-refresh').disabled=!data.url||data.locked;
  const job=data.job;
  $('scene-art-status').textContent=job?.status==='generating'?'Generating scene artwork in ComfyUI…':job?.status==='failed'?'Art failed: '+job.error:data.locked?'Scene image locked':data.url?'Cached illustration for this location.':'No illustration yet. Generate one using ComfyUI.';
}
async function refreshSceneArtwork(auto=false){
  if(!state.active)return;
  const campaignId=state.active.id,loc=state.sceneLocation;
  const data=await request('/api/artwork/scene?campaign_id='+encodeURIComponent(campaignId));
  if(campaignId!==state.active?.id||loc!==state.sceneLocation)return;
  showSceneArt(data.scene);
  if(data.scene?.job?.status==='generating')startArtPolling('scene');
  else if(auto&&!data.scene?.url&&!data.scene?.job){
    const status=await getArtStatus();
    if(status.available && status.checkpoints.length && state.active?.id===campaignId && loc===state.sceneLocation)await generateArt('scene',false,true);
  }
}
async function getArtStatus(force=false){
  if(!force && state.artStatus && Date.now()-state.artStatus.checked<30000)return state.artStatus;
  const status=await request('/api/artwork/status');state.artStatus={...status,checked:Date.now()};return state.artStatus;
}
async function chooseArtCheckpoint(){
  const status=await getArtStatus(true);
  if(!status.available||!status.checkpoints.length)throw new Error('ComfyUI is not ready. Start local ComfyUI with an image-generation checkpoint; see README.');
  const saved=settingsGet('comfy_checkpoint','');
  const chosen=status.checkpoints.includes(saved)?saved:status.checkpoints[0];
  settingsPut('comfy_checkpoint',chosen);
  return chosen;
}
async function generateArt(kind,refresh=false,silent=false){
  if(!state.active)return;
  try{
    const checkpoint=await chooseArtCheckpoint();
    const cid=state.active.id;
    const result=await request(kind==='scene'?'/api/artwork/generate-scene':'/api/campaigns/'+cid+'/portrait/generate',
      {method:'POST',body:kind==='scene'?{campaign_id:cid,checkpoint,refresh}:{checkpoint}});
    if(kind==='scene'){if(!silent)toast('Generating location art in the background');await refreshSceneArtwork();startArtPolling('scene')}
    else {if($('codex-art-status'))$('codex-art-status').textContent='Generating portrait in ComfyUI…';startArtPolling('portrait');if(!silent)toast('Generating portrait in the background')}
  }catch(err){if(!silent)toast(err.message,true);if($('scene-art-status')&&kind==='scene')$('scene-art-status').textContent=err.message}
}
function startArtPolling(kind){
  stopArtPolling();let tries=0;
  artPolling=setInterval(async()=>{
    try{
      if(!state.active || ++tries>95){stopArtPolling();return}
      if(kind==='scene'){
        const data=await request('/api/artwork/scene?campaign_id='+encodeURIComponent(state.active.id));showSceneArt(data.scene);
        if(data.scene.job?.status!=='generating')stopArtPolling();
      }else{
        const job=await request('/api/artwork/job?kind=portrait&campaign_id='+encodeURIComponent(state.active.id));
        if(job.job?.status!=='generating'){
          stopArtPolling();if(job.job?.status==='ready'){state.portraitRev=Date.now();loadPortraitInCodex();renderPortraitThumb(state.active.id)}
          if($('codex-art-status'))$('codex-art-status').textContent=job.job?.status==='failed'?job.job.error:'Portrait ready.';
        }
      }
    }catch{stopArtPolling()}
  },3000);
}
async function toggleSceneLock(){
  if(!state.active||!state.sceneRecord?.url)return;
  try{const response=await request('/api/artwork/lock-scene',{method:'POST',body:{campaign_id:state.active.id,locked:!state.sceneRecord.locked}});showSceneArt(response.scene)}catch(err){toast(err.message,true)}
}

function spellImageUrl(id){return '/api/spell-images/'+encodeURIComponent(id);}
function spellLibraryMarkup(pc,ownerId){
  const spells=pc.ability_details||[];
  return `<p class="muted">Describe what each spell does so your Game Master uses its real effects, costs and limitations.</p><div class="spell-gallery">${spells.map(spell=>`<div class="spell-entry"><div class="spell-art"><img src="${spellImageUrl(spell.id)}" alt="Artwork for ${escapeHtml(spell.name)}" loading="lazy" onerror="this.style.display='none'"></div><div class="spell-entry-body"><h4>${escapeHtml(spell.name)}</h4><small>${escapeHtml(spell.kind||'Ability')}</small><p>${escapeHtml(spell.effect||'Add a description so the Game Master understands this ability.')}</p><button type="button" class="button secondary small edit-spell" data-spell-id="${escapeHtml(spell.id)}">✎ Edit ability</button></div></div>`).join('')||'<p class="muted">No spells added yet.</p>'}</div><button type="button" id="spell-add" class="button primary small">＋ Add spell or ability</button>`;
}
function wireSpellButtons(scope,ownerId,pc){
  document.querySelectorAll('.edit-spell').forEach(b=>b.onclick=()=>showSpellEditor(scope,ownerId,pc,b.dataset.spellId));
  const add=$('spell-add');if(add)add.onclick=()=>showSpellEditor(scope,ownerId,pc,null);
}
function spellInput(id,label,value='',rows=0){
  if(rows)return `<label class="field"><span>${label}</span><textarea id="${id}" rows="${rows}">${escapeHtml(value)}</textarea></label>`;
  return `<label class="field"><span>${label}</span><input id="${id}" value="${escapeHtml(value)}"></label>`;
}
function showSpellEditor(scope,ownerId,pc,spellId){
  const current=(pc.ability_details||[]).find(x=>x.id===spellId)||{};
  const newId=spellId||crypto.randomUUID();
  showModal('SPELLS & ABILITIES', current.name?'Edit '+current.name:'New ability', `<form id="spell-form">
     ${spellInput('spell-name','NAME',current.name||'')}
     ${spellInput('spell-kind','TYPE (SPELL / PASSIVE / SUMMON / TECHNIQUE)',current.kind||'')}
     ${spellInput('spell-effect','WHAT IT DOES — THE GAME MASTER USES THIS',current.effect||'',5)}
     ${spellInput('spell-visual','WHAT IT LOOKS LIKE',current.visual||'',3)}
     <div class="form-grid">${spellInput('spell-range','RANGE',current.range||'')}${spellInput('spell-target','TARGET',current.target||'')}</div>
     ${spellInput('spell-cost','COST / COOLDOWN',current.cost||'')}
     ${spellInput('spell-limitations','LIMITATIONS / CONDITIONS',current.limitations||'',3)}
     ${spellInput('spell-flavor','FLAVOUR / HISTORY (OPTIONAL)',current.flavor||'',2)}
     <div class="spell-art-editor"><img src="${spellImageUrl(newId)}" alt="Spell art" onerror="this.style.display='none'" class="spell-editor-image"><label class="field"><span>UPLOAD SPELL ART (PNG, JPEG, WEBP — 8 MB MAX)</span><input id="spell-file" type="file" accept="image/png,image/jpeg,image/webp"></label><label class="field"><span>GENERATE WITH COMFYUI AFTER SAVING</span><input id="spell-want-generate" type="checkbox"> Generate artwork from the effect and visual description</label><p class="muted note">ComfyUI requires a running local service and image checkpoint; uploading works immediately without it.</p></div>
     <button class="button primary full" type="submit">Save spell and artwork →</button>
     ${current.id?'<button class="button ghost full" type="button" id="spell-delete">Remove ability</button>':''}
     <p class="muted note" id="spell-editor-status"></p></form>`);
  const all=(pc.ability_details||[]).map(x=>({...x}));
  const url='/api/'+scope+'/'+encodeURIComponent(ownerId)+'/abilities';
  const refresh=async()=>{
    if(scope==='campaigns'){
      const data=await request('/api/campaigns/'+encodeURIComponent(ownerId));state.active=data.campaign;
      renderCharacter(state.active);if(!$('codex-overlay').classList.contains('hidden')){state.codexTab='spellbook';renderCodexCharacter();}
    }else{
      await refreshLibrary();renderLibraryCharacterDetail(ownerId);
    }
  };
  const save=async(remove=false)=>{
    const btn=$('spell-form').querySelector('button[type=submit]');btn.disabled=true;
    try{
      let next=[...all];
      if(remove){next=next.filter(x=>x.id!==newId);}
      else{
        const name=$('spell-name').value.trim();if(!name)throw Error('Enter a spell name.');
        const item={id:newId,name,...Object.fromEntries(['kind','effect','visual','range','target','cost','limitations','flavor'].map(k=>[k,$('spell-'+k).value.trim()]))};
        const index=next.findIndex(x=>x.id===newId);
        if(index>=0)next[index]=item;else next.push(item);
      }
      const saved=await request(url,{method:'PATCH',body:{abilities:next}});
      if(!remove){
        const file=$('spell-file').files[0];
        if(file){
          if(file.size>8*1024*1024||!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Use PNG, JPEG or WebP below 8 MB.');
          const charId=scope==='characters'?ownerId:state.active.character_id;
          if(!charId)throw Error('No reusable character linked to this campaign');
          const res=await fetch('/api/characters/'+encodeURIComponent(charId)+'/spells/'+encodeURIComponent(newId)+'/image',{method:'POST',headers:{'Content-Type':file.type},body:file});
          if(!res.ok)throw Error((await res.json()).error||'Could not upload spell artwork');
        }
        if($('spell-want-generate').checked) {
          const charId=scope==='characters'?ownerId:state.active.character_id;
          const info=await request('/api/artwork/status');
          if(!info.available||!(info.checkpoints||[]).length){toast('Spell saved. ComfyUI is not ready for generation; upload art now or install ComfyUI and a checkpoint.',true)}
          else{
            const checkpoint=settingsGet('comfy_checkpoint','')||info.checkpoints[0];
            await request('/api/characters/'+encodeURIComponent(charId)+'/spells/'+encodeURIComponent(newId)+'/generate',{method:'POST',body:{checkpoint}});
            toast('Spell saved. Artwork is generating in the background.');
          }
        }
      }
      closeModal();await refresh();toast(remove?'Spell removed.':'Spell description saved. The GM can now use it.');
    }catch(e){$('spell-editor-status').textContent=e.message;toast(e.message,true)}finally{btn.disabled=false;}
  };
  $('spell-form').onsubmit=e=>{e.preventDefault();save(false)};
  if($('spell-delete'))$('spell-delete').onclick=()=>save(true);
}
function speechPlainText(text){
  return String(text||'')
    .replace(/^\[[^\]\n]{3,230}\]\s*\n*/, '')
    .replace(/\\([*`_])/g,'$1')
    .replace(/(\*{1,3})([^*\n]+?)\1/g,(_,stars,content)=>content.trim())
    .replace(/(^|\s)_{1,2}([^_\n]+?)_{1,2}(?=\s|$|[.,!?])/g,(_,before,content)=>before+content.trim())
    .replace(/`+([^`\n]+?)`+/g,(_,content)=>content.trim())
    .replace(/(^|\s)\*+(?=\s|$)/g,'$1')
    .trim();
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
  for(const controller of pendingSpeechRequests)controller.abort();pendingSpeechRequests.clear();
  if(activeAudio){activeAudio.pause();activeAudio.removeAttribute('src');activeAudio.load();activeAudio=null;}
  if(activeUrl){URL.revokeObjectURL(activeUrl);activeUrl=null;}
}
function stopSpeech(){
  speechSequence++;clearAudio();
  if('speechSynthesis' in window) speechSynthesis.cancel();
  state.speechPaused=false;state.speaking=false;
  narrationStatus('Narration stopped');updatePlaybackButtons();ambientSetVolume();
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
  narrationStatus('Narration finished');updatePlaybackButtons();ambientSetVolume();
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
function fastStartChunks(text){
  const sentences=String(text).match(/[^.!?\n]+[.!?\n]*/g)||[text];
  const first=sentences[0]||'';
  if(first.length>=20 && first.length<=260){
    return [first.trim(),...speechChunks(sentences.slice(1).join(''),500)].filter(Boolean);
  }
  return speechChunks(text,260);
}
const pendingSpeechRequests=new Set();
async function fetchNeuralChunk(chunk,seq){
  const controller=new AbortController();pendingSpeechRequests.add(controller);
  try{
    const response=await fetch('/api/tts/speech',{
      method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
      body:JSON.stringify({text:chunk,voice:$('voices').value||'bm_george',speed:Number($('speed').value)})
    });
    if(!response.ok){let detail;try{detail=(await response.json()).error}catch{}throw new Error(detail||'Neural voice request failed');}
    const blob=await response.blob();
    if(seq!==speechSequence)return null;
    return blob;
  }finally{pendingSpeechRequests.delete(controller);}
}
async function playNeuralSpeech(text,seq){
  try{
    const chunks=fastStartChunks(text);
    if(!chunks.length){speechDone(seq);return;}
    // Start short initial speech quickly; prepare only ONE subsequent block at
    // a time in parallel while the previous audio plays.
    let nextBlob=fetchNeuralChunk(chunks[0],seq).catch(e=>e);
    for(let i=0;i<chunks.length;i++){
      if(seq!==speechSequence)return;
      narrationStatus(state.speechPaused?'Narration paused':'Preparing natural voice…');
      const blob=await nextBlob;
      if(seq!==speechSequence || !blob)return;
      if(blob instanceof Error)throw blob;
      nextBlob=i+1<chunks.length?fetchNeuralChunk(chunks[i+1],seq).catch(e=>e):null;
      const url=URL.createObjectURL(blob);activeUrl=url;
      const audio=new Audio(url);activeAudio=audio;audio.volume=Number($('volume').value)/100;
      await new Promise((resolve,reject)=>{
        let complete=false;
        function finish(error){if(complete)return;complete=true;cancelAudioWait=null;if(error)reject(error);else resolve();}
        cancelAudioWait=()=>finish();
        audio.onended=()=>finish();
        audio.onerror=()=>finish(new Error('Could not play generated narration audio'));
        if(state.speechPaused)return;
        audio.play().then(()=>narrationStatus('Reading aloud')).catch(finish);
      });
      if(seq!==speechSequence)return;
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
  text=speechPlainText(text);
  if(!text.trim())return;
  stopSpeech();const seq=speechSequence;
  state.speaking=true;state.speechPaused=false;ambientSetVolume();
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
// A local user can install a verified GitHub release immediately or select a ZIP.
function openUpdatesModal(){
  showModal('APPLICATION UPDATES', 'Update Storyforge', `
    <p class="muted modal-intro">Future verified GitHub releases can install automatically when Storyforge isn't being used. Saved campaigns are backed up before each installation.</p>
    <div class="world-preview"><strong>Installed:</strong> <span id="update-installed">Checking...</span><p class="muted note" id="update-prev-result"></p></div>
    <label class="toggle-line"><input type="checkbox" id="auto-updates" checked> Automatically install trusted updates when idle</label>
    <p class="muted note" id="update-channel">Checking GitHub release channel…</p>
    <button class="button primary full" id="install-latest-now">Check &amp; install latest release now</button>
    <p class="muted note">Updates immediately at your request—even while you're using Storyforge. Your current session will briefly disconnect during restart.</p>
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
  $('install-latest-now').onclick=async()=>{
    const button=$('install-latest-now');
    button.disabled=true;
    $('update-result').textContent='Checking the official GitHub release and installing if a newer version exists…';
    try{
      const oldVersion=(await request('/api/updates')).version;
      await request('/api/updates/install-latest',{method:'POST',body:{}});
      for(let attempt=0;attempt<110;attempt++){
        await new Promise(resolve=>setTimeout(resolve,1000));
        try{
          const data=await request('/api/updates');
          updateIndicator(data);
          const phase=data.channel?.phase;
          if(data.version!==oldVersion && data.status?.phase==='completed'){
            $('update-result').textContent='Updated to v'+data.version+'. Reloading…';
            location.reload();return;
          }
          if(phase==='current'){
            $('update-result').textContent='You already have the latest published Storyforge version.';
            return;
          }
          if(phase==='failed'||phase==='unavailable'){
            $('update-result').textContent='GitHub update could not finish: '+(data.channel?.error||'See updater.log');
            return;
          }
          if(phase==='downloading')$('update-result').textContent='Downloading and verifying the official release…';
          if(phase==='installing')$('update-result').textContent='Installing update and restarting Storyforge…';
        }catch{/* The server briefly goes offline during restart. */}
      }
      $('update-result').textContent='Still waiting for Storyforge to restart. See data/updates/updater.log if needed.';
    }catch(e){$('update-result').textContent=e.message;toast(e.message,true)}
    finally{button.disabled=false;}
  };
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
$('home-home').onclick=toLibrary;
$('home-discover').onclick=()=>{$('discovery-section').scrollIntoView({behavior:'smooth'})};
$('home-campaigns').onclick=()=>{$('recent-section').scrollIntoView({behavior:'smooth'})};
$('home-characters').onclick=showCharacterLibrary;
$('home-import').onclick=showImportModal;
$('home-create').onclick=()=>{$('discovery-section').scrollIntoView({behavior:'smooth'})};
$('home-new-adventure').onclick=()=>{$('discovery-section').scrollIntoView({behavior:'smooth'})};
$('nav-story').onclick=openAdventureOrNotice;
$('nav-adventures').onclick=()=>{$('campaign-links').classList.toggle('hidden');};
$('nav-character').onclick=()=>{if(state.active&&state.world)showCodex('character');else showCharacterLibrary();};
$('nav-world-lore').onclick=()=>{if(!state.active){toLibrary();return}showCodex('world');};
$('nav-journal').onclick=()=>{if(!state.active)return openAdventureOrNotice();showCodex('journal');};
$('nav-settings').onclick=()=>{if(!state.active)return toast('Open an adventure to configure its narrator.');revealDetailsOnMobile();$('voice-settings').open=true;$('voice-settings').scrollIntoView({block:'nearest',behavior:'smooth'});};
$('composer-abilities').onclick=()=>{if(!state.active)return;state.codexTab='spellbook';showCodex('character');};
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
$('codex-close').onclick=closeCodex;
$('codex-overlay').onclick=e=>{if(e.target===$('codex-overlay'))closeCodex()};
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeCodex();closeModal()}});
$('scene-generate').onclick=()=>generateArt('scene',false);
$('scene-refresh').onclick=()=>generateArt('scene',true);
$('scene-lock').onclick=toggleSceneLock;
$('scene-expand').onclick=()=>{
  const img=$('scene-image');
  if(img.classList.contains('hidden')||!img.getAttribute('src'))return;
  $('scene-lightbox-image').src=img.src;
  $('scene-lightbox-name').textContent=$('scene-title').textContent||'Location artwork';
  $('scene-lightbox').showModal();
};
$('scene-lightbox-close').onclick=()=>$('scene-lightbox').close();
$('scene-lightbox').onclick=e=>{if(e.target===$('scene-lightbox'))$('scene-lightbox').close()};
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

// Local, procedural instrumental soundtrack. Runs entirely in Web Audio on this
// device: no web-streamed or copyrighted tracks. A user click is required
// before AudioContext can produce sound in Brave/Chromium.
const AMBIENT_MOODS={
  exploration:{tones:[146.83,174.61,220,293.66],melody:[293.66,349.23,440,392,293.66],tempo:2700,filter:1800},
  tavern:{tones:[196,246.94,293.66,392],melody:[392,440,493.88,587.33,440],tempo:2150,filter:2400},
  mystery:{tones:[110,130.81,164.81,220],melody:[220,246.94,261.63,196,174.61],tempo:3400,filter:1000},
  danger:{tones:[110,130.81,155.56,220],melody:[220,233.08,261.63,155.56,220],tempo:1800,filter:950},
  peace:{tones:[174.61,220,261.63,349.23],melody:[349.23,392,440,523.25,440],tempo:3300,filter:2000}
};
const ambient={context:null,master:null,drone:[],tick:null,playing:false,mood:'',counter:0};
function ambientSceneMood(){
  const txt=((state.active?.state?.location||'')+' '+(state.lastNarration||'').slice(-1400)).toLowerCase();
  if(/battle|fight|attack|ambush|combat|bloodshed|chase|siege/.test(txt))return 'danger';
  if(/tavern|inn|pub|market|festival|ballroom|feast/.test(txt))return 'tavern';
  if(/crypt|grave|dungeon|shadow|fog|haunted|cemetery|mystery/.test(txt))return 'mystery';
  if(/garden|sanctuary|chapel|temple|peaceful|meadow/.test(txt))return 'peace';
  return 'exploration';
}
function ambientSelectedMood(){return $('ambient-mood').value==='auto'?ambientSceneMood():$('ambient-mood').value;}
function ambientSetVolume(){
  $('ambient-volume-value').textContent=$('ambient-volume').value+'%';
  settingsPut('ambient-volume',$('ambient-volume').value);
  if(ambient.master&&ambient.context){
    const target=Number($('ambient-volume').value)/100*(state.speaking ? 0.32 : 1);
    ambient.master.gain.setTargetAtTime(target,ambient.context.currentTime,.2);
  }
}
function ambientStopNotes(){
  if(ambient.tick){clearInterval(ambient.tick);ambient.tick=null;}
  for(const oscillator of ambient.drone){try{oscillator.stop()}catch{}}
  ambient.drone=[];
}
function ambientTone(hertz,at,length,level,kind='sine'){
  const ctx=ambient.context;if(!ctx||!ambient.master)return;
  const oscillator=ctx.createOscillator();oscillator.type=kind;oscillator.frequency.setValueAtTime(hertz,at);
  const gain=ctx.createGain();gain.gain.setValueAtTime(.00001,at);
  gain.gain.linearRampToValueAtTime(level,at+Math.min(.7,length/3));
  gain.gain.exponentialRampToValueAtTime(.00001,at+length);
  oscillator.connect(gain);gain.connect(ambient.master);
  oscillator.start(at);oscillator.stop(at+length+.01);
}
function ambientStartMood(){
  if(!ambient.context||!ambient.playing)return;
  const mood=ambientSelectedMood();if(mood===ambient.mood && ambient.tick)return;
  ambientStopNotes();ambient.mood=mood;ambient.counter=0;
  const cfg=AMBIENT_MOODS[mood]||AMBIENT_MOODS.exploration;
  const ctx=ambient.context;
  // Low organ-like atmospheric pad with slow independent pulses.
  cfg.tones.slice(0,3).forEach((note,i)=>{
    const osc=ctx.createOscillator();osc.type='sine';osc.frequency.value=note/(i===0?2:1);
    const amp=ctx.createGain();amp.gain.value=i===0?.055:.025;
    osc.connect(amp);amp.connect(ambient.master);osc.start();ambient.drone.push(osc);
  });
  const playNote=()=>{
    if(!ambient.playing||ambient.context?.state!=='running')return;
    const n=ambient.counter++;
    const note=cfg.melody[(n+(n%3===0?1:0))%cfg.melody.length];
    ambientTone(note,ctx.currentTime+.05,cfg.tempo/1000*1.05,.035,'sine');
    if(n%4===0)ambientTone(note*1.5,ctx.currentTime+.7,1.9,.011,'triangle');
  };
  playNote();ambient.tick=setInterval(playNote,cfg.tempo);
  $('ambient-status').textContent='Playing '+mood+' · ducking under GM voice';
}
async function ambientToggle(force){
  const enable=typeof force==='boolean'?force:!ambient.playing;
  if(!enable){ambient.playing=false;ambientStopNotes();
    if(ambient.context){await ambient.context.suspend().catch(()=>{});}
    $('ambient-toggle').textContent='▶ Play music';$('ambient-status').textContent='Music paused';return;
  }
  const AudioContextClass=window.AudioContext||window.webkitAudioContext;
  if(!AudioContextClass){toast('This browser does not support local ambient audio',true);return;}
  try{
    if(!ambient.context){ambient.context=new AudioContextClass();ambient.master=ambient.context.createGain();ambient.master.connect(ambient.context.destination);}
    await ambient.context.resume();ambient.playing=true;
    ambientSetVolume();ambientStartMood();$('ambient-toggle').textContent='■ Stop music';
  }catch(e){ambient.playing=false;toast('Could not start ambient audio: '+e.message,true);}
}
$('ambient-auto').checked=settingsGet('ambient-enabled','false')==='true';
$('ambient-mood').value=settingsGet('ambient-mood','auto');
$('ambient-volume').value=settingsGet('ambient-volume','22');ambientSetVolume();
$('ambient-toggle').onclick=()=>{const on=!ambient.playing;$('ambient-auto').checked=on;settingsPut('ambient-enabled',String(on));ambientToggle(on);};
$('ambient-auto').onchange=()=>{settingsPut('ambient-enabled',String($('ambient-auto').checked));ambientToggle($('ambient-auto').checked);};
$('ambient-mood').onchange=()=>{settingsPut('ambient-mood',$('ambient-mood').value);if(ambient.playing)ambientStartMood();};
$('ambient-volume').oninput=ambientSetVolume;
// Autoplay policies require an explicit interaction after every browser launch.
// If music was enabled in a previous visit, resume on the next user gesture.
if($('ambient-auto').checked){
  $('ambient-status').textContent='Tap Play music to resume your saved soundtrack';
  document.addEventListener('pointerdown',()=>{if($('ambient-auto').checked&&!ambient.playing)ambientToggle(true);},{once:true});
}

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
document.querySelector('.app-shell').classList.add('home-view');
refreshLibrary().catch(e=>toast(e.message,true));

// Keep an open, visible campaign safe from unattended application restarts.
function storyforgeActivity(){if(document.visibilityState==='visible')fetch('/api/updates/activity',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).catch(()=>{});}
setInterval(storyforgeActivity,30000); storyforgeActivity();
