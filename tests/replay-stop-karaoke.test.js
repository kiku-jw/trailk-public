import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const file=fileURLToPath(import.meta.url),web=path.resolve(path.dirname(file),'../assets/web');
if(process.argv.includes('--probe')){
 let now=0,serial=0,stopEvents=0;const nodes=new Map(),timers=new Map(),listeners=new Map(),calls=[];
 class Node{
  constructor(text=''){this.textContent=text;this.value='';this.children=[];this.dataset={};this.checked=false;this.disabled=false;this.attributes=new Map();this.listeners=new Map();this.classes=new Set();this.classList={toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name)};this.scrollTop=0;this.scrollHeight=0;this.clientHeight=400}
  append(...children){this.children.push(...children)}replaceChildren(){this.children=[]}remove(){}contains(){return false}
  setAttribute(name,value){this.attributes.set(name,value)}getAttribute(name){return this.attributes.get(name)}
  addEventListener(name,callback){const group=this.listeners.get(name)||[];group.push(callback);this.listeners.set(name,group)}
  dispatchEvent(event){for(const callback of this.listeners.get(event.type)||[])callback(event)}
  click(){if(!this.disabled)return this.onclick?.()}getBoundingClientRect(){return{left:0,width:880,top:0,bottom:400}}
  querySelector(){return new Node()}querySelectorAll(){return[]}
 }
 const get=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id)};get('font').value='26';get('theme').value='dark';
 const document={getElementById:get,createTextNode:text=>new Node(text),createElement:()=>new Node(),addEventListener(){},querySelector:()=>get('camera-focus'),querySelectorAll:()=>[],activeElement:null,hidden:false,documentElement:{dataset:{},style:{setProperty(){}}}};
 const window={calmPreferences:{uiVersion:2,mode:'replay'},addEventListener:(name,fn)=>{const group=listeners.get(name)||[];group.push(fn);listeners.set(name,group)},dispatchEvent:event=>{if(event.type==='session-stop')stopEvents++;for(const callback of listeners.get(event.type)||[])callback(event)}};
 const fetch=async (url,options={})=>{calls.push({url,method:options.method||'GET'});if(url==='/replay.json')return{ok:true,json:async()=>({events:[{kind:'delta',text:'Synthetic question? '},{kind:'end'}]})};if(url.startsWith('/api/state?'))return{ok:true,json:async()=>({instance_id:'synthetic-backend',running:false,events:[],settings:{},configured:false})};throw Error('Unexpected request in offline replay')};
 class Event{constructor(type){this.type=type}}
 const context=vm.createContext({window,document,performance:{now:()=>now},fetch,Event,CustomEvent:class extends Event{constructor(type,options){super(type);this.detail=options.detail}},innerWidth:1200,getComputedStyle:()=>({getPropertyValue:()=>0}),setTimeout(){},setInterval:(fn,ms)=>{const id=++serial;timers.set(id,{fn,ms});return id},clearInterval:id=>timers.delete(id)});
 const modules=new Map();async function load(filename){if(modules.has(filename))return modules.get(filename);const module=new vm.SourceTextModule(fs.readFileSync(filename,'utf8'),{context,identifier:filename});modules.set(filename,module);await module.link(spec=>load(path.resolve(spec.startsWith('/')?web:path.dirname(filename),spec.startsWith('/')?spec.slice(1):spec)));return module}
 await(await load(path.join(web,'app.js'))).evaluate();await new Promise(r=>setImmediate(r));
 assert.equal(window.calmMode,'replay');assert.equal(get('session').disabled,false);get('session').click();assert.equal(get('session').textContent,'Остановить');assert([...timers.values()].some(timer=>timer.ms===35));
 const selected='Do NOT send 35.';get('english').value=selected;window.calmSelectedReply({en:selected,ru:'Не отправляйте 35.'});get('karaoke-play').click();const [timerId,timer]=[...timers].find(([,value])=>value.ms===50);now=334;timer.fn();assert.equal(get('karaoke-position').textContent,'2 / 4');
 now=400;get('session').click();assert.equal(get('session').textContent,'Начать пример');assert.equal(timers.has(timerId),false,'Replay Stop must stop the actual karaoke timer');assert.equal(stopEvents,1);assert(![...timers.values()].some(value=>value.ms===35));
 const position=get('karaoke-position').textContent;now=10000;timer.fn();assert.equal(get('karaoke-position').textContent,position);assert.equal(position,'На паузе · 2 / 4');assert.equal(get('english').value,selected);assert.equal(calls.filter(call=>call.method==='POST').length,0);
 console.log(JSON.stringify({position,stopEvents,postCalls:0}));
}else test('actual session-button Stop in replay stops karaoke without changing selected text or calling a provider',()=>{
 const result=JSON.parse(execFileSync(process.execPath,['--experimental-vm-modules',file,'--probe'],{encoding:'utf8',stdio:['ignore','pipe','inherit']}));assert.equal(result.stopEvents,1);assert.equal(result.postCalls,0);assert.equal(result.position,'На паузе · 2 / 4');
});
