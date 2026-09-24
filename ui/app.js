'use strict';
const $ = id => document.getElementById(id);
let tracks = [], selectedId = null, filter = 'all', busy = false, ready = false;
let renderedKey = '', completedJob = null, sending = false, polling = false, connectionError = false, toastTimer;
let extraThreads = 4;
let versionDraft=null, versionsKey='', comparisonRevision=0;
const versionLabels={original:'Original',variation:'Variation',lyrics_revision:'Lyrics Revision',remix:'Remix',replay:'Replay',score_revision:'Score Revision'};
let managing=false, renameId=null, managementRevision=0;
const music = new MusicGuide(api,()=>editor.changed());
window.musicGuide=music;
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
function inputs(){const data=flatInputs();if(editor.mode==='sections'){delete data.title;delete data.style;delete data.lyrics;data.song=editor.song();}else if(Object.keys(music.settings()).length>1){delete data.style;data.music_settings=music.settings();}if($('use-score').checked)data.abc=$('abc').value;if(versionDraft)data.version={parent_id:versionDraft.parent_id,kind:versionDraft.kind};return data;}
function saveDraft(){try{localStorage.setItem('music-studio-draft-v3',JSON.stringify({...flatInputs(),score_editor:{enabled:$('use-score').checked,text:$('abc').value},version:versionDraft,music_settings:music.settings(),editor:editor.draft()}));}catch{notify('초안을 저장하지 못했습니다. 브라우저 저장 공간을 확인해 주세요.');}}
function fill(data){$('abc').value=data.score_editor?.text??data.abc??'';$('use-score').checked=data.score_editor?.enabled??!!data.abc;$('score-analysis').textContent='';versionDraft=data.version||null;paintVersionDraft();for(const k of ['title','style','lyrics','seed','steps','timeout','cot'])if(data[k]!==undefined)$(k).value=data[k];extraThreads=data.threads||4;music.load(data);editor.load(data);count();}
function updateActions(){ $('generate').disabled=sending||busy||!ready;$('generate').replaceChildren(document.createTextNode(sending?'요청을 보내는 중…':busy?'음악을 만들고 있어요…':'음악 만들기 ↗'));const track=tracks.find(t=>t.id===selectedId);
  $('replay').disabled=sending||busy||!ready||!!track?.deleted;
  $('reuse').disabled=!!track?.deleted;
  $('edit-score').disabled=busy||!track?.has_score||!!track?.deleted;
  $('branch-version').disabled=busy||!track||!!track.deleted||track.status==='running';
  for(const id of ['rename-track','delete-track','restore-track'])$(id).disabled=managing||busy||!track;
  $('delete-track').hidden=!!track?.deleted;$('restore-track').hidden=!track?.deleted; }
async function api(path,data){const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json','X-Studio-Request':'1'},body:JSON.stringify(data)}:{});const result=await response.json();if(!response.ok)throw new Error(result.error||'요청에 실패했습니다.');return result;}
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function renderTracks(force=false){
  const query=$('search').value.toLocaleLowerCase();
  const key=JSON.stringify([tracks.map(t=>[t.id,t.title,t.status,t.has_audio,t.deleted,t.song_id,t.parent_id,t.version_kind,t.has_score]),selectedId,filter,query]);
  if(!force&&key===renderedKey)return;renderedKey=key;
  const list=tracks.filter(t=>(filter==='trash'?t.deleted:!t.deleted&&(filter==='all'||(filter==='failed'?!['succeeded','running'].includes(t.status):t.status===filter)))&&`${t.title} ${t.input.style}`.toLocaleLowerCase().includes(query));
  $('tracks').replaceChildren();$('track-count').textContent=tracks.filter(t=>!t.deleted&&t.has_audio).length;
  if(!list.length){$('tracks').append(element('p','empty',tracks.length?'조건에 맞는 곡이 없어요. 다른 검색어나 필터를 선택해 주세요.':'아직 만든 음악이 없어요. 왼쪽에서 첫 곡을 만들어 보세요.'));return;}
  const groups=new Map();
  for(const track of list){const id=track.song_id||track.id;if(!groups.has(id))groups.set(id,[]);groups.get(id).push(track);}
  for(const [id,family] of groups){
    const root=tracks.find(t=>t.id===id);
    const heading=element('h3','version-group',(root?.title||'원본 기록 없음')+' · '+family.length+'개 버전');$('tracks').append(heading);
    for(const track of family){
    const button=element('button',`track${track.id===selectedId?' selected':''}`);button.type='button';button.setAttribute('aria-label',`${track.title} 선택`);button.setAttribute('aria-pressed',String(track.id===selectedId));
    const art=element('span','track-art',track.has_audio?'▶':'♪');art.setAttribute('aria-hidden','true');button.append(art);
    const copy=element('span','track-copy');copy.append(element('strong','',track.title),element('span','style-preview',track.input.style),element('span','track-date',`${new Date(track.created_at).toLocaleDateString('ko-KR')} · ${track.deleted?'휴지통':labels[track.status]||track.status} · ${versionLabels[track.version_kind]||'Original'}`));button.append(copy,element('span','track-time',track.wav?clock(track.wav.duration_seconds):'—'));
    button.addEventListener('click',()=>select(track.id,true));$('tracks').append(button);
    }
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
  if(changed||$('view-score').hidden===!!track.has_score){$('score-content').textContent='';$('score-status').textContent=track.has_score?'저장된 계획 또는 입력 악보를 확인할 수 있습니다.':'저장된 악보가 없습니다. 멜로디/화성 계획 모드로 새로 생성하면 악보를 저장합니다.';}
  $('view-score').hidden=!track.has_score;$('download-score').hidden=!track.has_score;$('download-score').href='/api/score?id='+encodeURIComponent(id)+'&download=1';
  $('metadata-link').href=`/api/metadata?id=${encodeURIComponent(id)}`;
  if(track.has_audio){
    $('player-title').textContent=track.title;$('player-subtitle').textContent=`48 kHz · Stereo · ${clock(track.wav.duration_seconds)}`;
    const url=`/api/audio?id=${encodeURIComponent(id)}`;
    if(changed||$('audio').getAttribute('src')!==url){$('audio').src=url;}
    $('download').href=url+'&download=1';$('download').classList.remove('disabled');$('download').setAttribute('aria-disabled','false');
    if(play)$('audio').play().catch(()=>notify('아래 플레이어에서 재생 버튼을 눌러 주세요.'));
  }else{
    $('audio').pause();$('audio').removeAttribute('src');$('audio').load();$('player-title').textContent=track.title;$('player-subtitle').textContent='아직 재생할 음원이 없습니다.';$('download').removeAttribute('href');$('download').classList.add('disabled');$('download').setAttribute('aria-disabled','true');
  }
  renderVersions();renderTracks();updateActions();
}
function renderJob(job){
  $('job-panel').hidden=!job;if(!job)return;
  $('job-stage').textContent=job.stage;$('job-title').textContent=job.title;$('job-time').textContent=clock(job.elapsed_seconds);$('job-log').textContent=job.log||'모델과 실행 환경을 확인하고 있습니다.';
  $('activity').classList.toggle('done',job.status!=='running');
  $('job-message').textContent=job.error|| (job.status==='running'?'창을 새로고침해도 생성은 계속됩니다.':job.status==='succeeded'?'라이브러리에 저장됐어요. 아래에서 들어보세요.':'설정을 확인하고 다시 시도해 주세요.');
  if(job.status!=='running'&&completedJob!==job.id){completedJob=job.id;if(job.status==='succeeded'&&job.run_id){select(job.run_id);notify('새로운 음악이 완성됐어요.');}}
}
async function refresh(){
  if(polling)return;polling=true;const revision=managementRevision;
  try{const state=await api('/api/state');if(revision!==managementRevision)return;if(connectionError){error('');connectionError=false;}tracks=[...state.tracks,...(state.trash||[])];ready=state.ready;busy=state.job?.status==='running'||state.busy;$('connection').textContent=ready?(busy?'음악 생성 중':'로컬 스튜디오 연결됨'):'환경 확인 필요';
    if(state.issue)error(state.issue);const current=tracks.find(t=>t.id===selectedId);if(selectedId&&(!current||(current.deleted&&filter!=='trash')))clearSelection();if(current&&($('selected-title').textContent!==current.title||$('view-score').hidden===!!current.has_score))select(current.id);renderTracks();renderVersions();renderJob(state.job);if(filter!=='trash'&&!selectedId&&tracks.some(t=>t.has_audio))select(tracks.find(t=>t.has_audio).id);updateActions();
  }catch(e){connectionError=true;ready=false;updateActions();$('connection').textContent='서버 연결 끊김';error('스튜디오 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.');}
  finally{polling=false;}
}
async function submit(path,data){
  if(sending||busy)return;sending=true;error('');updateActions();
  try{await api(path,data);busy=true;notify('음악 만들기를 시작했어요.');await refresh();}
  catch(e){error(e.message);}
  finally{sending=false;updateActions();}
}
$('composer').addEventListener('submit',event=>{event.preventDefault();const data=inputs();if(data.abc!==undefined&&$('cot').value==='off'){error('ABC 악보를 사용하려면 멜로디 또는 멜로디 + 화성 계획 모드를 선택하세요.');$('cot').focus();return;}if(!flatInputs().style.trim()&&Object.keys(music.settings()).length===1){error('원하는 음악 스타일을 입력해 주세요.');$('style').focus();return;}if(editor.mode==='raw'&&!data.lyrics.trim()){error('노래에 사용할 가사를 입력해 주세요.');$('lyrics').focus();return;}saveDraft();submit('/api/jobs',data);});
$('composer').addEventListener('input',event=>{if(!event.target.closest('#section-cards')){music.changed();count();saveDraft();editor.changed();}});
$('composer').addEventListener('change',saveDraft);
$('reuse').addEventListener('click',()=>{const track=tracks.find(t=>t.id===selectedId);if(track&&confirm('현재 초안을 선택한 곡의 가사와 설정으로 바꿀까요?')){fill(track.input);saveDraft();$('title').focus();$('composer').scrollIntoView({behavior:'smooth',block:'start'});notify('가사와 설정을 가져왔어요. 수정해서 새 곡을 만들어 보세요.');}});
$('replay').addEventListener('click',()=>{if(selectedId)submit('/api/replay',{id:selectedId});});
document.querySelectorAll('[data-preset]').forEach(button=>button.addEventListener('click',()=>{$('style').value=presetStyles[button.dataset.preset];music.changed();saveDraft();editor.changed();}));
$('example').addEventListener('click',()=>{if($('lyrics').value.trim()&&$('lyrics').value!==exampleLyrics&&!confirm('현재 가사를 예시 가사로 바꿀까요?'))return;$('lyrics').value=exampleLyrics;count();saveDraft();editor.changed();});
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});renderTracks();}));
$('search').addEventListener('input',()=>renderTracks());$('refresh').addEventListener('click',()=>refresh());
$('audio').addEventListener('error',()=>{if($('audio').getAttribute('src'))notify('음원을 불러오지 못했습니다. 서버 연결을 확인해 주세요.');});

function clearSelection(){
  selectedId=null;versionsKey='';comparisonRevision++;$('selected').hidden=true;
  $('audio').pause();$('audio').removeAttribute('src');$('audio').load();
  $('player-title').textContent='라이브러리에서 곡을 선택하세요';$('player-subtitle').textContent='';
  $('download').removeAttribute('href');$('download').classList.add('disabled');$('download').setAttribute('aria-disabled','true');
}
async function manageTrack(action,id,title){
  if(managing||busy)return false;
  managing=true;updateActions();$('save-track-name').disabled=true;
  try{
    const track=await api('/api/tracks/'+action,{id,title});managementRevision++;
    tracks=tracks.map(t=>t.id===id?track:t);
    if(action==='delete'||action==='restore'){if(selectedId===id)clearSelection();}
    else if(selectedId===id)select(id);
    renderTracks(true);
    notify(action==='rename'?'곡 이름을 변경했습니다.':action==='delete'?'휴지통으로 이동했습니다. 휴지통에서 복원할 수 있어요.':'라이브러리에 복원했습니다.');
    return true;
  }catch(e){if(action==='rename')$('manage-error').textContent=e.message;else notify(e.message);return false;}
  finally{managing=false;$('save-track-name').disabled=false;updateActions();}
}
$('rename-track').onclick=()=>{
  const track=tracks.find(t=>t.id===selectedId);if(!track)return;
  renameId=track.id;$('track-name').value=track.title;$('manage-error').textContent='';
  $('rename-dialog').showModal();$('track-name').focus();
};
$('cancel-rename').onclick=()=>$('rename-dialog').close();
$('rename-form').onsubmit=async event=>{event.preventDefault();if(await manageTrack('rename',renameId,$('track-name').value.trim()))$('rename-dialog').close();};
$('delete-track').onclick=()=>{
  const track=tracks.find(t=>t.id===selectedId);
  if(track&&confirm('“'+track.title+'”을 휴지통으로 이동할까요? 음원과 생성 기록은 보관되며 복원할 수 있습니다.'))manageTrack('delete',track.id);
};
$('restore-track').onclick=()=>{if(selectedId)manageTrack('restore',selectedId);};

$('inspect-score').onclick=async()=>{
  const abc=$('abc').value;
  try{const result=await api('/api/score/inspect',{abc});if(abc!==$('abc').value)return;$('score-analysis').textContent=Object.entries(result.headers).map(([k,v])=>k+': '+v).join(' · ')+' · '+result.characters+'자\n'+result.notice;}
  catch(e){if(abc===$('abc').value)$('score-analysis').textContent=e.message;}
};
$('abc-file').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  try{if(file.size>96000)throw new Error('ABC 파일은 96KB 이하여야 합니다.');const text=await file.text();if(text.length>24000)throw new Error('ABC는 24,000자 이하여야 합니다.');
    if(!confirm('현재 악보 텍스트를 파일 내용으로 바꿀까요?'))return;
    $('abc').value=text;$('score-analysis').textContent='파일을 가져왔습니다. 헤더를 확인한 뒤 악보 사용을 선택하세요.';saveDraft();
  }catch(e){$('score-analysis').textContent=e.message;}finally{event.target.value='';}
};
$('view-score').onclick=async()=>{
  const id=selectedId;
  try{const result=await api('/api/score?id='+encodeURIComponent(id));if(id!==selectedId)return;$('score-content').textContent=result.abc;$('score-status').textContent=result.source==='provided'?'생성에 사용한 입력 악보':'모델이 생성한 계획 악보 · 음원 채보 결과가 아닙니다.';}
  catch(e){if(id===selectedId)$('score-status').textContent=e.message;}
};
$('edit-score').onclick=async()=>{
  const track=tracks.find(t=>t.id===selectedId);if(!track?.has_score||track.deleted||busy)return;
  try{const result=await api('/api/score?id='+encodeURIComponent(track.id));if(track.id!==selectedId)return;
    if(!confirm('현재 초안을 이 곡의 가사·설정·악보로 바꾸고 악보 수정 버전을 준비할까요?'))return;
    fill(track.input);$('abc').value=result.abc;$('use-score').checked=true;
    if($('cot').value==='off')$('cot').value='full';
    versionDraft={parent_id:track.id,kind:'score_revision',title:track.title};paintVersionDraft();saveDraft();
    $('abc').closest('details').open=true;$('abc').focus();$('abc').scrollIntoView({behavior:'smooth',block:'center'});
  }catch(e){notify(e.message);}
};

function paintVersionDraft(){
  $('version-draft').hidden=!versionDraft;
  $('version-source').textContent=versionDraft?`${versionLabels[versionDraft.kind]||'Version'} · ${versionDraft.title||versionDraft.parent_id}에서 시작`:'';
}
$('detach-version').onclick=()=>{versionDraft=null;paintVersionDraft();saveDraft();};
$('branch-version').onclick=()=>{
  const track=tracks.find(t=>t.id===selectedId);if(!track||track.deleted||busy||track.status==='running')return;
  if(!confirm('현재 초안을 선택한 곡의 가사·설정으로 바꾸고 새 버전을 준비할까요?'))return;
  fill(track.input);versionDraft={parent_id:track.id,kind:$('version-kind').value,title:track.title};
  paintVersionDraft();saveDraft();$('composer').scrollIntoView({behavior:'smooth',block:'start'});notify('초안을 편집한 뒤 음악 만들기를 누르면 새 버전으로 저장합니다.');
};
function renderVersions(){
  const track=tracks.find(t=>t.id===selectedId);if(!track)return;
  const family=tracks.filter(t=>(t.song_id||t.id)===(track.song_id||track.id));
  const key=JSON.stringify([selectedId,family.map(t=>[t.id,t.title,t.deleted,t.status,t.has_audio,t.parent_id,t.version_kind,t.has_score])]);if(key===versionsKey)return;versionsKey=key;comparisonRevision++;
  const parent=tracks.find(t=>t.id===track.parent_id);
  $('version-lineage').textContent=(versionLabels[track.version_kind]||'Original')+(parent?' · 부모: '+parent.title+(parent.deleted?' (휴지통)':''):'')+(track.lineage_issue?' · '+track.lineage_issue:'');
  $('version-list').replaceChildren();$('compare-version').replaceChildren();$('version-diff').replaceChildren();
  for(const t of family){
    const name=(versionLabels[t.version_kind,t.has_score]||'Original')+' · '+t.title+(t.deleted?' (휴지통)':'');
    const b=element('button','quiet-button',name);b.type='button';b.setAttribute('aria-pressed',String(t.id===selectedId));b.onclick=()=>select(t.id);$('version-list').append(b);
    if(t.id!==selectedId){const option=element('option','',name);option.value=t.id;$('compare-version').append(option);}
  }
  if(parent)$('compare-version').value=parent.id;
  if(!$('compare-version').value&&$('compare-version').options.length)$('compare-version').selectedIndex=0;
  comparisonActions();
}
function comparisonActions(){
  const before=tracks.find(t=>t.id===$('compare-version').value),after=tracks.find(t=>t.id===selectedId);
  $('compare-versions').disabled=!before||!after;$('listen-before').disabled=!before?.has_audio;$('listen-after').disabled=!after?.has_audio;
}
$('compare-version').onchange=()=>{comparisonRevision++;$('version-diff').replaceChildren();comparisonActions();};
$('compare-versions').onclick=async()=>{
  const revision=++comparisonRevision;
  $('version-diff').textContent='변경 내용을 확인하고 있습니다…';
  try{
    const result=await api('/api/versions/compare?left='+encodeURIComponent($('compare-version').value)+'&right='+encodeURIComponent(selectedId));if(revision!==comparisonRevision)return;
    $('version-diff').replaceChildren();
    if(!result.changes.length)$('version-diff').textContent='생성 입력과 엔진 설정이 같습니다.';
    for(const change of result.changes){
      const details=element('details','');details.append(element('summary','',change.label));
      const format=value=>typeof value==='string'?value:JSON.stringify(value,null,2);
      details.append(element('pre','', '기준\n'+format(change.before)+'\n\n선택 버전\n'+format(change.after)));$('version-diff').append(details);
    }
  }catch(e){if(revision===comparisonRevision)$('version-diff').textContent=e.message;}
};
function listenVersion(id){
  const track=tracks.find(t=>t.id===id);if(!track?.has_audio)return;
  const url='/api/audio?id='+encodeURIComponent(id);$('audio').src=url;
  $('player-title').textContent=track.title;$('player-subtitle').textContent='버전 비교 · '+(versionLabels[track.version_kind]||'Original');
  $('download').href=url+'&download=1';$('download').classList.remove('disabled');$('download').setAttribute('aria-disabled','false');
  $('audio').play().catch(()=>notify('아래 플레이어에서 재생 버튼을 눌러 주세요.'));
}
$('listen-before').onclick=()=>listenVersion($('compare-version').value);
$('listen-after').onclick=()=>listenVersion(selectedId);

try{const draft=JSON.parse(localStorage.getItem('music-studio-draft-v3')||localStorage.getItem('music-studio-draft'));if(draft&&typeof draft==='object')fill(draft);}catch{/* ignore invalid draft */}
music.init();editor.init();count();refresh();setInterval(refresh,2000);
