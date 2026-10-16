"""Run the scene-memory controls in the shared Node/DOM request harness."""
import unittest

import test_story_request_ui as story_ui


MEMORY_HARNESS = r"""
for(const id of ['nav-journal','nav-character','codex-body','codex-tab-content']){
  nodes.set(id,new Element(id));
}
let allowRemoval=true;
const confirmations=[];
context.window.confirm=message=>{confirmations.push(message);return allowRemoval;};
vm.runInContext(`
  var memoryRepaints=[];
  renderCodexJournal=()=>memoryRepaints.push('journal');
  renderCodexCharacter=()=>memoryRepaints.push('character');
`,context);
const memoryUi=vm.runInContext('({renderSceneMemory,wireSceneMemoryRemoval,memoryRepaints})',context);
let buttonNumber=0;
function memoryButton(payload){
  const button=new Element('remembered-fact-'+(++buttonNumber));
  button.dataset={memory:JSON.stringify(payload)};
  nodes.set(button.id,button);
  memoryUi.wireSceneMemoryRemoval({querySelectorAll:selector=>{
    assert.equal(selector,'.remove-scene-memory');return [button];
  }});
  return button;
}
function decodeAttribute(value){
  const entities={'&quot;':'"','&#39;':"'",'&lt;':'<','&gt;':'>','&amp;':'&'};
  return value.replace(/&quot;|&#39;|&lt;|&gt;|&amp;/g,match=>entities[match]);
}
function renderedPayloads(html){
  return [...html.matchAll(/data-memory="([^"]*)"/g)]
    .map(match=>JSON.parse(decodeAttribute(match[1])));
}
"""


@unittest.skipUnless(story_ui.NODE, 'Node is required for browser request behavior checks')
class SceneMemoryUiTests(unittest.TestCase):
    def run_js(self, script):
        # Reuse the existing application loader, fake DOM and async completion
        # checks without loading that module's test class a second time.
        story_ui.StoryRequestUiTests.run_js(self, MEMORY_HARNESS + '\n' + script)

    def test_untrusted_memory_is_escaped_and_removal_payloads_round_trip(self):
        self.run_js(r"""
const name='Mara"><img src=x onerror="attack()"> & her \'friend\'';
const summary='SUMMARY <svg onload="attack()"> & "quoted"';
const npcFact='NPC </span><script>attack()</script> & \'quoted\'';
const thread='THREAD "><input autofocus onfocus="attack()">';
const event='EVENT <iframe src="javascript:attack()"> &amp;';
const memory={summary,npcs:[{name,facts:[npcFact]}],open_threads:[thread],events:[event]};
const html=memoryUi.renderSceneMemory(memory);
assert.ok(!/<(?:img|svg|script|input|iframe)\b/i.test(html));
assert.ok(html.includes('&lt;script&gt;'));
assert.ok(html.includes('&amp;amp;'));
assert.ok(html.includes('aria-label="Remove this remembered fact"'));
const payloads=renderedPayloads(html);
assert.equal(payloads.length,4);
assert.deepEqual(payloads,[
  {kind:'summary',index:0,text:summary,name:''},
  {kind:'npc_fact',index:0,text:npcFact,name},
  {kind:'open_threads',index:0,text:thread,name:''},
  {kind:'events',index:0,text:event,name:''}
]);
const ordinary=memoryUi.renderSceneMemory({npcs:[{name:'Mara',facts:['Mara guards the gate.']}],events:[],open_threads:[]});
assert.ok(ordinary.includes('<summary>Mara</summary>'));
assert.ok(ordinary.includes('<span>Mara guards the gate.</span>'));
""")

    def test_relationship_view_shows_only_npc_facts_with_exact_indices(self):
        self.run_js(r"""
const html=memoryUi.renderSceneMemory({summary:'SUMMARY_SENTINEL',
  npcs:[{name:'Mara',facts:['First fact.','Second fact.']}],
  open_threads:['THREAD_SENTINEL'],events:['EVENT_SENTINEL']},true);
assert.ok(!html.includes('SUMMARY_SENTINEL'));
assert.ok(!html.includes('THREAD_SENTINEL'));
assert.ok(!html.includes('EVENT_SENTINEL'));
assert.deepEqual(renderedPayloads(html),[
  {kind:'npc_fact',index:0,text:'First fact.',name:'Mara'},
  {kind:'npc_fact',index:1,text:'Second fact.',name:'Mara'}
]);
""")

    def test_success_removes_the_selected_fact_and_refreshes_the_visible_journal(self):
        self.run_js(r"""
app.state.active.id='campaign /with? punctuation';
const originalMessages=app.state.messages;
get('nav-journal').classList.add('active');
get('action').value='My next action remains a draft.';
const payload={kind:'npc_fact',index:1,text:'A particular fact.',name:'Mara & Orin'};
const button=memoryButton(payload);
const pending=button.onclick();
assert.equal(button.disabled,true);assert.equal(app.state.busy,true);
assert.equal(get('send-action').disabled,true);
assert.equal(app.calls.length,1);
assert.equal(app.calls[0].url,'/api/campaigns/campaign%20%2Fwith%3F%20punctuation/memory/remove');
assert.equal(app.calls[0].options.method,'POST');
assert.equal(JSON.stringify(app.calls[0].options.body),JSON.stringify(payload));
const replacement={location:'Before',scene_memory:{npcs:[{name:'Mara',facts:['A retained fact.']}]}};
resolveResponse({state:replacement,removed:true});await pending;
assert.equal(app.state.active.state,replacement);
assert.deepEqual([...app.painted],['state']);
assert.deepEqual([...memoryUi.memoryRepaints],['journal']);
assert.equal(app.state.messages,originalMessages);
assert.equal(get('action').value,'My next action remains a draft.');
assert.equal(app.state.busy,false);assert.equal(button.disabled,false);
assert.equal(get('send-action').disabled,false);
""")

    def test_response_cannot_replace_a_different_campaign_after_navigation(self):
        self.run_js(r"""
const originalCampaign=app.state.active;
const button=memoryButton({kind:'events',index:0,text:'Old remembered event.',name:''});
const pending=button.onclick();
const other={id:'second',state:{location:'Other town',scene_memory:{events:['Other event.']}}};
const messages=[{id:99,role:'gm',content:'A different campaign.'}];
app.state.active=other;app.state.messages=messages;
get('nav-character').classList.add('active');
resolveResponse({state:{location:'Old reply location',scene_memory:{events:[]}},removed:true});
await pending;
assert.equal(app.calls[0].url,'/api/campaigns/first/memory/remove');
assert.equal(app.state.active,other);
assert.equal(other.state.location,'Other town');
assert.deepEqual(other.state.scene_memory.events,['Other event.']);
assert.equal(originalCampaign.state.location,'Before');
assert.equal(app.state.messages,messages);
assert.equal(app.painted.length,0);assert.equal(memoryUi.memoryRepaints.length,0);
assert.equal(app.state.busy,false);assert.equal(get('send-action').disabled,false);
""")

    def test_response_cannot_update_a_new_view_of_the_same_campaign(self):
        self.run_js(r"""
const campaign=app.state.active, original=campaign.state;
const button=memoryButton({kind:'events',index:0,text:'Old remembered event.',name:''});
const pending=button.onclick();
// Returning home/reopening a view invalidates a request even if the campaign
// identity object has not yet been replaced by its fresh GET response.
vm.runInContext('campaignView++',context);
get('nav-journal').classList.add('active');
resolveResponse({state:{location:'Stale location'},removed:true});await pending;
assert.equal(app.state.active,campaign);assert.equal(campaign.state,original);
assert.equal(app.painted.length,0);assert.equal(memoryUi.memoryRepaints.length,0);
assert.equal(app.state.busy,false);assert.equal(button.disabled,false);
""")

    def test_cancel_makes_no_request_and_the_control_can_be_used_afterward(self):
        self.run_js(r"""
allowRemoval=false;
const campaign=app.state.active, original=campaign.state;
const button=memoryButton({kind:'events',index:0,text:'A selected event.',name:''});
await button.onclick();
assert.equal(app.calls.length,0);assert.equal(confirmations.length,1);
assert.equal(campaign.state,original);assert.equal(app.state.busy,false);
assert.equal(button.disabled,false);assert.equal(get('send-action').disabled,false);
allowRemoval=true;
const pending=button.onclick();
assert.equal(app.calls.length,1);
resolveResponse({state:{location:'Before',scene_memory:{events:[]}},removed:true});
await pending;
assert.equal(confirmations.length,2);
assert.equal(campaign.state.scene_memory.events.length,0);
""")

    def test_pending_removal_blocks_duplicate_clicks_and_story_submissions(self):
        self.run_js(r"""
const button=memoryButton({kind:'events',index:0,text:'A selected event.',name:''});
const pending=button.onclick();
await button.onclick();
get('action').value='I wait at the gate.';await app.sendAction();
assert.equal(app.calls.length,1);assert.equal(confirmations.length,1);
assert.equal(get('action').value,'I wait at the gate.');
resolveResponse({state:{location:'Before',scene_memory:{events:[]}},removed:true});await pending;
assert.equal(app.state.busy,false);assert.equal(button.disabled,false);
assert.equal(get('send-action').disabled,false);
assert.equal(get('action').value,'I wait at the gate.');
""")

    def test_failure_preserves_memory_and_allows_a_fresh_retry(self):
        self.run_js(r"""
const campaign=app.state.active;
campaign.state={location:'Before',scene_memory:{events:['A selected event.']}};
const original=campaign.state, messages=app.state.messages;
const button=memoryButton({kind:'events',index:0,text:'A selected event.',name:''});
const pending=button.onclick();
rejectResponse(new Error('Scene memory changed. Refresh and try again.'));await pending;
assert.equal(campaign.state,original);assert.equal(app.state.messages,messages);
assert.equal(app.painted.length,0);assert.equal(memoryUi.memoryRepaints.length,0);
assert.equal(app.state.busy,false);assert.equal(button.disabled,false);
assert.equal(get('send-action').disabled,false);
assert.ok(app.notices.some(notice=>notice.fail&&notice.text.includes('Scene memory changed')));
context.responsePromise=Promise.resolve({state:{location:'Before',scene_memory:{events:[]}},removed:true});
await button.onclick();
assert.equal(app.calls.length,2);assert.equal(campaign.state.scene_memory.events.length,0);
""")

    def test_finishing_after_the_button_is_detached_restores_request_controls(self):
        self.run_js(r"""
const button=memoryButton({kind:'events',index:0,text:'A selected event.',name:''});
const pending=button.onclick();
nodes.delete(button.id);
resolveResponse({state:{location:'Before',scene_memory:{events:[]}},removed:true});await pending;
assert.equal(app.state.active.state.scene_memory.events.length,0);
assert.equal(app.state.busy,false);assert.equal(get('send-action').disabled,false);
assert.equal(app.calls.length,1);
""")


if __name__ == '__main__':
    unittest.main()
