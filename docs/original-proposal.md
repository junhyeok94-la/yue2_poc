# YuE2 기반 로컬 AI 음악 생성 프로젝트 기획안

## 1. 프로젝트 개요

### 프로젝트명
**Local AI Music Studio**

### 프로젝트 목표
사용자가 자연어로 원하는 음악의 분위기, 장르, 가사 주제 등을 입력하면 AI가 이를 해석하여 가사와 곡 구조를 설계하고, YuE2 기반 음악 생성 모델을 이용해 실제 음원을 생성하는 로컬 AI 음악 생성 시스템을 구축한다.

초기 버전에서는 RTX 3060 12GB 환경에서 안정적으로 음악을 생성하는 것을 우선 목표로 하며, 이후 LLM을 활용한 곡 기획 자동화, 가사 생성, 음악 생성 이력 관리 및 재생성 기능까지 확장한다.

---

# 2. 프로젝트 추진 배경

최근 생성형 AI 기술의 발전으로 음악 이론이나 DAW 사용 경험이 없는 사용자도 자연어만으로 음악을 생성할 수 있게 되었다.

Suno와 같은 서비스형 AI 음악 생성 플랫폼은 접근성과 결과물 품질이 높지만, 모델 내부 처리 과정에 대한 제어와 커스터마이징에는 제한이 있다.

본 프로젝트에서는 오픈 모델인 YuE2를 활용하여 다음과 같은 요소를 직접 실험한다.

- 로컬 GPU 기반 음악 생성
- 음악 생성 모델 추론 구조 이해
- 양자화 모델을 활용한 저사양 GPU 최적화
- LLM과 음악 생성 모델 결합
- 자연어 기반 곡 기획 자동화
- 향후 Melody / Chord / Arrangement 제어 기능 확장

이를 통해 단순히 AI 음악 서비스를 사용하는 수준을 넘어, 직접 AI 음악 생성 파이프라인을 구축하고 개선하는 것을 목표로 한다.

---

# 3. 개발 환경

## Hardware

- GPU: NVIDIA RTX 3060 12GB
- CPU: 로컬 PC CPU 사용
- RAM: 시스템 메모리 활용
- Storage: 모델 및 생성 음원 저장

## Software

- Python
- PyTorch
- CUDA
- YuE2
- GGUF Quantized Model
- audio.cpp 또는 GGUF 지원 추론 엔진
- Hugging Face
- FFmpeg

## 향후 추가 기술

- FastAPI
- Streamlit 또는 Gradio
- SQLite / PostgreSQL
- LLM API 또는 Local LLM
- Docker

---

# 4. 시스템 전체 구조

```text
사용자
  │
  │ 자연어 요청
  ▼
AI Music Planner
  │
  ├─ 장르
  ├─ BPM
  ├─ 분위기
  ├─ 악기 구성
  ├─ 보컬 스타일
  └─ 곡 구조
       │
       ▼
Lyrics Generator
       │
       ▼
Music Prompt Generator
       │
       ▼
YuE2
       │
       ▼
Music Generation
       │
       ▼
WAV / MP3
       │
       ▼
Music Library
```

---

# 5. 주요 기능

## 5.1 자연어 기반 음악 생성

사용자가 자연어로 원하는 음악을 설명한다.

예시

```text
새벽에 혼자 운전하면서 들을 수 있는
조금 우울하지만 너무 어둡지는 않은
한국 R&B 스타일 노래를 만들어줘.

남자 보컬이고
후렴은 기억에 잘 남았으면 좋겠어.
```

AI가 이를 음악 생성에 필요한 구조화된 정보로 변환한다.

예시

```json
{
  "genre": "Korean R&B",
  "mood": ["melancholic", "late-night", "emotional"],
  "tempo": 88,
  "vocal": "male",
  "structure": [
    "Intro",
    "Verse",
    "Pre-Chorus",
    "Chorus",
    "Verse",
    "Chorus",
    "Bridge",
    "Final Chorus"
  ]
}
```

---

# 5.2 AI 가사 생성

곡 분위기와 사용자가 입력한 주제를 기반으로 가사를 자동 생성한다.

사용자는 다음 중 하나를 선택할 수 있다.

- 전체 가사 자동 생성
- 사용자가 직접 작성
- 일부 가사만 입력 후 AI가 확장

예시

```text
주제:
헤어진 사람을 잊었다고 생각했지만
새벽에 문득 떠오르는 감정
```

AI 생성 결과

```text
Verse

아무렇지 않은 하루 끝에서
문득 네 이름이 떠올라
지운 줄 알았던 기억들이
새벽 공기처럼 번져가
```

---

# 5.3 곡 구조 자동 설계

AI가 음악 스타일에 따라 곡 구조를 설계한다.

예시

```text
Intro

Verse 1

Pre-Chorus

Chorus

Verse 2

Chorus

Bridge

Final Chorus

Outro
```

향후에는 사용자가 직접 구조를 수정할 수 있도록 한다.

---

# 5.4 YuE2 음악 생성

생성된 가사와 음악 스타일 Prompt를 YuE2에 전달하여 음악을 생성한다.

RTX 3060 12GB 환경을 고려하여 초기 버전에서는 GGUF 양자화 모델을 활용한다.

예상 구성

```text
YuE2-3B

↓

GGUF Q4 / Q5

↓

RTX 3060 12GB

↓

Audio Generation
```

초기 개발 목표는 품질 극대화보다 **안정적인 생성 성공**에 둔다.

---

# 5.5 생성 음원 관리

생성된 음악의 정보를 저장한다.

예시 데이터

```text
song_id

title

prompt

lyrics

genre

mood

bpm

model

quantization

seed

generation_time

audio_path

created_at
```

사용자는 이전 생성 결과를 확인하고 동일한 설정으로 다시 생성할 수 있다.

---

# 6. 단계별 개발 계획

## Phase 1. YuE2 로컬 음악 생성

### 목표

RTX 3060 12GB 환경에서 YuE2를 이용해 실제 음악 생성에 성공한다.

### 개발 범위

- CUDA 환경 구성
- YuE2 실행 환경 구축
- GGUF 모델 다운로드
- Q4 / Q5 모델 테스트
- 음악 생성 테스트
- VRAM 사용량 측정
- 생성 시간 측정
- 생성 파일 저장

### 완료 기준

```text
Prompt + Lyrics

↓

YuE2

↓

WAV 파일 생성
```

이 단계에서는 UI를 만들지 않는다.

CLI 기반으로 음악 생성 성공 여부에 집중한다.

---

# Phase 2. 음악 생성 인터페이스

### 목표

사용자가 쉽게 음악을 만들 수 있는 UI 제공

### 후보 기술

Streamlit 또는 Gradio

### UI 예시

```text
Music Style

[ Korean R&B ]

Mood

[ Late Night ]
[ Emotional ]

Vocal

[ Male ]

Lyrics

-----------------------
가사 입력
-----------------------

[ Generate Music ]
```

생성 완료 후

```text
▶ Play

Download WAV

Generation Time

GPU Memory Usage
```

등의 정보를 제공한다.

---

# Phase 3. AI Music Planner

LLM을 활용하여 자연어 요청을 음악 생성 Prompt로 자동 변환한다.

예시

사용자 입력

```text
비 오는 날 카페에서 들을 수 있는
조용한 여성 보컬 노래 만들어줘.
```

LLM 출력

```text
Genre:
Lo-fi R&B

Tempo:
76 BPM

Mood:
Rainy
Warm
Calm

Instrument:
Electric Piano
Soft Bass
Brush Drums

Vocal:
Female

Structure:
Intro
Verse
Chorus
Verse
Chorus
Outro
```

이 결과를 YuE2 입력 Prompt로 변환한다.

---

# Phase 4. AI Lyrics Agent

사용자가 음악 주제를 입력하면 LLM이 가사를 생성한다.

Workflow

```text
Topic

↓

Lyrics Planner

↓

Verse / Chorus Structure

↓

Lyrics Generator

↓

YuE2
```

추가적으로 다음 기능을 제공한다.

- 후렴만 다시 생성
- Verse만 수정
- 표현 스타일 변경
- 영어 / 한국어 혼합 가사
- 라임 강화

---

# Phase 5. 음악 생성 Agent

전체 음악 생성 과정을 Agent 형태로 구성한다.

```text
User

↓

Music Agent

↓

Music Planner

↓

Lyrics Agent

↓

Prompt Builder

↓

YuE2

↓

Audio Generator

↓

Quality Check

↓

Music Library
```

사용자는 최종적으로 다음과 같이 요청할 수 있다.

```text
새벽 감성의 한국 R&B 곡 만들어줘.

남자 보컬이고
헤어진 사람을 떠올리는 내용인데
너무 우울하지는 않았으면 좋겠어.

후렴은 중독성 있게 만들어줘.
```

AI가 전체 음악 생성 과정을 자동 처리한다.

---

# 7. 향후 확장 기능

## Melody Control

YuE2가 생성한 멜로디 정보를 수정하여 새로운 곡을 생성한다.

```text
Original Melody

↓

Melody Modification

↓

Music Regeneration
```

---

## Chord Control

동일한 멜로디에 다른 코드 진행을 적용한다.

예

```text
C - G - Am - F
```

에서

```text
Am - F - C - G
```

등으로 변경하여 분위기 차이를 비교한다.

---

## Remix 기능

기존 생성곡을 기반으로 다른 스타일의 음악을 생성한다.

예

```text
R&B

↓

Lo-fi Version

↓

Acoustic Version

↓

Jazz Version
```

---

# 8. 데이터 관리 구조

프로젝트 디렉터리 예시

```text
local-ai-music-studio/

src/

    music_generator/

    lyrics_generator/

    music_planner/

models/

    yue2/

outputs/

    2026-09-23/

        song_001/

            audio.wav

            lyrics.txt

            metadata.json

database/

config/

ui/

tests/
```

---

# 9. 프로젝트 핵심 기술 포인트

본 프로젝트의 핵심은 단순히 AI로 음악을 생성하는 것이 아니라 다음 기술을 직접 경험하는 데 있다.

### Generative AI

LLM과 Audio Generation Model 연결

### Model Inference

로컬 GPU에서 생성형 AI 모델 실행

### Quantization

GGUF Q4 / Q5 등을 활용한 GPU 메모리 최적화

### GPU Optimization

RTX 3060 12GB 환경에서 VRAM 사용 최적화

### AI Agent

여러 AI 모델을 하나의 Workflow로 연결

### AI Pipeline

```text
Natural Language

↓

Structured Music Plan

↓

Lyrics

↓

Music Generation

↓

Audio
```

---

# 10. 최종 목표

최종적으로 사용자가 다음과 같이 자연어로 요청한다.

```text
새벽에 한강 드라이브하면서 들을 만한
90년대 느낌의 R&B 만들어줘.

남자 보컬이고
헤어진 사람을 우연히 다시 만난 내용이면 좋겠어.
```

시스템은 자동으로 다음 과정을 수행한다.

```text
1. 음악 컨셉 분석

2. 장르 / BPM / Mood 결정

3. 곡 구조 생성

4. 가사 생성

5. YuE2 Prompt 생성

6. 음악 생성

7. WAV / MP3 변환

8. 생성 결과 저장
```

최종 결과

```text
Title

Lyrics

Music Specification

Audio

Generation Metadata
```

를 하나의 Music Project 형태로 관리한다.

---

# 11. MVP 정의

본 프로젝트의 첫 번째 완성 버전은 다음 조건을 충족하면 완료로 정의한다.

1. RTX 3060 12GB 환경에서 YuE2 실행

2. GGUF 기반 음악 생성

3. Style Prompt 입력

4. Lyrics 입력

5. WAV 음악 파일 생성

6. 생성 결과 자동 저장

7. 생성 설정 metadata 저장

MVP에서는 LLM Agent와 UI 기능은 필수 기능으로 포함하지 않는다.

---

# 12. 프로젝트 발전 방향

프로젝트는 다음 순서로 발전시킨다.

```text
Phase 1

YuE2 음악 생성

↓

Phase 2

Web UI

↓

Phase 3

AI Music Planner

↓

Phase 4

AI Lyrics Agent

↓

Phase 5

AI Music Agent

↓

Phase 6

Melody / Chord Control
```

초기에는 **“내 컴퓨터에서 AI가 실제 노래 한 곡을 만들어낸다.”** 는 경험을 만드는 데 집중한다.

그 이후 생성 과정의 각 단계를 AI Agent와 자동화 Pipeline으로 발전시킨다.