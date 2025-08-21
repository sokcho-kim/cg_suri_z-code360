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

def load_sample_data():
    """샘플 데이터 로드"""
    try:
        print("=== 샘플 데이터 로드 시작 ===")
        
        # 수가 파일 로드 (샘플)
        suga_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\★수가반영내역(25.8.1.기준)_전체판.xlsx'
        suga_df = pd.read_excel(suga_file, nrows=2000)  # 2000행만
        print(f"수가 파일 로드: {suga_df.shape}")
        
        # 상병코드 파일 로드 (샘플)
        disease_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\배포용 상병마스터_240101(2).xlsx'
        xl_file = pd.ExcelFile(disease_file)
        
        # 적절한 시트 찾기
        sheet_name = xl_file.sheet_names[1]  # 두 번째 시트
        disease_df = pd.read_excel(disease_file, sheet_name=sheet_name, header=10, nrows=5000)  # 5000행만
        disease_df = disease_df.iloc[:, :3].copy()
        disease_df.columns = ['상병코드', '한글명', '영문명']
        
        # 상병코드 유효성 검증
        valid_pattern = disease_df['상병코드'].astype(str).str.match(r'^[A-Z]\d+')
        disease_df = disease_df[valid_pattern].dropna(subset=['상병코드', '한글명']).reset_index(drop=True)
        
        print(f"상병 파일 로드: {disease_df.shape}")
        return suga_df, disease_df
    
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
        return None, None

def extract_meaningful_tokens(text):
    """의미있는 토큰 추출"""
    if pd.isna(text) or not text:
        return set()
    
    text = str(text).lower()
    text = re.sub(r'\([^)]*\)', '', text)  # 괄호 제거
    
    # 토큰 추출
    korean_tokens = re.findall(r'[가-힣]+', text)
    english_tokens = re.findall(r'[a-zA-Z]+', text)
    
    all_tokens = korean_tokens + english_tokens
    
    # 필터링
    meaningful_tokens = set()
    for token in all_tokens:
        token = token.lower()
        if (len(token) >= BLOCKING_MIN_TOKEN_LEN and 
            token not in STOPWORDS and
            not re.match(r'^[0-9\-\.]+$', token)):
            meaningful_tokens.add(token)
    
    return meaningful_tokens

def is_valid_child_code(disease_code):
    """상위범주 코드 여부 확인"""
    if not disease_code or len(str(disease_code)) < 4:
        return False
    
    code_str = str(disease_code).upper()
    
    # 상위범주 패턴 제외
    if (len(code_str) == 3 or 
        code_str.endswith('.X') or 
        code_str.endswith('.9') or
        re.match(r'^[A-Z]\d{2}$', code_str)):
        return False
    
    return True

def check_blocking_condition(suga_tokens, disease_tokens):
    """블로킹 조건 검사"""
    if not suga_tokens or not disease_tokens:
        return False
    
    common_tokens = suga_tokens.intersection(disease_tokens)
    meaningful_common = [token for token in common_tokens 
                        if len(token) >= BLOCKING_MIN_TOKEN_LEN]
    
    return len(meaningful_common) > 0

def process_single_row(suga_row, disease_df):
    """단일 수가 행 처리"""
    # 원본 정보 보존
    base_info = {
        '수가코드': suga_row.get('수가코드', ''),
        '수가명_한글': suga_row.get('한글명', ''),  # 원본 그대로
        '수가명_영문': suga_row.get('영문명', ''),  # 원본 그대로
        '단가정보': suga_row.get('상대가치점수', ''),
        '적용일자': suga_row.get('적용일자', ''),
        '분류번호': suga_row.get('분류번호', '')
    }
    
    suga_korean = str(suga_row.get('한글명', ''))
    suga_english = str(suga_row.get('영문명', ''))
    
    # 토큰 추출
    suga_tokens_kr = extract_meaningful_tokens(suga_korean)
    suga_tokens_en = extract_meaningful_tokens(suga_english)
    suga_tokens = suga_tokens_kr.union(suga_tokens_en)
    
    matches = []
    
    # 1. 완전일치 우선
    for _, disease_row in disease_df.iterrows():
        disease_korean = str(disease_row.get('한글명', '')).strip()
        disease_english = str(disease_row.get('영문명', '')).strip()
        
        # 한글명 완전일치
        if (suga_korean.strip().lower() == disease_korean.lower() and 
            len(suga_korean.strip()) > 2):
            match = base_info.copy()
            match.update({
                '매칭_상병코드': disease_row.get('상병코드', ''),
                '매칭_상병명_한글': disease_korean,
                '매칭_상병명_영문': disease_english,
                '매칭_방식': 'exact',
                '매칭_점수': 100,
                '매칭_키워드': 'exact_korean'
            })
            matches.append(match)
        
        # 영문명 완전일치
        elif (suga_english.strip().lower() == disease_english.lower() and 
              len(suga_english.strip()) > 2):
            match = base_info.copy()
            match.update({
                '매칭_상병코드': disease_row.get('상병코드', ''),
                '매칭_상병명_한글': disease_korean,
                '매칭_상병명_영문': disease_english,
                '매칭_방식': 'exact',
                '매칭_점수': 100,
                '매칭_키워드': 'exact_english'
            })
            matches.append(match)
    
    # 2. 완전일치가 없으면 퍼지 매칭
    if not matches and suga_tokens:
        for _, disease_row in disease_df.iterrows():
            disease_code = disease_row.get('상병코드', '')
            disease_korean = str(disease_row.get('한글명', ''))
            disease_english = str(disease_row.get('영문명', ''))
            
            # 상위범주 필터링
            if STRICT_CHILD_CODE_ONLY and not is_valid_child_code(disease_code):
                continue
            
            # 토큰 추출
            disease_tokens_kr = extract_meaningful_tokens(disease_korean)
            disease_tokens_en = extract_meaningful_tokens(disease_english)
            disease_tokens = disease_tokens_kr.union(disease_tokens_en)
            
            # 블로킹 조건 확인
            if not check_blocking_condition(suga_tokens, disease_tokens):
                continue
            
            # 한글명 퍼지 매칭
            if suga_korean and disease_korean:
                token_score = fuzz.token_set_ratio(suga_korean, disease_korean)
                partial_score = fuzz.partial_ratio(suga_korean, disease_korean)
                max_score = max(token_score, partial_score)
                
                if max_score >= FUZZY_THRESHOLD or partial_score >= PARTIAL_THRESHOLD:
                    common_tokens = suga_tokens_kr.intersection(disease_tokens_kr)
                    match = base_info.copy()
                    match.update({
                        '매칭_상병코드': disease_code,
                        '매칭_상병명_한글': disease_korean,
                        '매칭_상병명_영문': disease_english,
                        '매칭_방식': 'fuzzy',
                        '매칭_점수': max_score,
                        '매칭_키워드': ','.join(sorted(common_tokens))
                    })
                    matches.append(match)
            
            # 영문명 퍼지 매칭
            if suga_english and disease_english:
                token_score = fuzz.token_set_ratio(suga_english, disease_english)
                partial_score = fuzz.partial_ratio(suga_english, disease_english)
                max_score = max(token_score, partial_score)
                
                if max_score >= FUZZY_THRESHOLD or partial_score >= PARTIAL_THRESHOLD:
                    common_tokens = suga_tokens_en.intersection(disease_tokens_en)
                    match = base_info.copy()
                    match.update({
                        '매칭_상병코드': disease_code,
                        '매칭_상병명_한글': disease_korean,
                        '매칭_상병명_영문': disease_english,
                        '매칭_방식': 'fuzzy',
                        '매칭_점수': max_score,
                        '매칭_키워드': ','.join(sorted(common_tokens))
                    })
                    matches.append(match)
    
    # 3. 매칭 실패 시 미매칭 기록
    if not matches:
        match = base_info.copy()
        match.update({
            '매칭_상병코드': '',
            '매칭_상병명_한글': '',
            '매칭_상병명_영문': '',
            '매칭_방식': 'no_match',
            '매칭_점수': 0,
            '매칭_키워드': ''
        })
        matches.append(match)
    
    # 점수 순 정렬하고 상위 3개만
    matches = sorted(matches, key=lambda x: x['매칭_점수'], reverse=True)[:3]
    
    return matches

def main():
    print("=== 의료 수가-상병코드 매핑 v2 (샘플 테스트) ===")
    
    # 1. 샘플 데이터 로드
    suga_df, disease_df = load_sample_data()
    if suga_df is None or disease_df is None:
        print("❌ 데이터 로드 실패")
        return
    
    # 2. 매핑 실행
    print("\n=== 매핑 시작 ===")
    all_results = []
    exact_count = 0
    fuzzy_count = 0
    no_match_count = 0
    
    for idx, suga_row in suga_df.iterrows():
        if idx % 100 == 0:
            print(f"진행: {idx}/{len(suga_df)} ({idx/len(suga_df)*100:.1f}%)")
        
        matches = process_single_row(suga_row, disease_df)
        
        for match in matches:
            all_results.append(match)
            
            if match['매칭_방식'] == 'exact':
                exact_count += 1
            elif match['매칭_방식'] == 'fuzzy':
                fuzzy_count += 1
            else:
                no_match_count += 1
    
    # 3. 결과 생성
    result_df = pd.DataFrame(all_results)
    
    print(f"\n=== 매핑 완료 ===")
    print(f"완전일치: {exact_count}개")
    print(f"퍼지매칭: {fuzzy_count}개")
    print(f"미매칭: {no_match_count}개")
    print(f"총 결과행: {len(result_df)}개")
    
    # 4. 품질 검증
    high_quality = len(result_df[result_df['매칭_점수'] >= 95])
    total_matched = exact_count + fuzzy_count
    
    if total_matched > 0:
        print(f"고품질 매칭(≥95점): {high_quality}개 ({high_quality/total_matched*100:.1f}%)")
        
        # 상위범주 코드 비율
        matched_df = result_df[result_df['매칭_점수'] > 0]
        upper_category_count = sum(1 for code in matched_df['매칭_상병코드'] 
                                  if not is_valid_child_code(code))
        upper_ratio = upper_category_count / len(matched_df) if len(matched_df) > 0 else 0
        print(f"상위범주 코드 비율: {upper_ratio*100:.2f}%")
    
    # 5. 결과 저장
    import os
    os.makedirs('./outputs', exist_ok=True)
    
    output_file = './outputs/medical_code_integrated_v2_sample.csv'
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 샘플 결과 저장: {output_file}")
    
    # 6. 미리보기
    print(f"\n=== 샘플 결과 (10건) ===")
    sample_cols = ['수가코드', '수가명_한글', '매칭_상병코드', '매칭_상병명_한글', '매칭_방식', '매칭_점수']
    available_cols = [col for col in sample_cols if col in result_df.columns]
    print(result_df[available_cols].head(10).to_string(index=False))
    
    # 7. 방아쇠손가락 관련 확인
    trigger_cases = result_df[result_df['수가명_한글'].str.contains('방아쇠', na=False)]
    if len(trigger_cases) > 0:
        print(f"\n=== 방아쇠 관련 매칭 확인 ===")
        print(trigger_cases[available_cols].to_string(index=False))

if __name__ == "__main__":
    main()