'use strict';
const $ = id => document.getElementById(id);
let tracks = [], selectedId = null, filter = 'all', busy = false, ready = false;
let renderedKey = '', completedJob = null, sending = false, polling = false, connectionError = false, toastTimer;
let extraThreads = 4;
const editor = new SongEditor(()=>{count();saveDraft();},api);
const labels = {succeeded:'완성',running:'생성 중',failed:'실패',timed_out:'시간 초과',cancelled:'중단'};
const presetStyles = {
  rnb:'Korean, mellow R&B, warm male vocal, electric piano, soft bass, gentle drums',
  lofi:'Korean, lo-fi jazz, soft female vocal, warm Rhodes piano, brush drums, rainy cafe mood',
  pop:'Korean, bright indie pop, clear female vocal, acoustic guitar, lively drums, uplifting chorus',
  acoustic:'Korean, acoustic folk, gentle male vocal, fingerpicked guitar, intimate warm atmosphere'
};
const exampleLyrics = '[Verse]\n강물 위로 번져 가는 불빛 사이로\n오늘의 기억을 천천히 내려놓아\n\n[Chorus]\n조금 더 달려도 괜찮아\n새벽 끝엔 다시 아침이 오니까';
const clock = seconds => {const n=Math.max(0,Math.floor(seconds||0));return `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`;};
function notify(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4000);}
function error(message){$('form-error').textContent=message||'';$('form-error').hidden=!message;}
function count(){ $('char-count').textContent=`${$('lyrics').value.length.toLocaleString()} / 12,000`; }
function flatInputs(){return {title:$('title').value.trim(),style:$('style').value.trim(),lyrics:$('lyrics').value,
  seed:Number($('seed').value),steps:Number($('steps').value),threads:extraThreads,timeout:Number($('timeout').value),cot:$('cot').value};}
function inputs(){const data=flatInputs();if(editor.mode==='sections'){delete data.title;delete data.style;delete data.lyrics;data.song=editor.song();}return data;}
function saveDraft(){try{localStorage.setItem('music-studio-draft-v3',JSON.stringify({...flatInputs(),editor:editor.draft()}));}catch{notify('초안을 저장하지 못했습니다. 브라우저 저장 공간을 확인해 주세요.');}}
function fill(data){for(const k of ['title','style','lyrics','seed','steps','timeout','cot'])if(data[k]!==undefined)$(k).value=data[k];extraThreads=data.threads||4;editor.load(data);count();}
function updateActions(){ $('generate').disabled=sending||busy||!ready;$('generate').replaceChildren(document.createTextNode(sending?'요청을 보내는 중…':busy?'음악을 만들고 있어요…':'음악 만들기 ↗'));$('replay').disabled=sending||busy||!ready; }
async function api(path,data){const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json','X-Studio-Request':'1'},body:JSON.stringify(data)}:{});const result=await response.json();if(!response.ok)throw new Error(result.error||'요청에 실패했습니다.');return result;}
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function renderTracks(force=false){
  const query=$('search').value.toLocaleLowerCase();
  const key=JSON.stringify([tracks.map(t=>[t.id,t.status,t.has_audio]),selectedId,filter,query]);
  if(!force&&key===renderedKey)return;renderedKey=key;
  const list=tracks.filter(t=>(filter==='all'||(filter==='failed'?!['succeeded','running'].includes(t.status):t.status===filter))&&`${t.title} ${t.input.style}`.toLocaleLowerCase().includes(query));
  $('tracks').replaceChildren();$('track-count').textContent=tracks.filter(t=>t.has_audio).length;
  if(!list.length){$('tracks').append(element('p','empty',tracks.length?'조건에 맞는 곡이 없어요. 다른 검색어나 필터를 선택해 주세요.':'아직 만든 음악이 없어요. 왼쪽에서 첫 곡을 만들어 보세요.'));return;}
  for(const track of list){
    const button=element('button',`track${track.id===selectedId?' selected':''}`);button.type='button';button.setAttribute('aria-label',`${track.title} 선택`);button.setAttribute('aria-pressed',String(track.id===selectedId));
    const art=element('span','track-art',track.has_audio?'▶':'♪');art.setAttribute('aria-hidden','true');button.append(art);
    const copy=element('span','track-copy');copy.append(element('strong','',track.title),element('span','style-preview',track.input.style),element('span','track-date',`${new Date(track.created_at).toLocaleDateString('ko-KR')} · ${labels[track.status]||track.status}`));button.append(copy,element('span','track-time',track.wav?clock(track.wav.duration_seconds):'—'));
    button.addEventListener('click',()=>select(track.id,true));$('tracks').append(button);
  }
}
function select(id,play=false){
  const track=tracks.find(t=>t.id===id);if(!track)return;
  const changed=selectedId!==id;selectedId=id;$('selected').hidden=false;$('selected-title').textContent=track.title;$('selected-style').textContent=track.input.style;$('selected-lyrics').textContent=track.input.lyrics;
  $('selected-error').hidden=!track.error;$('selected-error').textContent=track.error||'';
  $('selected-stats').replaceChildren();
  const peak=Object.values(track.gpu?.peak_device_used_mib||{});
  for(const [label,value] of [['음원 길이',track.wav?clock(track.wav.duration_seconds):'—'],['생성 시간',track.elapsed_seconds?`${track.elapsed_seconds.toFixed(1)}초`:'—'],['VRAM 표본 최대',peak.length?`${(Math.max(...peak)/1024).toFixed(1)} GiB`:'—'],['시드',track.input.seed]]){
    const stat=element('span','',label);stat.append(element('strong','',String(value)));if(label.startsWith('VRAM'))stat.title='장치 전체 사용량을 약 1초마다 측정한 값입니다.';$('selected-stats').append(stat);
  }
  $('selected-song').hidden=!track.input.song;$('selected-sections').replaceChildren();
  for(const section of track.input.song?.sections||[])$('selected-sections').append(element('li','',section.label+' · '+(section.bars===null?'마디 수 미정':section.bars+' bars')));
  $('metadata-link').href=`/api/metadata?id=${encodeURIComponent(id)}`;
  if(track.has_audio){
    $('player-title').textContent=track.title;$('player-subtitle').textContent=`48 kHz · Stereo · ${clock(track.wav.duration_seconds)}`;
    const url=`/api/audio?id=${encodeURIComponent(id)}`;
    if(changed||!$('audio').getAttribute('src')){$('audio').src=url;}
    $('download').href=url+'&download=1';$('download').classList.remove('disabled');$('download').setAttribute('aria-disabled','false');
    if(play)$('audio').play().catch(()=>notify('아래 플레이어에서 재생 버튼을 눌러 주세요.'));
  }else{
    $('audio').pause();$('audio').removeAttribute('src');$('audio').load();$('player-title').textContent=track.title;$('player-subtitle').textContent='아직 재생할 음원이 없습니다.';$('download').removeAttribute('href');$('download').classList.add('disabled');$('download').setAttribute('aria-disabled','true');
  }
  renderTracks();updateActions();
}
function renderJob(job){
  $('job-panel').hidden=!job;if(!job)return;
  $('job-stage').textContent=job.stage;$('job-title').textContent=job.title;$('job-time').textContent=clock(job.elapsed_seconds);$('job-log').textContent=job.log||'모델과 실행 환경을 확인하고 있습니다.';
  $('activity').classList.toggle('done',job.status!=='running');
  $('job-message').textContent=job.error|| (job.status==='running'?'창을 새로고침해도 생성은 계속됩니다.':job.status==='succeeded'?'라이브러리에 저장됐어요. 아래에서 들어보세요.':'설정을 확인하고 다시 시도해 주세요.');
  if(job.status!=='running'&&completedJob!==job.id){completedJob=job.id;if(job.status==='succeeded'&&job.run_id){select(job.run_id);notify('새로운 음악이 완성됐어요.');}}
}
async function refresh(){
  if(polling)return;polling=true;
  try{const state=await api('/api/state');if(connectionError){error('');connectionError=false;}tracks=state.tracks;ready=state.ready;busy=state.job?.status==='running'||state.busy;$('connection').textContent=ready?(busy?'음악 생성 중':'로컬 스튜디오 연결됨'):'환경 확인 필요';
    if(state.issue)error(state.issue);renderTracks();renderJob(state.job);if(!selectedId&&tracks.some(t=>t.has_audio))select(tracks.find(t=>t.has_audio).id);updateActions();
  }catch(e){connectionError=true;ready=false;updateActions();$('connection').textContent='서버 연결 끊김';error('스튜디오 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.');}
  finally{polling=false;}
}
async function submit(path,data){
  if(sending||busy)return;sending=true;error('');updateActions();
  try{await api(path,data);busy=true;notify('음악 만들기를 시작했어요.');await refresh();}
  catch(e){error(e.message);}
  finally{sending=false;updateActions();}
}
$('composer').addEventListener('submit',event=>{event.preventDefault();const data=inputs();if(!flatInputs().style.trim()){error('원하는 음악 스타일을 입력해 주세요.');$('style').focus();return;}if(editor.mode==='raw'&&!data.lyrics.trim()){error('노래에 사용할 가사를 입력해 주세요.');$('lyrics').focus();return;}saveDraft();submit('/api/jobs',data);});
$('composer').addEventListener('input',event=>{if(!event.target.closest('#section-cards')){count();saveDraft();editor.changed();}});
$('composer').addEventListener('change',saveDraft);
$('reuse').addEventListener('click',()=>{const track=tracks.find(t=>t.id===selectedId);if(track&&confirm('현재 초안을 선택한 곡의 가사와 설정으로 바꿀까요?')){fill(track.input);saveDraft();$('title').focus();$('composer').scrollIntoView({behavior:'smooth',block:'start'});notify('가사와 설정을 가져왔어요. 수정해서 새 곡을 만들어 보세요.');}});
$('replay').addEventListener('click',()=>{if(selectedId)submit('/api/replay',{id:selectedId});});
document.querySelectorAll('[data-preset]').forEach(button=>button.addEventListener('click',()=>{$('style').value=presetStyles[button.dataset.preset];saveDraft();editor.changed();}));
$('example').addEventListener('click',()=>{if($('lyrics').value.trim()&&$('lyrics').value!==exampleLyrics&&!confirm('현재 가사를 예시 가사로 바꿀까요?'))return;$('lyrics').value=exampleLyrics;count();saveDraft();editor.changed();});
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});renderTracks();}));
$('search').addEventListener('input',()=>renderTracks());$('refresh').addEventListener('click',()=>refresh());
$('audio').addEventListener('error',()=>{if($('audio').getAttribute('src'))notify('음원을 불러오지 못했습니다. 서버 연결을 확인해 주세요.');});
try{const draft=JSON.parse(localStorage.getItem('music-studio-draft-v3')||localStorage.getItem('music-studio-draft'));if(draft&&typeof draft==='object')fill(draft);}catch{/* ignore invalid draft */}
editor.init();count();refresh();setInterval(refresh,2000);
