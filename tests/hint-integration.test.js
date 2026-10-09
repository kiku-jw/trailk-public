import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const file=fileURLToPath(import.meta.url),web=path.resolve(path.dirname(file),'../assets/web');
if(process.argv.includes('--probe')){
 let now=0,tick;const nodes=new Map(),listeners=new Map(),calls=[];
 const get=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',dataset:{},checked:true,children:[],addEventListener(){},querySelectorAll(){return[]},replaceChildren(){},getBoundingClientRect(){return{top:0}},contains(){return false}});return nodes.get(id)};
 const state={session_id:'synthetic-run',native_session:{approval_id:'synthetic-approval'},text_ready:true,text_context_allowed:true,running:true,settings:{auto_suggestions:true},capture:{activity:'pause'}};
 const document={getElementById:get,querySelectorAll:()=>[],activeElement:null};
 const window={calmMode:'live',calmLiveState:state,calmMark(){},calmFocusStale(){},addEventListener:(name,fn)=>listeners.set(name,fn)};
 const fetch=async (url,options={})=>{
  calls.push({url,body:options.body?JSON.parse(options.body):null,signal:options.signal});
  if(url==='/api/text')return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true}));
  return {ok:true,json:async()=>url==='/api/token'?{token:'DUMMY-TOKEN'}:url==='/api/personal-context'?{text:''}:state};
 };
 const context=vm.createContext({window,document,performance:{now:()=>now},fetch,setInterval:fn=>{tick=fn},setTimeout(){},Event:class{},AbortController,DOMException});
 const modules=new Map();async function load(filename){if(modules.has(filename))return modules.get(filename);const module=new vm.SourceTextModule(fs.readFileSync(filename,'utf8'),{context,identifier:filename});modules.set(filename,module);await module.link(spec=>load(path.resolve(spec.startsWith('/')?web:path.dirname(filename),spec.startsWith('/')?spec.slice(1):spec)));return module}
 await(await load(path.join(web,'integration.js'))).evaluate();tick();
 listeners.get('conversation-text')({detail:{synthetic:false,text:'Цена 3.5, не 35. '}});now=750;tick();await new Promise(r=>setImmediate(r));
 const paid=calls.find(call=>call.url==='/api/text');assert(paid);assert.equal(paid.body.hint_session,'synthetic-run');assert(Number.isSafeInteger(paid.body.hint_generation));
 listeners.get('conversation-text')({detail:{synthetic:false,text:'Нет, не в четверг, а в пятницу. '}});assert.equal(paid.signal.aborted,true);await new Promise(r=>setImmediate(r));
 const cancel=calls.find(call=>call.url==='/api/text/cancel');assert(cancel);assert.deepEqual(cancel.body,{hint_generation:paid.body.hint_generation,hint_session:'synthetic-run'});assert.equal(cancel.signal,undefined);
 listeners.get('session-stop')();now=3000;window.calmUserStopped=true;tick();await new Promise(r=>setImmediate(r));
 console.log(JSON.stringify({requests:calls.filter(call=>call.url==='/api/text').length,context:window.calmConversationContext(),cancel_keys:Object.keys(cancel.body),latency:window.calmLatencySummary().requestToRender.samples}));
}else test('actual automatic-hint integration aborts obsolete transport and sends metadata-only cancellation',()=>{
 const result=JSON.parse(execFileSync(process.execPath,['--experimental-vm-modules',file,'--probe'],{encoding:'utf8',stdio:['ignore','pipe','inherit']}));assert.equal(result.requests,1);assert(result.context.includes('Цена 3.5, не 35.'));assert(result.context.includes('не в четверг'));assert.equal(result.latency,0);assert.deepEqual(result.cancel_keys,['hint_generation','hint_session']);
});
