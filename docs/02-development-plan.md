# 상세 개발 계획

진행 순서: 기획 검토 → 개발 계획 → Phase 1 구현 → 실측 → 안정화.

## Phase 1 작업 분해

| 순서 | 작업 | 산출물 | 완료 기준 |
|---|---|---|---|
| 1 | 공식 엔진/모델 revision과 다운로드 검증값 확보 | runtime/model lock | 버전·출처·SHA256 기록 |
| 2 | 프로젝트 내부 설치 | runtime/, models/ | 다른 Python·시스템 PATH 변경 없이 CLI help 실행 |
| 3 | Python 표준 라이브러리 CLI | doctor, generate, replay | 입력 검증, 경로 처리, dry-run 가능 |
| 4 | 생성 실행과 이력 저장 | outputs/YYYY-MM-DD/id/ | 성공·실패·타임아웃 상태 및 입력·로그 보존 |
| 5 | GPU 표본 수집, WAV 검사 | metadata.json, gpu.csv | 비어 있지 않은 PCM WAV 확인, 표본 수·측정 범위 표시 |
| 6 | 실패 시나리오 테스트 | unittest | 경로 공백·한글, 잘못된 입력, 엔진 실패, invalid WAV, timeout, 재생성 검증 |
| 7 | RTX 3060 실측 | 실제 영어 음원 및 실행 기록 | CUDA 실행 확인 + WAV 생성 |
| 8 | 한국어/반복/장문 검증 | 검증 보고서 | 반복 3회 및 사용자 청취 결과를 구분해 기록 |

## 설계

Python 표준 라이브러리로 입력·실행·이력을 관리하고 subprocess의 인자 배열로 엔진을 호출한다.
shell 문자열을 조립하지 않는다. 상대 설정 경로는 프로젝트 루트 기준이다.
엔진과 모델은 명시적 구성 파일로 주입한다. 모델 다운로드는 별도 설치 스크립트로 분리한다.
다중 생성은 잠금 파일로 차단하고 예외/중단 시 해제한다. 강제 종료 후 잠금이 남으면 doctor 안내에 따라 PID를 확인한다.

실행 입력: title, style, lyrics, seed, cot(off/full/melody), steps, threads, timeout.
기본값: CUDA, Q4_0 + F16 VAE, cot=off, steps=8, 단일 작업.
짧은 가사를 사용하되 출력 초 길이를 보장하는 임의 옵션은 만들지 않는다.

저장 정보: schema_version, id, status, created_at, title, style, lyrics, seed, engine/model 정보,
실제 argv, elapsed_seconds, returncode, error, audio_path, WAV 속성, GPU 표본 통계.
재생성은 이전 입력/설정을 사용해 새 디렉터리를 만들고 parent_id를 기록한다.
실행 당시 모델 변경 여부는 설치 lock과 실제 파일 해시 검증으로 확인한다.

## 문제 대응

- CUDA 로딩 실패: 배포 DLL·드라이버·CLI 로그를 확인. CPU 성공을 GPU 성공으로 바꾸어 기록하지 않는다.
- OOM: 다른 앱 점유 확인 → 짧은 입력과 Q4 유지 → 지원되는 엔진 옵션을 조사. 자동 무한 재시도 없음.
- Python launcher 실패: 프로젝트 launcher에서 명시적 Python 경로를 선택할 수 있도록 한다.
- 네트워크 차단: 다운로드/실행 실패를 기록하고 준비된 코드와 실측 미완료를 구분한다.
- 곡 잘림·잡음: WAV 파일 유효성과 음악 품질을 분리해 평가한다.

## 후속 단계와 진입 조건

| 단계 | 범위 | 진입 조건 | 검증 |
|---|---|---|---|
| Phase 2 | Figma 기반 단일 사용자 웹 UI, 재생·다운로드·작업 상태 | Phase 1 반복 생성 안정화 | 동시 요청 차단, UI 재접속, 실패 표시 |
| Phase 3 | LLM 곡 기획, 구조화 schema, 사용자 수정 | 생성 파이프라인 안정화 | 장르/BPM/구조 필드 검증; 모델이 보장하지 않는 제어는 힌트로 표시 |
| Phase 4 | 가사 생성·부분 수정·다국어 | 한국어 실측 평가 | 섹션 보존과 사용자 원문 수정 이력 |
| Phase 5 | 계획→가사→생성 작업 오케스트레이션, SQLite 검색 | 각 단계 독립 검증 | 제한된 재시도, 재개·취소·오류 추적 |
| Phase 6 | ABC 악보·멜로디·화성 및 cover 실험 | 모델/API 호환성 검증 | 악보 변경과 청취 결과 비교 |

Phase 2는 Figma 화면을 반영하기 위해 당초 Gradio 대신 Python 표준 라이브러리 서버와 HTML/CSS/JavaScript로 구현했다. 추가 Python 패키지는 필요하지 않다. 실측 및 완료 범위는 03·04 보고서를 참고한다.

한국어 품질을 단일 청취 결과로 일반화하거나 일정·품질 수치를 보장하지 않는다.
각 단계에서 산출물과 미완료 조건을 기록한 다음 다음 단계로 진행한다.
