import pandas as pd
from fuzzywuzzy import fuzz
import re

# 테스트용 샘플 데이터
test_suga_data = [
    {'수가코드': 'IERA3533', '한글명': '방아쇠수지절개술', '영문명': 'Trigger Finger Release'},
    {'수가코드': 'N0830', '한글명': '손목관절경검사', '영문명': 'Wrist Arthroscopy'},
    {'수가코드': 'IER45320', '한글명': '자궁외임신수술-자궁각임신', '영문명': 'Cornual Pregnancy'}
]

test_disease_data = [
    {'상병코드': 'M65.3', '한글명': '방아쇠손가락', '영문명': 'Trigger finger'},
    {'상병코드': 'M65.30', '한글명': '상세불명의 방아쇠손가락', '영문명': 'Trigger finger, unspecified'},
    {'상병코드': 'S69.9', '한글명': '손가락의 기타 및 상세불명 손상', '영문명': 'Other and unspecified injury of finger'},
    {'상병코드': 'O00.0', '한글명': '복강임신', '영문명': 'Abdominal pregnancy'},
    {'상병코드': 'O00.1', '한글명': '자궁각 임신', '영문명': 'Cornual pregnancy'}
]

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
    stopwords = ['수술','증후군','질환','손가락','수지','부위','증상','기타','NOS']
    meaningful_tokens = set()
    
    for token in all_tokens:
        token = token.lower()
        if (len(token) >= 3 and 
            token not in stopwords and
            not re.match(r'^[0-9\-\.]+$', token)):
            meaningful_tokens.add(token)
    
    return meaningful_tokens

def check_blocking_condition(suga_tokens, disease_tokens):
    """블로킹 조건 검사"""
    common_tokens = suga_tokens.intersection(disease_tokens)
    meaningful_common = [token for token in common_tokens if len(token) >= 3]
    return len(meaningful_common) > 0

def test_mapping_logic():
    """매핑 로직 테스트"""
    print("=== v2 매핑 로직 테스트 ===\n")
    
    suga_df = pd.DataFrame(test_suga_data)
    disease_df = pd.DataFrame(test_disease_data)
    
    results = []
    
    for _, suga_row in suga_df.iterrows():
        print(f"[검토] 수가: {suga_row['수가코드']} - {suga_row['한글명']} ({suga_row['영문명']})")
        
        # 원본 정보 보존
        base_info = {
            '수가코드': suga_row['수가코드'],
            '수가명_한글': suga_row['한글명'],  # 원본 그대로!
            '수가명_영문': suga_row['영문명'],  # 원본 그대로!
        }
        
        # 토큰 추출
        suga_tokens_kr = extract_meaningful_tokens(suga_row['한글명'])
        suga_tokens_en = extract_meaningful_tokens(suga_row['영문명'])
        suga_tokens = suga_tokens_kr.union(suga_tokens_en)
        
        print(f"   수가 토큰: {sorted(suga_tokens)}")
        
        matches = []
        
        # 1. 완전일치 먼저
        for _, disease_row in disease_df.iterrows():
            if (suga_row['한글명'].lower().strip() == disease_row['한글명'].lower().strip() or
                suga_row['영문명'].lower().strip() == disease_row['영문명'].lower().strip()):
                
                match = base_info.copy()
                match.update({
                    '매칭_상병코드': disease_row['상병코드'],
                    '매칭_상병명_한글': disease_row['한글명'],
                    '매칭_상병명_영문': disease_row['영문명'],
                    '매칭_방식': 'exact',
                    '매칭_점수': 100
                })
                matches.append(match)
                print(f"   [OK] 완전일치: {disease_row['상병코드']} - {disease_row['한글명']}")
        
        # 2. 완전일치 없으면 퍼지 매칭
        if not matches:
            for _, disease_row in disease_df.iterrows():
                disease_tokens_kr = extract_meaningful_tokens(disease_row['한글명'])
                disease_tokens_en = extract_meaningful_tokens(disease_row['영문명'])
                disease_tokens = disease_tokens_kr.union(disease_tokens_en)
                
                print(f"   검토 중: {disease_row['상병코드']} - 토큰: {sorted(disease_tokens)}")
                
                # 블로킹 조건 확인
                if not check_blocking_condition(suga_tokens, disease_tokens):
                    print(f"     [X] 블로킹 실패 (공통 토큰 없음)")
                    continue
                
                # 한글명 퍼지 매칭
                if suga_row['한글명'] and disease_row['한글명']:
                    token_score = fuzz.token_set_ratio(suga_row['한글명'], disease_row['한글명'])
                    partial_score = fuzz.partial_ratio(suga_row['한글명'], disease_row['한글명'])
                    max_score = max(token_score, partial_score)
                    
                    print(f"     한글 점수: token={token_score}, partial={partial_score}")
                    
                    if max_score >= 90:
                        common_tokens = suga_tokens_kr.intersection(disease_tokens_kr)
                        match = base_info.copy()
                        match.update({
                            '매칭_상병코드': disease_row['상병코드'],
                            '매칭_상병명_한글': disease_row['한글명'],
                            '매칭_상병명_영문': disease_row['영문명'],
                            '매칭_방식': 'fuzzy',
                            '매칭_점수': max_score,
                            '매칭_키워드': ','.join(sorted(common_tokens))
                        })
                        matches.append(match)
                        print(f"     [OK] 퍼지매칭: {disease_row['상병코드']} (점수: {max_score})")
                
                # 영문명 퍼지 매칭
                if suga_row['영문명'] and disease_row['영문명']:
                    token_score = fuzz.token_set_ratio(suga_row['영문명'], disease_row['영문명'])
                    partial_score = fuzz.partial_ratio(suga_row['영문명'], disease_row['영문명'])
                    max_score = max(token_score, partial_score)
                    
                    print(f"     영문 점수: token={token_score}, partial={partial_score}")
                    
                    if max_score >= 90:
                        common_tokens = suga_tokens_en.intersection(disease_tokens_en)
                        match = base_info.copy()
                        match.update({
                            '매칭_상병코드': disease_row['상병코드'],
                            '매칭_상병명_한글': disease_row['한글명'],
                            '매칭_상병명_영문': disease_row['영문명'],
                            '매칭_방식': 'fuzzy',
                            '매칭_점수': max_score,
                            '매칭_키워드': ','.join(sorted(common_tokens))
                        })
                        matches.append(match)
                        print(f"     [OK] 퍼지매칭: {disease_row['상병코드']} (점수: {max_score})")
        
        # 매칭 없으면 미매칭 기록
        if not matches:
            match = base_info.copy()
            match.update({
                '매칭_상병코드': '',
                '매칭_방식': 'no_match',
                '매칭_점수': 0
            })
            matches.append(match)
            print(f"   [X] 매칭 실패")
        
        # 최고 점수 3개까지만
        matches = sorted(matches, key=lambda x: x['매칭_점수'], reverse=True)[:3]
        results.extend(matches)
        print()
    
    # 결과 출력
    result_df = pd.DataFrame(results)
    print("=== 최종 결과 ===")
    display_cols = ['수가코드', '수가명_한글', '매칭_상병코드', '매칭_방식', '매칭_점수']
    available_cols = [col for col in display_cols if col in result_df.columns]
    print(result_df[available_cols].to_string(index=False))
    
    # 원본 보존 확인
    print(f"\n=== 원본 보존 확인 ===")
    print("수가명이 원본 그대로 보존되었는지 확인:")
    for _, row in result_df.iterrows():
        original = next(s['한글명'] for s in test_suga_data if s['수가코드'] == row['수가코드'])
        preserved = row['수가명_한글']
        status = '[OK]' if original == preserved else '[ERROR]'
        print(f"  {row['수가코드']}: '{original}' -> '{preserved}' {status}")

if __name__ == "__main__":
    test_mapping_logic()