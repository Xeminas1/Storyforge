"""Execute the story request controls with Node's built-in VM and a small DOM fake."""
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
class Element {
  constructor(id='') {
    this.id=id;this.value='';this.textContent='';this.disabled=false;this.checked=false;
    this.children=[];this.ids=[];this.classes=new Set();
    this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),contains:x=>this.classes.has(x),toggle:()=>{}};
  }
  set innerHTML(value) {
    for(const id of this.ids)nodes.delete(id);
    this.ids=[...value.matchAll(/id="([^"]+)"/g)].map(match=>match[1]);
    for(const id of this.ids)nodes.set(id,new Element(id));
  }
  appendChild(node){this.children.push(node);}
  remove(){this.removed=true;}
  scrollIntoView(){}
  focus(){}
}
for(const id of ['action','send-action','story-feed','model','autoplay','modal','modal-content','modal-title','modal-eyebrow','adventure','library','nav-worlds','nav-story','campaign-links','breadcrumb','story-world','story-title','app-shell','details'])nodes.set(id,new Element(id));
const document={getElementById:id=>nodes.get(id)||null,createElement:()=>new Element(),contains:node=>nodes.get(node.id)===node,querySelectorAll:()=>[],querySelector:selector=>nodes.get(selector.slice(1))};
const context=vm.createContext({document,window:{requestAnimationFrame:fn=>fn()},console,setTimeout,clearTimeout});
const source=fs.readFileSync('static/app.js','utf8');
// Load the actual application functions without starting its page bootstrap/network polls.
const bootstrap=source.indexOf('\nrefreshUpdateIndicator();');
assert.ok(bootstrap>0);
vm.runInContext(source.slice(0,bootstrap),context);
vm.runInContext(`
  var calls=[],notices=[],painted=[],spoken=[];
  request=async(url,options)=>{calls.push({url,options});return responsePromise;};
  toast=(text,fail)=>notices.push({text,fail});
  renderMessages=()=>painted.push('messages');
  updateState=()=>painted.push('state');
  refreshLibrary=async()=>{};
  stopArtPolling=()=>{};closeCodex=()=>{};
  renderCharacter=()=>{};renderWorldDetails=()=>{};setDetailTab=()=>{};
  stopSpeech=()=>{};
  speak=text=>spoken.push(text);
  state.active={id:'first',state:{location:'Before'}};
  state.messages=[{id:1,role:'player',content:'I wait.'},{id:2,role:'gm',content:'A guard watches.',has_checkpoint:true}];
`,context);
const app=vm.runInContext('({state,sendAction,openStoryMessageAction,showModal,closeModal,openCampaign,toLibrary,calls,notices,painted,spoken})',context);
const get=id=>document.getElementById(id);
let resolveResponse,rejectResponse;
context.responsePromise=new Promise((resolve,reject)=>{resolveResponse=resolve;rejectResponse=reject;});
const result={messages:[{id:3,role:'gm',content:'A bell rings.'}],state:{location:'After'},narration:'A bell rings.'};
"""


@unittest.skipUnless(NODE, 'Node is required for browser request behavior checks')
class StoryRequestUiTests(unittest.TestCase):
    def run_js(self, script):
        completed = subprocess.run(
            [NODE, '-e', HARNESS + '\n(async()=>{\n' + script + '\n})().then(()=>console.log("UI_TEST_COMPLETE")).catch(error=>{console.error(error);process.exitCode=1;});'],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('UI_TEST_COMPLETE', completed.stdout, 'The asynchronous behavior check did not finish')

    def test_failed_send_preserves_newly_edited_draft_and_existing_story(self):
        self.run_js(r"""
get('action').value='I wait.';
const original=app.state.messages, campaign=app.state.active;
const pending=app.sendAction();
get('action').value='I ask the guard about the bell.';
rejectResponse(new Error('Ollama is unavailable'));
await pending;
assert.equal(get('action').value,'I ask the guard about the bell.');
assert.equal(app.state.messages,original);
assert.equal(campaign.state.location,'Before');
assert.equal(app.state.busy,false);
assert.equal(get('send-action').disabled,false);
""")

    def test_success_clears_only_the_unchanged_submitted_draft(self):
        self.run_js(r"""
get('action').value='  I wait.  ';
const pending=app.sendAction();
assert.equal(get('action').value,'  I wait.  ');
resolveResponse(result);await pending;
assert.equal(app.calls[0].options.body.action,'I wait.');
assert.equal(get('action').value,'');
assert.equal(app.state.messages,result.messages);
""")

    def test_success_retains_a_new_draft_written_while_waiting(self):
        self.run_js(r"""
get('action').value='I wait.';
const pending=app.sendAction();
get('action').value='I examine the gate.';
resolveResponse(result);await pending;
assert.equal(get('action').value,'I examine the gate.');
""")

    def test_send_result_cannot_replace_another_campaign(self):
        self.run_js(r"""
get('action').value='I wait.';get('autoplay').checked=true;
const pending=app.sendAction();
const next={id:'second',state:{location:'Other town'}};
const messages=[{id:99,role:'gm',content:'A different story.'}];
app.state.active=next;app.state.messages=messages;
get('action').value='I visit the second town.';
resolveResponse(result);await pending;
assert.equal(app.calls[0].url,'/api/campaigns/first/turn');
assert.equal(app.state.messages,messages);
assert.equal(next.state.location,'Other town');
assert.equal(get('action').value,'I visit the second town.');
assert.equal(app.painted.length,0);assert.equal(app.spoken.length,0);
""")

    def test_feedback_confirmation_cannot_target_a_different_campaign(self):
        self.run_js(r"""
app.openStoryMessageAction(2,'retry');
app.state.active={id:'second',state:{location:'Other town'}};
const pending=get('confirm-story-correction').onclick();
assert.equal(app.calls.length,0);
resolveResponse(result);await pending;
assert.equal(app.state.active.state.location,'Other town');
assert.equal(app.state.busy,false);
""")

    def test_duplicate_send_and_feedback_requests_are_blocked(self):
        self.run_js(r"""
app.openStoryMessageAction(2,'retry');
get('story-correction-reason').value='Do not speak for my character.';
const confirm=get('confirm-story-correction').onclick;
const pending=confirm();
await confirm();get('action').value='I wait.';await app.sendAction();
assert.equal(app.calls.length,1);
rejectResponse(new Error('Generation failed'));await pending;
assert.equal(app.state.messages[1].content,'A guard watches.');
assert.equal(get('story-correction-reason').value,'Do not speak for my character.');
assert.equal(get('confirm-story-correction').disabled,false);
""")

    def test_pending_feedback_cannot_be_mistaken_for_a_cancelled_request(self):
        self.run_js(r"""
app.openStoryMessageAction(2,'retry');
const pending=get('confirm-story-correction').onclick();
assert.equal(get('cancel-story-correction').disabled,true);
app.closeModal();
assert.equal(get('modal').classList.contains('hidden'),false);
rejectResponse(new Error('Generation failed'));await pending;
app.closeModal();
assert.equal(get('modal').classList.contains('hidden'),true);
""")

    def test_feedback_failure_does_not_crash_after_modal_is_replaced(self):
        self.run_js(r"""
app.openStoryMessageAction(2,'retry');
const pending=get('confirm-story-correction').onclick();
app.showModal('OTHER','Other settings','<p id="other-content">Settings</p>');
rejectResponse(new Error('Generation failed'));await pending;
assert.equal(app.state.busy,false);
assert.equal(get('modal-title').textContent,'Other settings');
assert.ok(app.notices.some(notice=>notice.text==='Generation failed'));
""")

    def test_feedback_success_cannot_replace_another_campaign_or_modal(self):
        self.run_js(r"""
app.openStoryMessageAction(2,'retry');get('autoplay').checked=true;
const pending=get('confirm-story-correction').onclick();
const messages=[{id:99,role:'gm',content:'Another story.'}];
app.state.active={id:'second',state:{location:'Other town'}};app.state.messages=messages;
app.showModal('OTHER','Other settings','<p id="other-content">Settings</p>');
resolveResponse(result);await pending;
assert.equal(app.state.messages,messages);
assert.equal(app.state.active.state.location,'Other town');
assert.equal(get('modal').classList.contains('hidden'),false);
assert.equal(get('modal-title').textContent,'Other settings');
assert.equal(app.spoken.length,0);
""")

    def test_slower_campaign_load_cannot_replace_a_more_recent_selection(self):
        self.run_js(r"""
let finishFirst;
const first=new Promise(resolve=>{finishFirst=resolve;});
context.lookup=async url=>{
  if(url==='/api/campaigns/slow')await first;
  if(url.endsWith('/messages'))return {messages:[]};
  if(url.startsWith('/api/worlds/'))return {world:{title:'World'}};
  const id=url.split('/').at(-1);
  return {campaign:{id,world_id:id,title:id,state:{}}};
};
vm.runInContext('request=lookup',context);
const slow=app.openCampaign('slow');
await app.openCampaign('recent');
finishFirst();await slow;
assert.equal(app.state.active.id,'recent');
assert.equal(get('story-title').textContent,'recent');
""")

    def test_returning_home_during_campaign_load_keeps_home_visible(self):
        self.run_js(r"""
context.lookup=async url=>{
  if(url==='/api/campaigns/next')await context.responsePromise;
  if(url.endsWith('/messages'))return {messages:[]};
  if(url.startsWith('/api/worlds/'))return {world:{title:'World'}};
  return {campaign:{id:'next',world_id:'world',title:'Next',state:{}}};
};
vm.runInContext('request=lookup',context);
const pending=app.openCampaign('next');
app.toLibrary();resolveResponse(result);await pending;
assert.equal(app.state.active.id,'first');
assert.equal(get('adventure').classList.contains('hidden'),true);
assert.equal(get('library').classList.contains('hidden'),false);
""")


if __name__ == '__main__':
    unittest.main()
