"use strict";
class MusicGuide {
  constructor(api,onChange){
    this.api=api;this.onChange=onChange;this.revision=0;this.items=[];this.pending=false;this.configured=false;
    this.fields=['genre','bpm','key','moods','vocal','instruments'];
    document.getElementById('music-advise').onclick=()=>this.advise();
  }
  settings(){
    const result={advanced_prompt:document.getElementById('style').value.trim()};
    for(const field of this.fields){
      const value=document.getElementById('music-'+field).value.trim();if(!value)continue;
      result[field]=field==='bpm'?Number(value):['moods','instruments'].includes(field)?value.split(',').map(v=>v.trim()):value;
    }
    return result;
  }
  style(){
    const settings=this.settings(),parts=[];
    for(const field of this.fields){const value=settings[field];if(value===undefined)continue;parts.push(Array.isArray(value)?value.join(', '):String(value)+(field==='bpm'?' BPM':''));}
    if(settings.advanced_prompt)parts.push(settings.advanced_prompt);
    return parts.join(', ');
  }
  load(data){
    const settings=data.song?.music_settings||data.music_settings||{};
    for(const field of this.fields){const value=settings[field];document.getElementById('music-'+field).value=Array.isArray(value)?value.join(', '):value??'';}
    if(settings.advanced_prompt!==undefined)document.getElementById('style').value=settings.advanced_prompt;
    this.changed();
  }
  async init(){
    try{
      const config=await this.api('/api/music/guide');
      for(const field of config.fields){
        document.getElementById('why-'+field.id).textContent=field.description;
        const list=document.getElementById('options-'+field.id);if(!list)continue;
        for(const value of field.options){const option=document.createElement('option');option.value=value;list.append(option);}
      }
      const status=await this.api('/api/advisor');this.configured=status.configured;
      document.getElementById('music-ai-status').textContent=status.configured?'현재 음악 설정과 곡 제목을 Gemini에 보내 조언을 받습니다.':'AI 조언을 사용하려면 서버의 Gemini API 키를 설정하세요.';
      this.paint();
    }catch(e){document.getElementById('music-error').textContent=e.message;}
    this.preview();
  }
  changed(){this.revision++;this.paint();clearTimeout(this.timer);this.timer=setTimeout(()=>this.preview(),250);}
  async preview(){
    const revision=this.revision;
    try{const result=await this.api('/api/music/preview',{music_settings:this.settings()});if(revision!==this.revision)return;
      document.getElementById('style-preview').textContent=result.style||'설정을 선택하거나 자유 입력을 작성하세요.';document.getElementById('music-error').textContent='';
    }catch(e){if(revision===this.revision){document.getElementById('music-error').textContent=e.message;document.getElementById('style-preview').textContent='음악 설정을 확인해 주세요.';}}
  }
  async advise(){
    if(this.pending||!this.configured)return;
    this.pending=true;this.items=[];this.batchRevision=this.revision;this.paint();document.getElementById('music-advice-status').textContent='설정을 검토하고 있습니다…';
    try{const result=await this.api('/api/music/advice',{music_settings:this.settings(),title:document.getElementById('title').value.trim()});
      this.items=result.suggestions;document.getElementById('music-advice-status').textContent=this.batchRevision!==this.revision?'요청 후 설정이 바뀌었습니다. 다시 조언을 요청하세요.':this.items.length?'적용할 항목을 직접 선택하세요.':'현재 설정에 추가 제안이 없습니다.';
    }catch(e){document.getElementById('music-advice-status').textContent=e.message;}
    finally{this.pending=false;this.paint();}
  }
  paint(){
    document.getElementById('music-advise').disabled=this.pending||!this.configured;
    const host=document.getElementById('music-suggestions');host.replaceChildren();
    for(const item of this.items){
      const card=document.createElement('article');card.className='music-suggestion';
      const heading=document.createElement('strong');heading.textContent=document.querySelector('label[for="music-'+item.field+'"]').textContent;card.append(heading);
      for(const text of ['원래 값: '+(item.original||'미정'),'제안: '+item.suggested,'왜? '+item.reason]){const p=document.createElement('p');p.textContent=text;card.append(p);}
      const apply=document.createElement('button');apply.type='button';apply.className='quiet-button';apply.textContent='적용';apply.disabled=this.batchRevision!==this.revision;
      apply.onclick=()=>{if(this.batchRevision!==this.revision)return;document.getElementById('music-'+item.field).value=item.suggested;this.items=this.items.filter(x=>x.id!==item.id);this.batchRevision=this.revision+1;this.changed();this.onChange();document.getElementById('music-advice-status').textContent='선택한 제안을 적용했습니다.';};
      const ignore=document.createElement('button');ignore.type='button';ignore.className='quiet-button';ignore.textContent='무시';ignore.onclick=()=>{this.items=this.items.filter(x=>x.id!==item.id);this.paint();};
      card.append(apply,ignore);host.append(card);
    }
  }
}

window.MusicGuide=MusicGuide;
