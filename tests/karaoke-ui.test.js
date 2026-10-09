import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const file=fileURLToPath(import.meta.url),web=path.resolve(path.dirname(file),'../assets/web');
if(process.argv.includes('--probe')){
 let now=0,interval=null,cleared=0;const nodes=new Map(),events=new Map(),documentEvents=new Map();
 class Node{
  constructor(text=''){this.textContent=text;this.children=[];this.value='';this.listeners=new Map();this.classes=new Set();this.classList={toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name)}}
  append(...children){this.children.push(...children)}replaceChildren(){this.children=[]}addEventListener(name,callback){this.listeners.set(name,callback)}click(){this.onclick?.()}
 }
 const get=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id)};
 const document={getElementById:get,createTextNode:text=>new Node(text),createElement:()=>new Node(),addEventListener:(name,fn)=>documentEvents.set(name,fn),hidden:false};
 const window={addEventListener:(name,fn)=>events.set(name,fn)};
 const context=vm.createContext({window,document,performance:{now:()=>now},setInterval:fn=>{interval=fn;return 1},clearInterval:()=>{interval=null;cleared++}});
 const modules=new Map();async function load(filename){if(modules.has(filename))return modules.get(filename);const module=new vm.SourceTextModule(fs.readFileSync(filename,'utf8'),{context,identifier:filename});modules.set(filename,module);await module.link(spec=>load(path.resolve(path.dirname(filename),spec)));return module}
 await(await load(path.join(web,'karaoke.js'))).evaluate();assert.equal(get('karaoke').hidden,true);
 const selected='I do NOT agree.\nThe price is 3.5, not 35.';get('english').value=selected;events.get('selected-reply')();
 const exact=get('karaoke-text').children.map(node=>node.textContent).join('');assert.equal(exact,selected);assert.equal(interval,null);
 get('karaoke-play').click();const oldTimer=interval;now=334;oldTimer();assert.equal(get('karaoke-position').textContent,'2 / 10');
 events.get('session-stop')();now=10000;oldTimer();assert.equal(get('karaoke-position').textContent,'На паузе · 2 / 10');assert.equal(interval,null);
 get('karaoke-play').click();document.hidden=true;documentEvents.get('visibilitychange')();assert.equal(interval,null);document.hidden=false;documentEvents.get('visibilitychange')();assert.equal(interval,null);
 get('english').value='Do not send 35.';get('english').listeners.get('input')();assert.equal(get('karaoke-position').textContent,'1 / 4');assert.equal(get('karaoke-text').children.map(node=>node.textContent).join(''),'Do not send 35.');
 console.log(JSON.stringify({exact,cleared,position:get('karaoke-position').textContent,network_calls:0}));
}else test('actual karaoke DOM keeps selected text, pauses on Stop/hide, and does not resume itself',()=>{
 const result=JSON.parse(execFileSync(process.execPath,['--experimental-vm-modules',file,'--probe'],{encoding:'utf8',stdio:['ignore','pipe','inherit']}));assert.equal(result.position,'1 / 4');assert(result.cleared>=2);assert.equal(result.network_calls,0);
});
