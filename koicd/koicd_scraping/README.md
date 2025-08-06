# KOICD 건강보험 수가코드 스크래핑 프로젝트

## 📁 파일 구성

### 🚀 메인 스크래핑 스크립트
- **`koicd_complete_scraper.py`** - 완전한 계층구조 수집 스크래퍼 (최신 버전)
- **`koicd_suga_playwright.py`** - 초기 Playwright 기반 스크래퍼
- **`koicd_page_test.py`** - 페이지 로딩 및 기본 요소 테스트

### 🔍 디버깅 도구
- **`debug_koicd_structure.py`** - 페이지 구조 상세 분석 도구
- **`test_single_row_toggle.py`** - 단일 행 토글 기능 집중 테스트

### 📊 분석 자료
- **`koicd_analysis_result.json`** - 페이지 테이블 구조 분석 결과
- **`koicd_initial_state.png`** - 초기 페이지 상태 스크린샷
- **`koicd_final_state.png`** - 로딩 완료 후 페이지 상태 스크린샷
- **`koicd_error_screenshot.png`** - 오류 발생 시 스크린샷

### 🧪 실험 코드
- **`koicd_suga_play_test.py`** - 초기 실험용 테스트 코드
- **`koicd_suga_selenium.ipynb`** - Selenium 기반 실험 노트북

## 🎯 주요 기능

### 기본 데이터 수집
- 건강보험 수가코드 및 행위명 추출
- 상세 정보 팝업에서 추가 데이터 수집
- 페이지네이션을 통한 전체 데이터 순회

### 계층구조 수집 (개발 중단)
- 메인 항목과 하위 항목 구분
- 토글 버튼 감지 및 하위 행 펼치기
- parent_code, child_code, hierarchy_level 정보 추가

### 안정성 보장
- 다중 셀렉터 시도로 견고한 요소 탐지
- 에러 처리 및 재시도 로직
- 서버 부하 방지를 위한 적절한 대기시간

## 🔧 사용법

### 메인 스크래핑 실행
```bash
python koicd_complete_scraper.py
```

### 페이지 구조 분석
```bash
python debug_koicd_structure.py
```

### 단일 행 토글 테스트
```bash
python test_single_row_toggle.py
```

## 📋 데이터 출력 형식

### CSV 컬럼 구조
```
parent_code, child_code, hierarchy_level, is_parent,
수가코드, 행위명_기본, 분류코드, 분류단계,
행위명(한글), 행위명(영문), 산정명,
수술여부, 상대가치점수, 본인부담률, 급여여부,
페이지, 수집일시
```

### JSON 구조
```json
{
  "parent_code": "AA100",
  "child_code": "AA101",
  "hierarchy_level": 1,
  "is_parent": false,
  "수가코드": "AA101",
  "행위명_기본": "초진진찰료",
  "분류코드": "AA",
  "분류단계": "2",
  "페이지": 1,
  "수집일시": "2025-01-08T..."
}
```

## ⚠️ 알려진 제한사항

1. **하위 항목 수집 불완전**: 토글 버튼 감지는 구현했으나 실제 하위 행 펼치기 실패
2. **JavaScript 의존성**: 일부 토글 기능이 복잡한 JavaScript 로직에 의존
3. **사이트 구조 변경 민감성**: 페이지 구조 변경 시 코드 수정 필요

## 🔄 개발 중단 사유

- 메인 레벨 192개 항목 수집 완료 (목표 달성)
- 하위 계층 토글 메커니즘의 복잡성으로 인한 개발 비용 증가
- 코드 목록 데이터 확보로 인한 우선순위 변경

## 📈 성과

- ✅ 메인 항목 192개 100% 수집 성공
- ✅ 상세 정보 팝업 데이터 추출 완료
- ✅ 안정적인 페이지네이션 처리
- ✅ 에러 처리 및 로깅 시스템 구축
- ⚠️ 하위 계층 수집 미완료 (토글 감지까지는 구현)