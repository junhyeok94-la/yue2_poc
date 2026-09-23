# Phase 1 구현 및 장치 검증 보고서

검증일: 2026-09-23. 기획 검토 → 상세 계획 → 구현 순서로 진행했다.

## 완료된 작업ㅈㅈ

- 원본 기획안 보존, 모델 구성·환경 요구사항·한국어 검증 조건 수정.
- 단계별 산출물·실패 대응·완료 기준을 포함한 개발 계획 작성.
- 프로젝트 내부에 공식 audio.cpp 0.8.1 CUDA 12.4 배포와 별도 CUDA runtime 설치.
- YuE2 Q4_0 본체, F16 VAE, sidecar 4개 다운로드 및 배포자 해시 확인.
- doctor / generate / replay / dry-run CLI, 파일 기반 이력, GPU 표본, 실패·취소·타임아웃 처리 구현.
- 검증 테스트 11개 통과. 실제 하위 프로세스 실패와 타임아웃 종료도 포함한다.

## 환경과 고정 버전

- Windows, Intel Core i5-8500, RAM 약 32GiB.
- RTX 3060 12288 MiB, 드라이버 610.88, compute capability 8.6.
- audio.cpp 0.8.1, 배포 바이너리 `--version`의 git `f2b4937`, cpu/cuda backend.
- 모델 revision: `f7cb0712b9c2e5e9dcadc8b3ab23a591756c131b`.
- Python 3.12.14. 기존 시스템 Python launcher 실패로 Codex 번들 Python 사용.
- PyTorch·FFmpeg·CUDA Toolkit을 추가로 설치하지 않았다.

## 실제 실행 결과

모든 성공 실행은 CUDA backend 및 CUDA graph 로그를 확인했다.
출력은 PCM16, 48000Hz, stereo이며 프레임 검사에서 누락/빈 파일이 없었다.
원시 측정 및 파일 해시는 [validation-results.json](validation-results.json)에 있다.

| 실행 ID | 입력 / 모드 | 음원 길이 | 전체 실행 | 장치 VRAM 표본 최대 |
|---|---|---:|---:|---:|
| 213622-7eb487ea | 영어 짧은 가사 / off | 71.64초 | 67.28초 | 5301 MiB |
| 213921-5fbd0c62 | 동일 설정 재생성 / off | 71.64초 | 66.94초 | 5201 MiB |
| 214028-f37ac422 | 동일 설정 재생성 / off | 71.64초 | 63.67초 | 5196 MiB |
| 213825-7e754352 | 한국어 짧은 가사 / off | 49.80초 | 48.97초 | 5162 MiB |
| 214148-120832df | 영어 긴 가사 / full | 212.92초 | 126.69초 | 7384 MiB |

전체 실행 시간에는 모델 해시 검사와 엔진 시작이 포함된다. VRAM은 약 1초 간격의
장치 전체 사용량으로 다른 앱을 포함하며 정확한 순간 최고치나 프로세스 전용 값이 아니다.

동일 영어 설정의 3회 생성 WAV SHA256이 모두 일치했다.
이는 이 환경의 관측 결과이며 다른 장치·엔진 버전까지 동일성을 보장하지 않는다.
한국어 입력은 UTF-8 파일로 보존되며, 공식 Windows CLI의 wmain → UTF-8 변환도 소스에서 확인했다.

긴 가사 실행은 3분 33초 길이 WAV를 생성했다. 엔진 로그의 `yue2.semantic.abc_truncated`와
`yue2.semantic.truncated`는 모두 0이다. 이는 토큰 상한으로 잘렸다는 표시가 없다는 뜻이며
모든 가사가 실제로 노래되었거나 음악적으로 자연스럽게 끝난다는 청취 판정은 아니다.
엔진은 score artifact 2086 bytes도 보고했다. 현재 CLI는 이 악보를 별도 파일로 내보내지 않는다.

## 청취 평가와 남은 검증

자동 검사는 파일 형식·비어 있지 않은 PCM 신호·실행 상태만 확인한다.
보컬 발음, 한국어 가사 일치도, 음악적 자연스러움, 잡음, 의도한 곡 종료는 아직 청취 평가 전이다.
짧은 영어 출력은 PCM 최대치 32767에 도달해, 청취 시 왜곡도 확인해야 한다.
최대치 도달만으로 왜곡이 들린다고 단정하지 않는다.

| 청취 항목 | 영어 | 한국어 |
|---|---|---|
| 보컬·반주가 의도한 스타일에 가까운가 | 미평가 | 미평가 |
| 입력 가사와 발음이 일치하는가 | 미평가 | 미평가 |
| 잡음·왜곡·갑작스러운 종료가 없는가 | 미평가 | 미평가 |
| 결과를 후속 UI 개발의 기준 샘플로 쓸 수 있는가 | 미평가 | 미평가 |

현재 상태는 **CLI 구현 완료 + CUDA 생성 총 5회 성공 + 짧은 영어 설정 반복 3회 성공 + 긴 곡/full 모드 성공**이다.
청취 평가 전이므로 Phase 1의 전체 품질 안정화를 완료했다고 표시하지 않는다.
Q8 비교는 필수 MVP 범위가 아니며 아직 실행하지 않았다.

## 재실행

프로젝트 루트에서:

```powershell
.\studio.ps1 doctor
.\studio.ps1 replay outputs/2026-09-23/213622-7eb487ea/metadata.json
.\studio.ps1 generate --title '긴 곡 테스트' --style 'English, mellow R&B, warm male vocal, electric piano, soft bass, gentle drums' --lyrics-file examples/lyrics-en-long.txt --cot full --timeout 900
```

실행 입력·로그는 outputs에, 엔진/모델 출처와 검증값은 config/downloads.lock.json에 남겼다.
outputs·models·runtime은 Git 제외 대상이다. 별도로 백업하지 않으면 저장소만으로 음원을 복구할 수 없다.
