const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require(require.resolve('jsdom',{paths:[process.env.MUSIC_STUDIO_TEST_DEPS||path.join(__dirname,'../outputs/ui-test')]}));
const base='http://127.0.0.1:7860';
async function until(fn){for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw new Error('UI condition timed out');}
async function setup(draft,advisor,library,musicAdvisor,workspace){
 const dom=new JSDOM(fs.readFileSync(path.join(__dirname,'../ui/index.html'),'utf8'),{url:base,runScripts:'outside-only'});
 const w=dom.window;const jobs=[];w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.load=function(){};w.HTMLMediaElement.prototype.play=()=>Promise.resolve();w.confirm=()=>true;w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 w.fetch=async(p,options)=>{
 if(musicAdvisor&&p==='/api/music/advice')return {ok:true,json:async()=>musicAdvisor(JSON.parse(options.body))};
 if(library&&p.startsWith('/api/score?id='))return {ok:true,json:async()=>({abc:'X:1\nM:4/4\nQ:1/4=90\nK:C\nC D E F |',source:'generated'})};
 if(library&&p.startsWith('/api/versions/compare?'))return {ok:true,json:async()=>({changes:[{label:'가사',before:'원본 가사',after:'수정 가사'}]})};
 if(library&&p==='/api/state')return {ok:true,json:async()=>({tracks:library.filter(t=>!t.deleted),trash:library.filter(t=>t.deleted),ready:true,busy:false,job:null})};
 if(library&&p.startsWith('/api/tracks/')){
   const data=JSON.parse(options.body),track=library.find(t=>t.id===data.id);
   if(p.endsWith('/rename'))track.title=data.title;
   else{track.deleted=p.endsWith('/delete');track.has_audio=!track.deleted;}
   return {ok:true,json:async()=>JSON.parse(JSON.stringify(track))};
 }
if(advisor&&p==='/api/advisor'){return {ok:true,json:async()=>options?.body?advisor(JSON.parse(options.body)):{configured:true,model:'test'}};}if(p==='/api/jobs'){jobs.push(JSON.parse(options.body));return {ok:true,json:async()=>({id:'test'})};}const response=await fetch(new URL(p,base),options);if(p==='/api/state'){const state=await response.json();return {ok:true,json:async()=>({...state,job:null,busy:false})};}return response;};
 if(workspace)w.localStorage.setItem('music-studio-workspace-v8',workspace);
 if(draft)w.localStorage.setItem('music-studio-draft',JSON.stringify(draft));
 w.eval(fs.readFileSync(path.join(__dirname,'../ui/song-editor.js'),'utf8'));
 w.eval(fs.readFileSync(path.join(__dirname,'../ui/music-guide.js'),'utf8'));
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

test('AI suggestions require apply; ignore and stale replies preserve lyrics',async()=>{
 let release;
 const advisor=async payload=>{
   if(release==='delay')await new Promise(resolve=>{release=resolve;});
   const line=payload.section.lyrics[0]||'';
   return {suggestions:[{id:'test-suggestion',section_id:payload.section.id,line_index:payload.action==='suggest'?payload.section.lyrics.length:0,
     original:payload.action==='suggest'?'':line,suggested:payload.action==='suggest'?'새로운 첫 줄\n새로운 둘째 줄':'고요한 이 밤',reason:'표현 제안',source_revision:'test'}]};
 };
 const {dom,w,d}=await setup(undefined,advisor);
 try{
   d.getElementById('add-section').click();
   await until(()=>!d.querySelector('.ai-request').disabled);
   input(w,d.querySelector('#section-cards textarea'),'조용한 밤');
   const clickReview=()=>d.querySelector('[data-action="review"]').click();
   clickReview();await until(()=>d.querySelector('.suggestion'));
   assert.equal(d.querySelector('#section-cards textarea').value,'조용한 밤');
   d.querySelector('.suggestion button:last-child').click();
   assert.equal(d.querySelector('.suggestion'),null);
   clickReview();await until(()=>d.querySelector('.suggestion'));
   input(w,d.querySelector('#section-cards textarea'),'사용자 직접 수정');
   assert.equal(d.querySelector('.suggestion button').disabled,true);
   assert.equal(d.querySelector('#section-cards textarea').value,'사용자 직접 수정');
   clickReview();await until(()=>d.querySelector('.suggestion button:not(:disabled)'));
   d.querySelector('.suggestion button').click();
   assert.equal(d.querySelector('#section-cards textarea').value,'고요한 이 밤');
   d.querySelector('[data-action="suggest"]').click();await until(()=>d.querySelector('.suggestion'));
   d.querySelector('.suggestion button').click();
   assert.equal(d.querySelector('#section-cards textarea').value,'고요한 이 밤\n새로운 첫 줄\n새로운 둘째 줄');
   release='delay';clickReview();await until(()=>typeof release==='function');
   input(w,d.querySelector('#section-cards textarea'),'응답 전에 편집');
   release();await until(()=>d.querySelector('.suggestion'));
   assert.equal(d.querySelector('.suggestion button').disabled,true);
   assert.equal(d.querySelector('#section-cards textarea').value,'응답 전에 편집');
 }finally{dom.window.close();}
});

for(const [action,label] of [['rhyme','라임'],['hook','Hook 강화']]){
 test(action+' request shows type, applies only selected line and blocks stale results',async()=>{
   const calls=[];
   const advisor=async payload=>{
     calls.push(payload);
     return {suggestions:[{id:action+'-id',type:action,section_id:payload.section.id,line_index:0,
       original:payload.section.lyrics[0],suggested:'기억에 남을 밤',reason:'원문의 감정을 살린 '+label+' 제안',source_revision:'test'}]};
   };
   const {dom,w,d}=await setup(undefined,advisor);
   try{
     d.getElementById('add-section').click();
     await until(()=>!d.querySelector('.ai-request').disabled);
     input(w,d.querySelector('#section-cards textarea'),'조용한 밤\n두 번째 행');
     const request=()=>d.querySelector('[data-action="'+action+'"]').click();
     request();await until(()=>d.querySelector('.suggestion'));
     assert.equal(calls[0].action,action);
     assert.equal(d.querySelector('.suggestion .mini-label').textContent,label);
     assert.equal(d.querySelector('#section-cards textarea').value,'조용한 밤\n두 번째 행');
     d.querySelector('.suggestion button:last-child').click();
     assert.equal(d.querySelector('.suggestion'),null);
     request();await until(()=>d.querySelector('.suggestion'));
     d.querySelector('.suggestion button').click();
     assert.equal(d.querySelector('#section-cards textarea').value,'기억에 남을 밤\n두 번째 행');
     request();await until(()=>d.querySelector('.suggestion'));
     input(w,d.querySelector('#section-cards textarea'),'직접 수정\n두 번째 행');
     assert.equal(d.querySelector('.suggestion button').disabled,true);
     assert.equal(d.querySelector('#section-cards textarea').value,'직접 수정\n두 번째 행');
   }finally{dom.window.close();}
 });
}

for(const action of ['review','rhyme','hook']){
 test(action+' applies in place and keeps independent suggestions usable',async()=>{
   const advisor=async payload=>({suggestions:[
     {id:'second',type:action==='review'?'expression':action,line_index:1,original:payload.section.lyrics[1],suggested:'두 번째 행 수정',reason:'두 번째 행 제안'},
     {id:'first',type:action==='review'?'expression':action,line_index:0,original:payload.section.lyrics[0],suggested:'첫 번째 행 수정',reason:'첫 번째 행 제안'},
     {id:'alternative',type:action==='review'?'expression':action,line_index:0,original:payload.section.lyrics[0],suggested:'첫 번째 행 다른 대안',reason:'동일 행 대안'}
   ]});
   const {dom,w,d,jobs}=await setup(undefined,advisor);
   try{
     d.getElementById('add-section').click();
     await until(()=>!d.querySelector('.ai-request').disabled);
     const area=d.querySelector('#section-cards textarea');
     input(w,area,'같은 원문\n같은 원문\n유지할 행');
     d.querySelector('[data-action="'+action+'"]').click();
     await until(()=>d.querySelectorAll('.suggestion').length===3);
     d.querySelector('.suggestion button').click();
     assert.equal(area.value,'같은 원문\n두 번째 행 수정\n유지할 행');
     assert.equal(d.querySelector('#section-cards textarea'),area);
     assert.equal(d.querySelector('.suggestion button').disabled,false);
     d.querySelector('.suggestion button').click();
     assert.equal(area.value,'첫 번째 행 수정\n두 번째 행 수정\n유지할 행');
     assert.equal(d.querySelector('.suggestion button').disabled,true);
     const draft=JSON.parse(w.localStorage.getItem('music-studio-draft-v3'));
     assert.deepEqual(draft.editor.sections[0].lyrics,['첫 번째 행 수정','두 번째 행 수정','유지할 행']);
     await until(()=>d.getElementById('compiled-preview').textContent.includes('첫 번째 행 수정\n두 번째 행 수정'));
     input(w,area,area.value+'\n직접 추가');
     assert.equal(JSON.parse(w.localStorage.getItem('music-studio-draft-v3')).editor.sections[0].lyrics[3],'직접 추가');
     d.getElementById('composer').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
     await until(()=>jobs.length===1);
     assert.deepEqual(jobs[0].song.sections[0].lyrics,['첫 번째 행 수정','두 번째 행 수정','유지할 행','직접 추가']);
   }finally{dom.window.close();}
 });
}

test('library rename, cancelled delete, trash and restore update player and search',async()=>{
 const library=[{id:'2026-09-24/010101-abcdef12',title:'원래 제목',input:{title:'원래 제목',style:'R&B',lyrics:'가사',seed:1},
   status:'succeeded',created_at:'2026-09-24T00:00:00+09:00',has_audio:true,deleted:false,wav:{duration_seconds:30}}];
 const {dom,w,d}=await setup(undefined,undefined,library);
 try{
   await until(()=>d.getElementById('selected-title').textContent==='원래 제목');
   const source=d.getElementById('audio').getAttribute('src');
   d.querySelector('[data-track-action=rename]').click();
   input(w,d.getElementById('track-name'),'바꾼 이름');
   d.getElementById('rename-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
   await until(()=>d.getElementById('selected-title').textContent==='바꾼 이름');
   assert.equal(d.getElementById('player-title').textContent,'바꾼 이름');
   assert.equal(d.getElementById('audio').getAttribute('src'),source);
   assert.equal(library[0].input.title,'원래 제목');
   input(w,d.getElementById('search'),'바꾼 이름');
   assert.equal(d.querySelectorAll('#tracks .track').length,1);
   w.confirm=()=>false;d.querySelector('[data-track-action=delete]').click();assert.equal(library[0].deleted,false);
   w.confirm=()=>true;d.querySelector('[data-track-action=delete]').click();
   await until(()=>d.getElementById('selected').hidden);
   assert.equal(d.getElementById('audio').getAttribute('src'),null);
   assert.equal(d.getElementById('download').getAttribute('href'),null);
   assert.equal(d.querySelectorAll('#tracks .track').length,0);
   d.querySelector('[data-filter="trash"]').click();
   assert.equal(d.querySelectorAll('#tracks .track').length,1);
   d.querySelector('#tracks .track').click();
   assert.equal(d.getElementById('replay').disabled,true);
   assert.equal(d.querySelector('[data-track-action=restore]').hidden,false);
   d.querySelector('[data-track-action=restore]').click();
   await until(()=>!library[0].deleted);
   d.querySelector('[data-filter="all"]').click();
   await until(()=>d.querySelector('#tracks .track'));
   d.querySelector('#tracks .track').click();
   assert.equal(d.getElementById('selected-title').textContent,'바꾼 이름');
   assert.equal(d.getElementById('replay').disabled,false);
 }finally{dom.window.close();}
});


test('music settings persist, compile, submit in both modes and reuse without duplication',async()=>{
 const {dom,w,d,jobs}=await setup();
 try{
  input(w,d.getElementById('style'),'Korean');
  input(w,d.getElementById('music-bpm'),'82');input(w,d.getElementById('music-key'),'A minor');
  input(w,d.getElementById('music-instruments'),'piano, bass');
  await until(()=>d.getElementById('style-preview').textContent==='82 BPM, A minor, piano, bass, Korean');
  assert.ok(d.getElementById('why-bpm').textContent.includes('분당'));
  const saved=JSON.parse(w.localStorage.getItem('music-studio-draft-v3'));
  assert.equal(saved.music_settings.bpm,82);
  const restored=await setup(saved);
  try{assert.equal(restored.d.getElementById('music-bpm').value,'82');assert.equal(restored.d.getElementById('style').value,'Korean');}finally{restored.dom.window.close();}
  d.getElementById('add-section').click();input(w,d.querySelector('#section-cards textarea'),'노래');
  d.getElementById('composer').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await until(()=>jobs.length===1);assert.equal(jobs[0].song.music_settings.bpm,82);
  const raw=await setup({title:'raw',style:'compiled old',lyrics:'노래',music_settings:saved.music_settings});
  try{
   assert.equal(raw.d.getElementById('style').value,'Korean');
   raw.d.getElementById('composer').dispatchEvent(new raw.w.Event('submit',{bubbles:true,cancelable:true}));
   await until(()=>raw.jobs.length===1);assert.equal(raw.jobs[0].style,undefined);assert.equal(raw.jobs[0].music_settings.bpm,82);
  }finally{raw.dom.window.close();}
 }finally{dom.window.close();}
});

test('music advice applies independently, ignores, and blocks late or stale results',async()=>{
 let release, delayed=false;
 const fake=async payload=>{
  if(delayed)await new Promise(resolve=>release=resolve);
  return {suggestions:[{id:'bpm',field:'bpm',original:String(payload.music_settings.bpm||''),suggested:'90',reason:'템포 조언'},
   {id:'key',field:'key',original:'',suggested:'C major',reason:'조성 조언'},
   {id:'genre',field:'genre',original:'',suggested:'Pop',reason:'장르 조언'}]};
 };
 const {dom,w,d}=await setup(undefined,()=>({suggestions:[]}),undefined,fake);
 try{
  await until(()=>!d.getElementById('music-advise').disabled);
  d.getElementById('music-advise').click();await until(()=>d.querySelectorAll('.music-suggestion').length===3);
  assert.equal(d.getElementById('music-bpm').value,'');
  d.querySelector('.music-suggestion button').click();assert.equal(d.getElementById('music-bpm').value,'90');
  assert.equal(d.querySelector('.music-suggestion button').disabled,false);
  d.querySelector('.music-suggestion button').click();assert.equal(d.getElementById('music-key').value,'C major');
  d.querySelector('.music-suggestion button:last-child').click();assert.equal(d.getElementById('music-genre').value,'');
  d.getElementById('music-advise').click();await until(()=>d.querySelectorAll('.music-suggestion').length===3);
  input(w,d.getElementById('style'),'changed');assert.equal(d.querySelector('.music-suggestion button').disabled,true);
  delayed=true;d.getElementById('music-advise').click();await until(()=>release);
  input(w,d.getElementById('music-bpm'),'100');release();await until(()=>d.querySelectorAll('.music-suggestion').length===3);
  assert.equal(d.querySelector('.music-suggestion button').disabled,true);assert.equal(d.getElementById('music-bpm').value,'100');
 }finally{dom.window.close();}
});


test('version family, branch draft, detach, comparison and alternating audio',async()=>{
 const root='2026-09-23/123456-abcdef12',child='2026-09-24/123457-abcdef13';
 const base={status:'succeeded',created_at:'2026-09-23',has_audio:true,deleted:false,wav:{duration_seconds:12},input:{title:'원본',style:'Korean R&B',lyrics:'원본 가사',seed:7,steps:8,timeout:1800,cot:'off'}};
 const library=[{...base,id:child,title:'수정본',song_id:root,parent_id:root,version_kind:'lyrics_revision',input:{...base.input,lyrics:'수정 가사'}},{...base,id:root,title:'원본',song_id:root,parent_id:null,version_kind:'original'}];
 const {dom,w,d,jobs}=await setup(undefined,undefined,library);
 try{
  assert.equal(d.querySelectorAll('.version-group').length,1);assert.ok(d.querySelector('.version-tree ul'));assert.ok(d.getElementById('version-list').textContent.includes('Lyrics Revision'));
  assert.equal(d.getElementById('compare-version').value,root);
  d.getElementById('compare-versions').click();await until(()=>d.getElementById('version-diff').textContent.includes('원본 가사'));
  d.getElementById('listen-before').click();assert.equal(d.getElementById('audio').getAttribute('src'),'/api/audio?id='+encodeURIComponent(root));
  assert.equal(d.getElementById('selected-title').textContent,'수정본');
  d.getElementById('listen-after').click();assert.equal(d.getElementById('audio').getAttribute('src'),'/api/audio?id='+encodeURIComponent(child));
  w.confirm=()=>false;d.getElementById('branch-version').click();assert.equal(d.getElementById('version-draft').hidden,true);
  w.confirm=()=>true;d.getElementById('version-kind').value='remix';d.getElementById('branch-version').click();
  assert.equal(d.getElementById('version-draft').hidden,false);assert.equal(d.getElementById('lyrics').value,'수정 가사');
  input(w,d.getElementById('style'),'Jazz');
  const draft=JSON.parse(w.localStorage.getItem('music-studio-draft-v3'));assert.equal(draft.version.parent_id,child);
  const restored=await setup(draft,undefined,library);
  try{assert.equal(restored.d.getElementById('version-draft').hidden,false);restored.d.getElementById('detach-version').click();assert.equal(JSON.parse(restored.w.localStorage.getItem('music-studio-draft-v3')).version,null);}finally{restored.dom.window.close();}
  d.getElementById('composer').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await until(()=>jobs.length===1);
  assert.deepEqual(jobs[0].version,{parent_id:child,kind:'remix'});assert.equal(jobs[0].style,'Jazz');
  assert.equal(library[0].input.style,'Korean R&B');
  d.getElementById('reuse').click();assert.equal(d.getElementById('version-draft').hidden,true);
 }finally{dom.window.close();}
});


test('score edit version, explicit use, mode validation, draft restore and request preservation',async()=>{
 const id='2026-09-24/123457-abcdef13';
 const library=[{id,title:'악보 곡',status:'succeeded',created_at:'2026-09-24',has_audio:true,has_score:true,deleted:false,song_id:id,version_kind:'original',wav:{duration_seconds:12},input:{title:'악보 곡',style:'Korean folk',lyrics:'가사',seed:7,steps:8,timeout:1800,cot:'melody'}}];
 const {dom,w,d,jobs}=await setup(undefined,undefined,library);
 try{
  assert.equal(d.getElementById('view-score').hidden,false);
  d.getElementById('view-score').click();await until(()=>d.getElementById('score-content').textContent.includes('K:C'));
  w.confirm=()=>false;d.getElementById('edit-score').click();await new Promise(r=>setTimeout(r,20));assert.equal(d.getElementById('abc').value,'');
  w.confirm=()=>true;d.getElementById('edit-score').click();await until(()=>d.getElementById('use-score').checked);
  assert.ok(d.getElementById('version-source').textContent.includes('Score Revision'));
  input(w,d.getElementById('abc'),'X:1\nM:4/4\nQ:1/4=100\nK:C\nD E F G |');
  d.getElementById('inspect-score').click();await until(()=>d.getElementById('score-analysis').textContent.includes('100'));
  const draft=JSON.parse(w.localStorage.getItem('music-studio-draft-v3'));
  const restored=await setup(draft,undefined,library);
  try{assert.equal(restored.d.getElementById('abc').value,d.getElementById('abc').value);assert.equal(restored.d.getElementById('use-score').checked,true);}finally{restored.dom.window.close();}
  d.getElementById('cot').value='off';d.getElementById('composer').dispatchEvent(new w.Event('submit',{cancelable:true}));assert.equal(jobs.length,0);assert.ok(d.getElementById('form-error').textContent.includes('ABC'));
  d.getElementById('cot').value='melody';d.getElementById('composer').dispatchEvent(new w.Event('submit',{cancelable:true}));await until(()=>jobs.length===1);
  assert.equal(jobs[0].abc,d.getElementById('abc').value);assert.equal(jobs[0].version.kind,'score_revision');assert.equal(d.getElementById('workspace-arrange').hidden,false);
  assert.equal(library[0].input.abc,undefined);
 }finally{dom.window.close();}
});


test('workspace tabs preserve exact draft nodes, values, keyboard navigation and generation payload',async()=>{
 const {dom,w,d,jobs}=await setup();
 try{
  assert.equal(d.getElementById('workspace-write').hidden,false);
  assert.equal(d.querySelectorAll('[role=tabpanel]:not([hidden])').length,1);
  assert.equal(d.getElementById('advanced-key').open,false);
  d.getElementById('add-section').click();const lyrics=d.querySelector('#section-cards textarea');input(w,lyrics,'유지할 가사');
  input(w,d.getElementById('music-bpm'),'90');input(w,d.getElementById('abc'),'K:C\nC D E F |');
  const before=w.localStorage.getItem('music-studio-draft-v3');
  for(const name of ['compose','arrange','versions','write']){
   d.getElementById('tab-'+name).click();assert.equal(d.getElementById('workspace-'+name).hidden,false);
   assert.equal(d.querySelectorAll('[role=tabpanel]:not([hidden])').length,1);
   assert.equal(d.querySelector('#section-cards textarea'),lyrics);
   assert.equal(w.localStorage.getItem('music-studio-draft-v3'),before);
  }
  d.getElementById('tab-write').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
  assert.equal(d.activeElement.id,'tab-compose');assert.equal(d.getElementById('tab-compose').getAttribute('aria-selected'),'true');
  assert.equal(w.localStorage.getItem('music-studio-workspace-v8'),'compose');
  assert.ok(d.getElementById('status-write').textContent.includes('✓'));
  assert.equal(d.querySelectorAll('#composer button[type=submit]').length,1);
  d.getElementById('composer').dispatchEvent(new w.Event('submit',{cancelable:true}));await until(()=>jobs.length===1);
  assert.equal(jobs[0].song.sections[0].lyrics[0],'유지할 가사');assert.equal(jobs[0].song.music_settings.bpm,90);assert.equal(jobs[0].abc,undefined);
  const reopened=await setup(JSON.parse(before),undefined,undefined,undefined,'arrange');
  try{assert.equal(reopened.d.getElementById('workspace-arrange').hidden,false);assert.equal(reopened.d.getElementById('abc').value,'K:C\nC D E F |');}finally{reopened.dom.window.close();}
 }finally{dom.window.close();}
});

test('hidden invalid inputs open their workspace and disclosure before generation',async()=>{
 const {dom,w,d,jobs}=await setup();
 try{
  input(w,d.getElementById('seed'),'-1');
  d.getElementById('composer').dispatchEvent(new w.Event('submit',{cancelable:true}));
  assert.equal(jobs.length,0);assert.equal(d.getElementById('workspace-arrange').hidden,false);
  assert.equal(d.querySelector('.advanced').open,true);assert.equal(d.activeElement.id,'seed');
  input(w,d.getElementById('seed'),'7');input(w,d.getElementById('style'),'');
  d.getElementById('tab-write').click();d.getElementById('composer').dispatchEvent(new w.Event('submit',{cancelable:true}));
  assert.equal(jobs.length,0);assert.equal(d.getElementById('workspace-compose').hidden,false);assert.equal(d.activeElement.id,'style');
 }finally{dom.window.close();}
});

test('AI suggestions remain applicable across workspace switches and advice opens on request only',async()=>{
 let calls=0;
 const advisor=async payload=>({suggestions:[{id:'one',section_id:payload.section.id,line_index:0,original:payload.section.lyrics[0],suggested:'새로운 가사',reason:'표현',type:'expression'}]});
 const musicAdvisor=async()=>{calls++;return {suggestions:[]};};
 const {dom,w,d}=await setup(undefined,advisor,undefined,musicAdvisor);
 try{
  assert.equal(d.getElementById('music-advice-body').hidden,true);assert.equal(calls,0);
  d.getElementById('add-section').click();input(w,d.querySelector('#section-cards textarea'),'원래 가사');
  await until(()=>!d.querySelector('[data-action=review]').disabled);d.querySelector('[data-action=review]').click();await until(()=>d.querySelector('.suggestion'));
  const apply=d.querySelector('.suggestion button');
  d.getElementById('tab-compose').click();d.getElementById('tab-arrange').click();d.getElementById('tab-write').click();
  assert.equal(apply.disabled,false);apply.click();assert.equal(d.querySelector('#section-cards textarea').value,'새로운 가사');
  d.getElementById('tab-compose').click();await until(()=>!d.getElementById('music-advise').disabled);d.getElementById('music-advise').click();await until(()=>calls===1);
  assert.equal(d.getElementById('music-advice-body').hidden,false);
 }finally{dom.window.close();}
});


test('playlist manages an unselected track without selecting or playing it',async()=>{
 const base={status:'succeeded',created_at:'2026-09-24',has_audio:true,deleted:false,wav:{duration_seconds:12},input:{title:'원본',style:'Korean',lyrics:'가사',seed:7}};
 const library=[{...base,id:'2026-09-24/123456-abcdef12',title:'재생 곡'},{...base,id:'2026-09-24/123457-abcdef13',title:'관리할 곡'}];
 const {dom,w,d}=await setup(undefined,undefined,library);
 try{
  let plays=0;w.HTMLMediaElement.prototype.play=()=>{plays++;return Promise.resolve();};
  const source=d.getElementById('audio').getAttribute('src');
  const action=name=>Array.from(d.querySelectorAll('[data-track-action]')).find(b=>b.dataset.trackId===library[1].id&&b.dataset.trackAction===name);
  assert.equal(d.querySelector('#selected [data-track-action]'),null);
  action('rename').click();assert.equal(d.getElementById('track-name').value,'관리할 곡');
  input(w,d.getElementById('track-name'),'새 이름');d.getElementById('rename-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await until(()=>library[1].title==='새 이름'&&!d.getElementById('rename-dialog').open);
  assert.equal(d.getElementById('selected-title').textContent,'재생 곡');assert.equal(d.getElementById('audio').getAttribute('src'),source);
  action('delete').click();await until(()=>library[1].deleted&&!action('delete'));
  assert.equal(d.getElementById('selected-title').textContent,'재생 곡');assert.equal(d.getElementById('audio').getAttribute('src'),source);assert.equal(plays,0);
  d.querySelector('[data-filter=trash]').click();action('restore').click();await until(()=>!library[1].deleted&&!action('restore'));
  assert.equal(d.getElementById('selected-title').textContent,'재생 곡');assert.equal(plays,0);
 }finally{dom.window.close();}
});
