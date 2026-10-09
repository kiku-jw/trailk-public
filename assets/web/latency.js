// Bounded, numeric metadata in RAM. No transcript/response text is accepted.
export class LatencyWindow {
 constructor(limit=128){this.limit=limit;this.changed=new Map();this.dispatches=new Map();this.values={segmentToDispatch:[],requestToResponse:[],requestToRender:[]};}
 clear(){this.changed.clear();this.dispatches.clear();for(const values of Object.values(this.values))values.length=0;}
 add(kind,value){if(!Number.isFinite(value)||value<0)return;const values=this.values[kind];values.push(value);if(values.length>this.limit)values.shift();}
 mark(stage,detail={},now=performance.now()){
  const revision=detail.revision;if(!Number.isInteger(revision))return;
  if(stage==='context_updated'&&Number.isFinite(detail.changed_at_ms)){this.changed.set(revision,detail.changed_at_ms);if(this.changed.size>this.limit)this.changed.delete(this.changed.keys().next().value);}
  if(stage==='dispatch'){this.dispatches.set(revision,now);if(this.dispatches.size>this.limit)this.dispatches.delete(this.dispatches.keys().next().value);if(this.changed.has(revision))this.add('segmentToDispatch',now-this.changed.get(revision));}
  if(stage==='response'&&this.dispatches.has(revision))this.add('requestToResponse',now-this.dispatches.get(revision));
  if(stage==='render_accepted'&&this.dispatches.has(revision)){this.add('requestToRender',now-this.dispatches.get(revision));this.dispatches.delete(revision);}
  if(stage==='discard'||stage==='request_rejected')this.dispatches.delete(revision);
 }
 snapshot(){const result={};for(const [kind,values] of Object.entries(this.values)){const sorted=[...values].sort((a,b)=>a-b);result[kind]={samples:sorted.length,p50:sorted.length?sorted[Math.ceil(.5*sorted.length)-1]:null,p95:sorted.length?sorted[Math.ceil(.95*sorted.length)-1]:null};}return result;}
}
