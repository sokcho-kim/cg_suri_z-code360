import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz
import re
import warnings
warnings.filterwarnings('ignore')

# 실행 파라미터
FUZZY_METHOD = 'token_set_ratio'
FUZZY_THRESHOLD = 90
PARTIAL_THRESHOLD = 95
BLOCKING_MIN_TOKEN_LEN = 3
STOPWORDS = ['수술','증후군','질환','손가락','수지','부위','증상','기타','NOS','기타및상세불명']
STRICT_CHILD_CODE_ONLY = True

def load_data():
    """데이터 로드 (원본 보존 원칙)"""
    try:
        print("=== 데이터 로드 시작 ===")
        
        # 수가 파일 로드 (모든 원본 컬럼 보존)
        suga_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\★수가반영내역(25.8.1.기준)_전체판.xlsx'
        suga_df = pd.read_excel(suga_file)
        print(f"수가 파일 로드: {suga_df.shape}")
        
        # 상병코드 파일 로드
        disease_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\배포용 상병마스터_240101(2).xlsx'
        xl_file = pd.ExcelFile(disease_file)
        
        # 적절한 시트 찾기
        sheet_name = None
        for name in xl_file.sheet_names:
            if '상병분류번호' in name and ('전체' in name or '상병코드' in name):
                sheet_name = name
                break
        if sheet_name is None:
            sheet_name = xl_file.sheet_names[1]
            
        disease_df = pd.read_excel(disease_file, sheet_name=sheet_name, header=10)
        disease_df = disease_df.iloc[:, :3].copy()
        disease_df.columns = ['상병코드', '한글명', '영문명']
        
        # 상병코드 유효성 검증 (A00-Z99 패턴)
        valid_pattern = disease_df['상병코드'].astype(str).str.match(r'^[A-Z]\d+')
        disease_df = disease_df[valid_pattern].dropna(subset=['상병코드', '한글명']).reset_index(drop=True)
        
        print(f"상병 파일 로드: {disease_df.shape}")
        print(f"수가 컬럼: {list(suga_df.columns)}")
        
        return suga_df, disease_df
    
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
        return None, None

def extract_meaningful_tokens(text):
    """의미있는 토큰 추출 (블로킹용)"""
    if pd.isna(text) or not text:
        return set()
    
    text = str(text).lower()
    
    # 괄호 내용 제거
    text = re.sub(r'\([^)]*\)', '', text)
    
    # 토큰 추출 (한글, 영문 단어)
    korean_tokens = re.findall(r'[가-힣]+', text)
    english_tokens = re.findall(r'[a-zA-Z]+', text)
    
    all_tokens = korean_tokens + english_tokens
    
    # 필터링: 길이, 스톱워드 제거
    meaningful_tokens = set()
    for token in all_tokens:
        token = token.lower()
        if (len(token) >= BLOCKING_MIN_TOKEN_LEN and 
            token not in STOPWORDS and
            not re.match(r'^[0-9\-\.]+$', token)):  # 숫자/코드 패턴 제외
            meaningful_tokens.add(token)
    
    return meaningful_tokens

def is_valid_child_code(disease_code):
    """상위범주 코드 여부 확인"""
    if not disease_code or len(str(disease_code)) < 4:
        return False
    
    code_str = str(disease_code).upper()
    
    # 상위범주 패턴들 (예: M79, S69 등 3자리 또는 .x로 끝나는 것)
    if (len(code_str) == 3 or 
        code_str.endswith('.X') or 
        code_str.endswith('.9') or
        re.match(r'^[A-Z]\d{2}$', code_str)):
        return False
    
    return True

def check_blocking_condition(suga_tokens, disease_tokens):
    """블로킹 조건 검사: 공통 의미 토큰이 최소 1개 이상"""
    if not suga_tokens or not disease_tokens:
        return False
    
    common_tokens = suga_tokens.intersection(disease_tokens)
    
    # 공통 토큰이 있고, 그 중 의미있는 토큰이 있는지 확인
    meaningful_common = [token for token in common_tokens 
                        if len(token) >= BLOCKING_MIN_TOKEN_LEN]
    
    return len(meaningful_common) > 0

def safe_fuzzy_matching(suga_row, disease_df):
    """안전한 퍼지 매칭 (블로킹 + 임계값)"""
    matches = []
    
    suga_korean = str(suga_row.get('한글명', ''))
    suga_english = str(suga_row.get('영문명', ''))
    
    # 수가에서 의미 토큰 추출
    suga_tokens_kr = extract_meaningful_tokens(suga_korean)
    suga_tokens_en = extract_meaningful_tokens(suga_english)
    suga_tokens = suga_tokens_kr.union(suga_tokens_en)
    
    if not suga_tokens:
        return matches
    
    for _, disease_row in disease_df.iterrows():
        disease_code = disease_row.get('상병코드', '')
        disease_korean = str(disease_row.get('한글명', ''))
        disease_english = str(disease_row.get('영문명', ''))
        
        # 상위범주 코드 필터링
        if STRICT_CHILD_CODE_ONLY and not is_valid_child_code(disease_code):
            continue
        
        # 상병에서 의미 토큰 추출
        disease_tokens_kr = extract_meaningful_tokens(disease_korean)
        disease_tokens_en = extract_meaningful_tokens(disease_english)
        disease_tokens = disease_tokens_kr.union(disease_tokens_en)
        
        # 블로킹 조건 검사
        if not check_blocking_condition(suga_tokens, disease_tokens):
            continue
        
        # 한글명 매칭
        if suga_korean and disease_korean:
            token_score = fuzz.token_set_ratio(suga_korean, disease_korean)
            partial_score = fuzz.partial_ratio(suga_korean, disease_korean)
            
            if token_score >= FUZZY_THRESHOLD or partial_score >= PARTIAL_THRESHOLD:
                common_tokens = suga_tokens_kr.intersection(disease_tokens_kr)
                matches.append({
                    'disease_code': disease_code,
                    'disease_korean': disease_korean,
                    'disease_english': disease_english,
                    'match_type': 'fuzzy',
                    'score': max(token_score, partial_score),
                    'keywords': ','.join(sorted(common_tokens))
                })
        
        # 영문명 매칭
        if suga_english and disease_english:
            token_score = fuzz.token_set_ratio(suga_english, disease_english)
            partial_score = fuzz.partial_ratio(suga_english, disease_english)
            
            if token_score >= FUZZY_THRESHOLD or partial_score >= PARTIAL_THRESHOLD:
                common_tokens = suga_tokens_en.intersection(disease_tokens_en)
                matches.append({
                    'disease_code': disease_code,
                    'disease_korean': disease_korean,
                    'disease_english': disease_english,
                    'match_type': 'fuzzy',
                    'score': max(token_score, partial_score),
                    'keywords': ','.join(sorted(common_tokens))
                })
    
    return matches

def exact_matching(suga_row, disease_df):
    """완전 일치 매칭"""
    matches = []
    
    suga_korean = str(suga_row.get('한글명', '')).strip().lower()
    suga_english = str(suga_row.get('영문명', '')).strip().lower()
    
    for _, disease_row in disease_df.iterrows():
        disease_code = disease_row.get('상병코드', '')
        disease_korean = str(disease_row.get('한글명', '')).strip().lower()
        disease_english = str(disease_row.get('영문명', '')).strip().lower()
        
        # 한글명 완전일치
        if (suga_korean and disease_korean and 
            len(suga_korean) > 2 and suga_korean == disease_korean):
            matches.append({
                'disease_code': disease_code,
                'disease_korean': disease_row.get('한글명', ''),
                'disease_english': disease_row.get('영문명', ''),
                'match_type': 'exact',
                'score': 100,
                'keywords': 'exact_korean'
            })
        
        # 영문명 완전일치
        elif (suga_english and disease_english and 
              len(suga_english) > 2 and suga_english == disease_english):
            matches.append({
                'disease_code': disease_code,
                'disease_korean': disease_row.get('한글명', ''),
                'disease_english': disease_row.get('영문명', ''),
                'match_type': 'exact',
                'score': 100,
                'keywords': 'exact_english'
            })
    
    return matches

def process_mapping(suga_df, disease_df):
    """매핑 프로세스 (LEFT JOIN 원칙, 원본 보존)"""
    print("\n=== 매핑 프로세스 시작 ===")
    
    results = []
    exact_count = 0
    fuzzy_count = 0
    no_match_count = 0
    
    total_rows = len(suga_df)
    
    for idx, suga_row in suga_df.iterrows():
        if idx % 1000 == 0:
            print(f"진행률: {idx}/{total_rows} ({idx/total_rows*100:.1f}%)")
        
        # 원본 수가 정보 보존
        base_row = {
            '수가코드': suga_row.get('수가코드', ''),
            '수가명_한글': suga_row.get('한글명', ''),  # 원본 그대로
            '수가명_영문': suga_row.get('영문명', ''),  # 원본 그대로
            '단가정보': suga_row.get('상대가치점수', ''),
            '적용일자': suga_row.get('적용일자', ''),
            '분류번호': suga_row.get('분류번호', '')
        }
        
        # 1. 완전일치 시도
        exact_matches = exact_matching(suga_row, disease_df)
        
        if exact_matches:
            # 완전일치가 있으면 fuzzy는 건너뛰기
            for match in exact_matches:
                result_row = base_row.copy()
                result_row.update({
                    '매칭_상병코드': match['disease_code'],
                    '매칭_상병명_한글': match['disease_korean'],
                    '매칭_상병명_영문': match['disease_english'],
                    '매칭_방식': match['match_type'],
                    '매칭_점수': match['score'],
                    '매칭_키워드': match['keywords']
                })
                results.append(result_row)
                exact_count += 1
        else:
            # 2. 완전일치가 없으면 퍼지 매칭 시도
            fuzzy_matches = safe_fuzzy_matching(suga_row, disease_df)
            
            if fuzzy_matches:
                # 점수 순으로 정렬하고 상위 매칭만 선택
                fuzzy_matches = sorted(fuzzy_matches, key=lambda x: x['score'], reverse=True)
                
                for match in fuzzy_matches[:3]:  # 최대 3개까지
                    result_row = base_row.copy()
                    result_row.update({
                        '매칭_상병코드': match['disease_code'],
                        '매칭_상병명_한글': match['disease_korean'],
                        '매칭_상병명_영문': match['disease_english'],
                        '매칭_방식': match['match_type'],
                        '매칭_점수': match['score'],
                        '매칭_키워드': match['keywords']
                    })
                    results.append(result_row)
                    fuzzy_count += 1
            else:
                # 3. 매칭 실패 시 NULL로 기록
                result_row = base_row.copy()
                result_row.update({
                    '매칭_상병코드': '',
                    '매칭_상병명_한글': '',
                    '매칭_상병명_영문': '',
                    '매칭_방식': 'no_match',
                    '매칭_점수': 0,
                    '매칭_키워드': ''
                })
                results.append(result_row)
                no_match_count += 1
    
    print(f"\n매핑 완료:")
    print(f"- 완전일치: {exact_count}개")
    print(f"- 퍼지매칭: {fuzzy_count}개")
    print(f"- 미매칭: {no_match_count}개")
    print(f"- 총 결과행: {len(results)}개")
    
    return pd.DataFrame(results), exact_count, fuzzy_count, no_match_count

def generate_quality_report(result_df, exact_count, fuzzy_count, no_match_count):
    """품질 리포트 생성"""
    total_matches = exact_count + fuzzy_count
    high_quality_count = len(result_df[result_df['매칭_점수'] >= 95])
    
    # 퍼지 매칭의 평균 점수
    fuzzy_scores = result_df[result_df['매칭_방식'] == 'fuzzy']['매칭_점수']
    avg_fuzzy_score = fuzzy_scores.mean() if len(fuzzy_scores) > 0 else 0
    
    # 상위범주 코드 비율 확인
    upper_category_count = 0
    matched_df = result_df[result_df['매칭_점수'] > 0]
    for code in matched_df['매칭_상병코드']:
        if not is_valid_child_code(code):
            upper_category_count += 1
    
    upper_category_ratio = upper_category_count / len(matched_df) if len(matched_df) > 0 else 0
    
    report = f"""
# 의료 수가-상병코드 매핑 품질 리포트 v2

## 매핑 통계
- **총 매칭 수**: {total_matches:,}개
- **완전일치**: {exact_count:,}개 ({exact_count/total_matches*100:.1f}%)
- **퍼지매칭**: {fuzzy_count:,}개 ({fuzzy_count/total_matches*100:.1f}%)
- **미매칭**: {no_match_count:,}개
- **평균 퍼지 점수**: {avg_fuzzy_score:.1f}점
- **고품질 매칭(≥95점)**: {high_quality_count:,}개 ({high_quality_count/total_matches*100:.1f}%)

## 품질 검증
- **상위범주 코드 비율**: {upper_category_ratio*100:.2f}% (목표: <1%)
- **퍼지 저품질 비율**: {len(result_df[result_df['매칭_점수'].between(1, FUZZY_THRESHOLD-1)])/total_matches*100:.2f}% (목표: <5%)

## 매개변수
- FUZZY_THRESHOLD: {FUZZY_THRESHOLD}
- PARTIAL_THRESHOLD: {PARTIAL_THRESHOLD}
- BLOCKING_MIN_TOKEN_LEN: {BLOCKING_MIN_TOKEN_LEN}
- STRICT_CHILD_CODE_ONLY: {STRICT_CHILD_CODE_ONLY}
"""
    
    return report, upper_category_ratio

def main():
    print("=== 의료 수가-상병코드 매핑 v2 (원본 보존) ===")
    
    # 1. 데이터 로드
    suga_df, disease_df = load_data()
    if suga_df is None or disease_df is None:
        print("❌ 데이터 로드 실패")
        return
    
    # 필수 컬럼 확인
    required_cols = ['수가코드', '한글명']
    missing_cols = [col for col in required_cols if col not in suga_df.columns]
    if missing_cols:
        print(f"❌ 필수 컬럼 누락: {missing_cols}")
        return
    
    # 2. 매핑 실행
    result_df, exact_count, fuzzy_count, no_match_count = process_mapping(suga_df, disease_df)
    
    # 3. 품질 검증
    report, upper_category_ratio = generate_quality_report(result_df, exact_count, fuzzy_count, no_match_count)
    
    # 실패 조건 검사
    total_matches = exact_count + fuzzy_count
    low_quality_ratio = len(result_df[result_df['매칭_점수'].between(1, FUZZY_THRESHOLD-1)]) / total_matches if total_matches > 0 else 0
    
    if upper_category_ratio > 0.01:
        print(f"❌ 실패: 상위범주 코드 비율 {upper_category_ratio*100:.2f}% > 1%")
        return
    
    if low_quality_ratio > 0.05:
        print(f"❌ 실패: 저품질 매칭 비율 {low_quality_ratio*100:.2f}% > 5%")
        return
    
    # 4. 결과 저장
    import os
    os.makedirs('./outputs', exist_ok=True)
    
    output_file = './outputs/medical_code_integrated_v2.csv'
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    report_file = './outputs/medical_code_mapper_v2_report.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 성공적으로 완료!")
    print(f"📁 결과 파일: {output_file}")
    print(f"📊 리포트: {report_file}")
    
    # 5. 샘플 미리보기
    print(f"\n=== 샘플 결과 (20건) ===")
    sample_cols = ['수가코드', '수가명_한글', '매칭_상병코드', '매칭_상병명_한글', '매칭_방식', '매칭_점수']
    print(result_df[sample_cols].head(20).to_string(index=False))
    
    print(report)

if __name__ == "__main__":
    main()