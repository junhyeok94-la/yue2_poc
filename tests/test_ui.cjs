const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require(require.resolve('jsdom',{paths:[process.env.MUSIC_STUDIO_TEST_DEPS||path.join(__dirname,'../outputs/ui-test')]}));
const base='http://127.0.0.1:7860';
async function until(fn){for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw new Error('UI condition timed out');}
async function setup(draft){
 const dom=new JSDOM(fs.readFileSync(path.join(__dirname,'../ui/index.html'),'utf8'),{url:base,runScripts:'outside-only'});
 const w=dom.window;const jobs=[];w.confirm=()=>true;w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 w.fetch=async(p,options)=>{if(p==='/api/jobs'){jobs.push(JSON.parse(options.body));return {ok:true,json:async()=>({id:'test'})};}const response=await fetch(new URL(p,base),options);if(p==='/api/state'){const state=await response.json();return {ok:true,json:async()=>({...state,job:null,busy:false})};}return response;};
 if(draft)w.localStorage.setItem('music-studio-draft',JSON.stringify(draft));
 w.eval(fs.readFileSync(path.join(__dirname,'../ui/song-editor.js'),'utf8'));
 w.eval(fs.readFileSync(path.join(__dirname,'../ui/app.js'),'utf8'));
 try {await until(()=>!w.document.getElementById('add-section').disabled);
 await until(()=>w.document.getElementById('connection').textContent==='로컬 스튜디오 연결됨');
 return {dom,w,d:w.document,jobs};}catch(e){dom.window.close();throw e;}
}
function input(w,el,value){el.value=value;el.dispatchEvent(new w.Event('input',{bubbles:true}));}
test('structure editing, Korean composition, guide, delete undo, compile and submit',async()=>{
 const {dom,w,d,jobs}=await setup();
 try{
  d.getElementById('add-section').click();
  let area=d.querySelector('#section-cards textarea');area.focus();
  area.dispatchEvent(new w.Event('compositionstart',{bubbles:true}));
  input(w,area,'새벽의 노래\n우리 함께');
  area.dispatchEvent(new w.Event('compositionend',{bubbles:true}));
  await until(()=>d.querySelector('.analysis-summary').textContent.includes('2행'));
  assert.equal(d.activeElement,area);assert.equal(d.querySelector('#section-cards textarea'),area);
  d.querySelector('.guide-option button').click();
  assert.equal(d.querySelector('input[aria-label="1번 Section 마디 수"]').value,'8');
  d.getElementById('new-section-type').value='chorus';d.getElementById('add-section').click();
  input(w,d.querySelector('textarea[aria-label="2번 Section 가사"]'),'다시 만나요');
  d.querySelector('button[aria-label="2번 Section ↑ 위로"]').click();
  assert.equal(d.querySelector('#section-cards textarea').value,'다시 만나요');
  d.querySelector('button[aria-label="1번 Section 삭제"]').click();
  assert.equal(d.querySelectorAll('.song-section').length,1);
  d.getElementById('undo-section').click();assert.equal(d.querySelectorAll('.song-section').length,2);
  await until(()=>d.getElementById('compiled-preview').textContent.startsWith('[Chorus]'));
  const draft=JSON.parse(w.localStorage.getItem('music-studio-draft-v3'));
  assert.equal(draft.editor.sections[0].type,'chorus');
  d.getElementById('composer').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await until(()=>jobs.length===1);
  assert.ok(jobs[0].song);assert.equal(jobs[0].lyrics,undefined);
  assert.equal(jobs[0].song.sections[1].bars,8);
 }finally{dom.window.close();}
});
test('legacy draft preserved; import applies only after explicit confirmation',async()=>{
 const legacy={title:'기존 곡',style:'Korean R&B',lyrics:'[Verse]\n한글\n\n[Special]\n원문',seed:7,steps:8,timeout:1800,cot:'off'};
 const {dom,w,d}=await setup(legacy);
 try{
  assert.equal(d.getElementById('raw-lyrics').hidden,false);
  assert.equal(d.getElementById('lyrics').value,legacy.lyrics);
  d.getElementById('section-mode').click();
  await until(()=>d.getElementById('import-dialog').open);
  assert.equal(d.getElementById('raw-lyrics').hidden,false);
  d.getElementById('cancel-import').click();
  assert.equal(d.getElementById('lyrics').value,legacy.lyrics);
  d.getElementById('section-mode').click();await until(()=>d.getElementById('import-dialog').open);
  d.getElementById('apply-import').click();
  assert.equal(d.getElementById('raw-lyrics').hidden,true);
  assert.equal(d.querySelectorAll('.song-section').length,2);
  assert.ok(d.querySelectorAll('.song-section textarea')[1].value.includes('[Special]'));
  assert.equal(JSON.parse(w.localStorage.getItem('music-studio-draft')).lyrics,legacy.lyrics);
 }finally{dom.window.close();}
});
