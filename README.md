# Local AI Music Studio

Windows / RTX 3060 12GB에서 YuE2 GGUF를 실행하는 로컬 음악 생성 웹 스튜디오와 CLI.
Python은 실행·이력 관리에만 사용하고 실제 추론은 audio.cpp CUDA가 수행합니다.

## v0.6 Song Versions

라이브러리에서 곡을 선택하고 “이 곡에서 새 버전”으로 Variation·Lyrics Revision·Remix를 만들 수 있습니다.
같은 곡의 버전들을 묶어 보여주며 부모 관계, 가사·설정 차이, 기준/선택 버전 듣기를 지원합니다.
[사용법·저장 방식·검증 결과](docs/09-v0.6-song-versions.md).

## v0.5 Music Guide

BPM·Key·Genre·Mood·Vocal·Instruments를 선택하고 각 설정의 “왜?” 설명을 볼 수 있습니다.
자유 입력과 합쳐진 YuE2 스타일을 미리 확인하며, Gemini 조언은 사용자가 선택한 항목만 적용합니다.
[사용법·데이터/API·검증 결과](docs/08-v0.5-music-guide.md).

## v0.4 Gemini AI Lyrics Assistant

Section 카드에서 가사 검토·다음 행 제안을 요청하고 직접 적용하거나 무시할 수 있습니다.
서버 .env에 GEMINI_API_KEY를 설정하세요. [설정·사용법·검증 결과](docs/06-v0.4-gemini.md).

## v0.3 Song Structure & Lyrics Workshop

Section별 가사·마디 수 편집, 순서 변경, 분석과 가이드를 지원합니다.
[사용법·호환성·검증 결과](docs/05-v0.3-workshop.md)를 확인하세요.

라이브러리에서 곡의 이름을 바꾸거나 휴지통으로 삭제·복원할 수 있습니다.
[곡 관리 안내](docs/07-library-management.md).

## 웹 스튜디오 실행

```powershell
.\web-studio.ps1
```

[로컬 스튜디오](http://127.0.0.1:7860)를 열어 스타일·가사를 입력하고 음악을 만드세요.
라이브러리 검색, 재생, WAV 다운로드, 설정 재사용과 재생성을 지원합니다.
생성 중 브라우저를 닫거나 새로고침해도 서버가 실행 중이면 작업이 계속됩니다.

- [Phase 2 실행 및 검증 안내](docs/04-web-studio.md)
- [Figma 화면 설계](https://www.figma.com/design/gKvtbRwlaaDLsVJRsuWKPe?node-id=3-9)

- [검토·수정 기획안](docs/01-reviewed-proposal.md)
- [상세 개발 계획](docs/02-development-plan.md)
- [실제 장치 검증 보고서](docs/03-validation-report.md)
- [원본 기획안](docs/original-proposal.md)

## 준비

Python 3.11 이상과 NVIDIA 드라이버가 필요합니다. Python 패키지 설치는 없습니다.
프로젝트 루트에서 실행하세요. 약 4GB를 내려받으며 압축 해제에 추가 공간이 필요합니다.

```powershell
python scripts/install_runtime.py
python studio.py doctor
```

설치 스크립트는 공식 v0.8.1 CUDA 12.4 바이너리·CUDA runtime과 고정된 모델 revision을
프로젝트 안에 설치하고 배포자 해시를 검증합니다. 시스템 PATH는 변경하지 않습니다.
이 PC에서는 기본 Python launcher가 실패하여 `studio.ps1`이 확인된 Codex 번들 Python을
사용합니다. 다른 환경에서는 `$env:MUSIC_STUDIO_PYTHON`으로 Python 실행 파일을 지정하거나
`python studio.py`를 직접 사용하세요.

## 생성

```powershell
.\studio.ps1 doctor
.\studio.ps1 generate --title 'River Lights' --style 'English, mellow R&B, warm male vocal, electric piano, soft bass, gentle drums' --lyrics-file examples/lyrics-en.txt
.\studio.ps1 generate --title '새벽의 강' --style 'Korean, mellow R&B, warm male vocal, electric piano, soft bass, gentle drums' --lyrics-file examples/lyrics-ko.txt
```

한국어 발음과 가사 일치도는 검증 대상입니다. Style의 BPM·장르 등은 조건 힌트이며
정확히 지켜진다고 보장하지 않습니다. `--seed`, `--steps`, `--cot off|full|melody`,
`--threads`, `--timeout`을 지정할 수 있습니다. 기본 제한 시간은 1800초입니다.
현재 CLI는 ABC 입력을 받지 않으며 `cot`는 모델 내부 계획 모드입니다.

설치 전에도 실행 인자만 확인할 수 있습니다.

```powershell
.\studio.ps1 --config config/example.json generate --style 'English, R&B' --lyrics-file examples/lyrics-en.txt --dry-run
.\studio.ps1 replay outputs/2026-09-23/<run-id>/metadata.json
```

재생성은 기존 파일을 덮어쓰지 않고 원래 입력과 설정으로 새 결과를 만듭니다.
현재 설치된 파일의 해시는 매 생성마다 기록되며 고정 모델 파일은 lock 해시와 비교합니다.
엔진 파일 해시는 이력에 보존하지만 다른 하드웨어에서 동일 WAV를 보장하지 않습니다.

## 결과와 실패 처리

`outputs/YYYY-MM-DD/<run-id>/`에 `audio.wav`, `metadata.json`, `lyrics.txt`, `style.txt`,
`engine.log`, `gpu.csv`를 저장합니다. 성공 종료와 WAV 프레임 검사를 모두 통과해야
`succeeded`가 됩니다. 파일 검사와 음악 품질은 다르며 청취 평가는 별도입니다.
GPU 수치는 약 1초 간격의 장치 전체 사용량으로, 다른 앱도 포함되고 순간 최고치는 놓칠 수 있습니다.

실패한 작업은 `failed`, 제한 시간 초과는 `timed_out`, Ctrl+C는 `cancelled`로 기록합니다.
종료 코드는 성공 0, 생성 실패 1, 입력·환경 오류 2입니다.
동시에 한 작업만 실행합니다. 강제 프로세스 종료 후 잠금이 남았다면
`outputs/.generation.lock`에 적힌 PID가 종료되었는지 확인한 후 해당 잠금 파일만 삭제하세요.
진행 로그는 실행 폴더의 `engine.log`에서 확인할 수 있습니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```

유닛 테스트는 가짜 엔진으로 저장·실패 처리 계약을 검사합니다. 실제 AI 생성 성공의 증거가 아닙니다.
실제 장치 검증은 별도의 생성 결과와 검증 보고서를 확인하세요.

모델은 [CC-BY-NC-4.0](https://huggingface.co/m-a-p/YuE2-3B)로 표시되어 있습니다.
설치 출처는 [audio.cpp](https://github.com/0xShug0/audio.cpp/releases/tag/v0.8.1)와
[audio-cpp/Yue2-3B-GGUF](https://huggingface.co/audio-cpp/Yue2-3B-GGUF)입니다.
