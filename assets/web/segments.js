// Append-only punctuation boundary. A terminal digit-period is ambiguous until
// more input or a confirmed quiet/boundary flush; decimals remain one thought.
export function sentencePrefix(text){
 for(let i=0;i<text.length;i++){
  const c=text[i];if(!'.!?'.includes(c))continue;
  if(c==='.'&&/\d/.test(text[i-1]||'')&&(i===text.length-1||/\d/.test(text[i+1])))continue;
  // A closing quote/bracket belongs to the completed sentence. In particular,
  // provider delta '?»' must not turn a finished question into a quiet fragment.
  let end=i+1;while(end<text.length&&/[»”"')\]}]/.test(text[end]))end++;
  if(end<text.length&&!/\s/.test(text[end]))continue;
  return text.slice(0,end+(end<text.length?1:0));
 }return null;
}
