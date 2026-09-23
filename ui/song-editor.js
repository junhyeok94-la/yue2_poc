'use strict';
(function(root){
const copy = value => JSON.parse(JSON.stringify(value));
function moveSection(sections, id, delta) {
  const next=copy(sections), index=next.findIndex(s=>s.id===id), target=index+delta;
  if(index<0||target<0||target>=next.length)return next;
  [next[index],next[target]]=[next[target],next[index]];return next;
}
function removeSection(sections,id){return sections.filter(s=>s.id!==id).map(copy);}
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
class SongEditor {
  constructor(onChange, api){
    this.advice=new Map();this.aiBusy=false;this.aiConfigured=false;this.onChange=onChange;this.api=api;this.sections=[];this.mode='sections';this.types=[];
    this.revision=0;this.timer=null;this.removed=null;this.composing=false;this.pending=null;
    this.host=document.getElementById('section-cards');this.raw=document.getElementById('raw-lyrics');
    this.preview=document.getElementById('compiled-preview');
    document.getElementById('add-section').onclick=()=>this.add();
    document.getElementById('undo-section').onclick=()=>this.undo();
    document.getElementById('raw-mode').onclick=()=>this.toRaw();
    document.getElementById('section-mode').onclick=()=>this.fromRaw();
    document.getElementById('apply-import').onclick=()=>{if(!this.pending)return;this.sections=this.pending;this.pending=null;this.mode='sections';this.removed=null;this.render();this.changed();document.getElementById('import-dialog').close();};
    document.getElementById('cancel-import').onclick=()=>document.getElementById('import-dialog').close();
    this.host.addEventListener('compositionstart',()=>{this.composing=true;});
    this.host.addEventListener('compositionend',()=>{this.composing=false;this.changed();});
  }
  async init(){
    try{const config=await this.api('/api/workshop');this.types=config.types;
      document.getElementById('structure-notice').textContent=config.notice;
      const select=document.getElementById('new-section-type');select.replaceChildren();
      for(const t of this.types){const option=node('option',t.label);option.value=t.type;select.append(option);}
      select.value='verse';document.getElementById('add-section').disabled=false;
      this.render();this.schedule();
      try{const status=await this.api('/api/advisor');this.aiConfigured=status.configured;this.aiModel=status.model;this.paintAdvice();}catch{this.aiConfigured=false;this.paintAdvice();}
    }catch(e){document.getElementById('editor-error').textContent='가이드 연결 실패: '+e.message;}
  }
  song(){return {schema_version:2,title:document.getElementById('title').value.trim(),sections:copy(this.sections),music_settings:{advanced_prompt:document.getElementById('style').value.trim()}};}
  draft(){return {mode:this.mode,sections:copy(this.sections),raw:document.getElementById('lyrics').value};}
  load(data){
    this.revision++;this.advice.clear();clearTimeout(this.timer);this.removed=null;
    if(data.editor && (!Array.isArray(data.editor.sections) || data.editor.sections.length>64 || !data.editor.sections.every(s=>s && typeof s.id==='string' && typeof s.type==='string' && typeof s.label==='string' && Array.isArray(s.lyrics) && s.lyrics.every(l=>typeof l==='string'))))throw new Error('저장된 편집 초안 형식이 잘못됐습니다.');
    if(data.editor){this.mode=data.editor.mode==='raw'?'raw':'sections';this.sections=copy(data.editor.sections||[]);document.getElementById('lyrics').value=data.editor.raw||'';}
    else if(data.song){this.sections=copy(data.song.sections);this.mode='sections';}
    else {this.mode='raw';this.sections=[];if(data.lyrics!==undefined)document.getElementById('lyrics').value=data.lyrics;}
    this.render();this.schedule();
  }
  changed(){this.revision++;this.paintAdvice();if(!this.composing){this.onChange();this.schedule();}}
  schedule(){clearTimeout(this.timer);this.timer=setTimeout(()=>this.analyze(),300);}
  async analyze(){
    const revision=this.revision;
    if(this.mode==='raw'){const value=document.getElementById('lyrics').value;this.preview.textContent=value;document.getElementById('compile-count').textContent=value.length+' / 12,000';return;}
    try {const result=await this.api('/api/song/preview',{song:this.song()});if(revision!==this.revision||this.mode!=='sections')return;
      document.getElementById('editor-error').textContent='';this.preview.textContent=result.compiled_lyrics||'가사가 있는 Section을 작성해 주세요.';
      document.getElementById('compile-count').textContent=result.compiled_lyrics.length+' / 12,000';
      document.getElementById('compile-warnings').textContent=result.warnings.map(w=>{const s=this.sections.find(s=>s.id===w.section_id);return (s?.label||'Section')+': '+w.message;}).join('\n');
      for(const a of result.analysis){const card=Array.from(this.host.children).find(n=>n.dataset.id===a.section_id);if(!card)continue;
        card.querySelector('.analysis-summary').textContent=a.lines_count+'행 · '+a.characters_count+'자 · '+(a.average_syllables===null?'한글 음절 집계 없음':'한글 평균 약 '+a.average_syllables+'음절/행');
        card.querySelector('.analysis-detail').textContent='행별 한글 음절 근사: '+a.approximate_syllables_per_line.map(x=>x===null?'—':x).join(' / ')+'\n빈 행: '+a.empty_lines+' · 행 길이: '+a.line_length_variation.min+'~'+a.line_length_variation.max+'자 · 표준편차 '+a.line_length_variation.stddev+'\n반복 단어: '+(a.repeated_words.map(w=>w.word+' ×'+w.count).join(', ')||'없음');
      }
    }catch(e){if(revision===this.revision){document.getElementById('editor-error').textContent=e.message;this.preview.textContent='입력을 확인해 주세요.';}}
  }
  render(){
    this.host.replaceChildren();this.raw.hidden=this.mode!=='raw';
    document.getElementById('structured-editor').hidden=this.mode!=='sections';
    document.getElementById('raw-mode').setAttribute('aria-pressed',String(this.mode==='raw'));
    document.getElementById('section-mode').setAttribute('aria-pressed',String(this.mode==='sections'));
    document.getElementById('lyrics').required=this.mode==='raw';
    document.getElementById('undo-section').hidden=!this.removed;
    document.getElementById('editor-error').textContent='';document.getElementById('compile-warnings').textContent='';
    if(!this.sections.length)this.host.append(node('p','Section을 추가해 곡의 구성을 직접 정해 보세요.','empty'));
    for(const [index,s] of this.sections.entries()){
      const card=node('section',undefined,'song-section');card.dataset.id=s.id;
      const row=node('div',undefined,'section-fields');
      const field=(label,control)=>{const wrap=node('label',label);wrap.append(control);return wrap;};
      const type=node('select');type.setAttribute('aria-label',(index+1)+'번 Section 타입');
      for(const t of this.types){const o=node('option',t.label);o.value=t.type;type.append(o);}type.value=s.type;
      type.onchange=()=>{s.type=type.value;this.changed();this.render();};
      const label=node('input');label.value=s.label;label.maxLength=80;label.setAttribute('aria-label',(index+1)+'번 Section 이름');label.oninput=()=>{s.label=label.value;this.changed();};
      const bars=node('input');bars.type='number';bars.min=1;bars.max=128;bars.placeholder='미정';bars.value=s.bars??'';bars.setAttribute('aria-label',(index+1)+'번 Section 마디 수');
      bars.oninput=()=>{s.bars=bars.value===''?null:Number(bars.value);this.changed();};
      row.append(field('타입',type),field('이름',label),field('마디 수',bars));card.append(row);
      const lyrics=node('textarea');lyrics.rows=5;lyrics.maxLength=12000;lyrics.value=s.lyrics.join('\n');lyrics.setAttribute('aria-label',(index+1)+'번 Section 가사');lyrics.placeholder='이 구간의 가사를 입력하세요.';
      lyrics.oninput=()=>{s.lyrics=lyrics.value===''?[]:lyrics.value.replace(/\r\n?/g,'\n').split('\n');this.changed();};card.append(lyrics);
      card.append(node('p','분석 준비 중…','analysis-summary'));
      const details=node('details');details.append(node('summary','가사 분석'));details.append(node('pre','','analysis-detail'));details.append(node('p','한글 완성형 글자 수의 근사치입니다. 영어·숫자는 세지 않으며 실제 가창 음절과 다를 수 있습니다.','field-foot'));card.append(details);
      const guide=node('details');guide.append(node('summary','Guide · 왜?'));
      const info=this.types.find(t=>t.type===s.type);guide.append(node('p',info?.description||'가이드를 불러오는 중입니다.'));
      for(const opt of info?.options||[]){const item=node('div',undefined,'guide-option');const choose=node('button',opt.bars+' bars','quiet-button');choose.type='button';choose.onclick=()=>{s.bars=opt.bars;bars.value=opt.bars;this.changed();};item.append(choose,node('span',opt.reason));guide.append(item);}
      card.append(guide);
      const assistant=node('section',undefined,'ai-assistant');assistant.append(node('h4','AI Lyrics Assistant'));
      assistant.append(node('p','요청하면 이 Section의 가사·구조와 곡 제목·스타일이 Google Gemini로 전송됩니다. 자동 적용하지 않습니다.','field-foot'));
      const aiActions=node('div',undefined,'section-actions');
      for(const [action,title] of [['review','가사 검토'],['rhyme','라임 검토'],['hook','Hook 강화'],['suggest','다음 1~2줄 제안']]){
        const button=node('button',title,'quiet-button ai-request');button.type='button';button.dataset.action=action;
        button.onclick=()=>this.askAdvice(s.id,action);aiActions.append(button);
      }
      assistant.append(node('p','라임: 행 사이의 소리 연결 · Hook: 기억에 남는 핵심 구절. 제안은 각각 원문 기준이며 직접 선택해 적용합니다.','field-foot'));
      assistant.append(aiActions,node('p','','ai-status'),node('div',undefined,'advice-list'));card.append(assistant);
      const actions=node('div',undefined,'section-actions');
      for(const [text,delta] of [['↑ 위로',-1],['↓ 아래로',1]]){const b=node('button',text,'quiet-button');b.type='button';b.disabled=index+delta<0||index+delta>=this.sections.length;b.setAttribute('aria-label',(index+1)+'번 Section '+text);
        b.onclick=()=>{this.sections=moveSection(this.sections,s.id,delta);this.render();this.changed();const c=Array.from(this.host.children).find(n=>n.dataset.id===s.id);c?.querySelector('textarea').focus();};actions.append(b);}
      const del=node('button','삭제','quiet-button');del.type='button';del.setAttribute('aria-label',(index+1)+'번 Section 삭제');del.onclick=()=>{this.removed={section:copy(s),index};this.sections=removeSection(this.sections,s.id);this.render();this.changed();document.getElementById('undo-section').focus();};actions.append(del);card.append(actions);this.host.append(card);
    }
    this.paintAdvice();
  }
  paintAdvice(){
    for(const card of this.host.querySelectorAll('.song-section')){
      const entry=this.advice.get(card.dataset.id);
      const status=card.querySelector('.ai-status');if(!status)continue;
      for(const b of card.querySelectorAll('.ai-request'))b.disabled=this.aiBusy||!this.aiConfigured;
      status.textContent=entry?.loading?'Gemini가 검토 중입니다…':entry?.error||entry?.message||(!this.aiConfigured?'Gemini 키 설정 후 서버를 재시작해 주세요.':entry?.items?.length===0?'추가 수정 제안이 없습니다.':this.aiModel||'');
      const list=card.querySelector('.advice-list');list.replaceChildren();
      for(const item of entry?.items||[]){
        const box=node('article',undefined,'suggestion');
        const kind={expression:'표현',syllable_balance:'음절 균형',rhyme:'라임',hook:'Hook 강화',idea:'아이디어'}[item.type]||'제안';
        box.append(node('span',kind,'mini-label'));
        box.append(node('strong',entry.action==='suggest'?'다음 행 추가':(item.line_index+1)+'행 수정'));
        for(const [label,value] of [['원문',item.original||'(Section 끝에 추가)'],['제안',item.suggested],['이유',item.reason]])box.append(node('h5',label),node('p',value));
        const stale=!this.canApplyAdvice(card.dataset.id,item,entry);
        if(stale)box.append(node('p','대상 원문이 변경됐거나 같은 행의 다른 제안을 적용했습니다. 다시 검토해 주세요.','stale-advice'));
        const apply=node('button','적용','quiet-button');apply.type='button';apply.disabled=stale;
        apply.onclick=()=>this.applyAdvice(card.dataset.id,item,entry);
        const ignore=node('button','무시','quiet-button');ignore.type='button';ignore.onclick=()=>{entry.items=entry.items.filter(x=>x.id!==item.id);this.paintAdvice();};
        box.append(apply,ignore);list.append(box);
      }
    }
  }
  async askAdvice(id,action){
    if(this.aiBusy||!this.aiConfigured)return;
    const section=this.sections.find(s=>s.id===id);if(!section)return;
    const entry={revision:this.revision,action,items:[],loading:true};this.advice.set(id,entry);this.aiBusy=true;this.paintAdvice();
    try{
      const response=await this.api('/api/advisor',{action,section:copy(section),context:{title:document.getElementById('title').value.trim(),style:document.getElementById('style').value.trim()}});
      entry.items=response.suggestions;
    }catch(e){entry.error=e.message;}
    finally{entry.loading=false;this.aiBusy=false;this.paintAdvice();}
  }
  canApplyAdvice(id,item,entry){
    const section=this.sections.find(s=>s.id===id);
    if(!section||this.mode!=='sections'||this.composing||this.advice.get(id)!==entry||entry.revision!==this.revision)return false;
    if(!entry.items.some(value=>value.id===item.id))return false;
    return entry.action==='suggest'
      ? item.line_index===section.lyrics.length&&item.original===''
      : section.lyrics[item.line_index]===item.original;
  }
  applyAdvice(id,item,entry){
    if(!this.canApplyAdvice(id,item,entry)){this.paintAdvice();return;}
    const section=this.sections.find(s=>s.id===id);
    if(entry.action!=='suggest')section.lyrics[item.line_index]=item.suggested;
    else section.lyrics.push(...item.suggested.split('\n'));
    entry.items=entry.items.filter(x=>x.id!==item.id);
    // Only this accepted batch advances. Manual edits and other pending requests
    // retain their older revision; same-line alternatives fail the source check.
    entry.revision=this.revision+1;
    entry.message=entry.action==='suggest'?'새 가사를 끝에 추가했습니다.':(item.line_index+1)+'행에 제안을 적용했습니다.';
    const card=Array.from(this.host.children).find(n=>n.dataset.id===id);
    const area=card?.querySelector('textarea');
    if(area){
      const scroll=area.scrollTop;
      area.value=section.lyrics.join('\n');
      const start=section.lyrics.slice(0,item.line_index).reduce((sum,line)=>sum+line.length+1,0);
      area.setSelectionRange(start,start+item.suggested.length);
      area.scrollTop=scroll;
    }
    this.changed();
  }
  add(){
    if(this.sections.length>=64){document.getElementById('editor-error').textContent='Section은 최대 64개입니다.';return;}
    const type=document.getElementById('new-section-type').value, label=this.types.find(t=>t.type===type)?.label||type;
    this.sections.push({id:crypto.randomUUID(),type,label,bars:null,lyrics:[]});this.render();this.changed();this.host.lastElementChild.querySelector('textarea').focus();
  }
  undo(){if(!this.removed)return;if(this.sections.length>=64){document.getElementById('editor-error').textContent='Section을 하나 지운 뒤 복구하세요. 최대 64개입니다.';return;}this.sections.splice(Math.min(this.removed.index,this.sections.length),0,this.removed.section);this.removed=null;this.render();this.changed();}
  async toRaw(){
    if(this.mode==='raw')return;
    try{const revision=this.revision;const result=await this.api('/api/song/preview',{song:this.song()});if(revision!==this.revision)return;if(!confirm('컴파일 가사를 원문 편집기로 가져올까요? 마디 수 등 구조 정보는 원문에 포함되지 않습니다.'))return;
      document.getElementById('lyrics').value=result.compiled_lyrics;this.mode='raw';this.render();this.changed();
    }catch(e){document.getElementById('editor-error').textContent=e.message;}
  }
  async fromRaw(){
    if(this.mode==='sections')return;
    try{const revision=this.revision;const result=await this.api('/api/song/import',{lyrics:document.getElementById('lyrics').value});
      const song=this.song();song.sections=result.sections;const preview=await this.api('/api/song/preview',{song});if(revision!==this.revision)return;this.pending=result.sections;
      document.getElementById('import-preview').textContent=preview.compiled_lyrics+'\n\n'+preview.warnings.map(w=>w.message).join('\n');document.getElementById('import-dialog').showModal();
    }catch(e){document.getElementById('editor-error').textContent=e.message;}
  }
}
if(typeof module!=='undefined'&&module.exports)module.exports={moveSection,removeSection};else root.SongEditor=SongEditor;
})(typeof window==='undefined'?{}:window);
