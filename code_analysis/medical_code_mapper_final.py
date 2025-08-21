import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz, process
import re
import warnings
warnings.filterwarnings('ignore')

def load_data():
    """올바른 데이터 구조로 로드"""
    try:
        # 수가 파일 로드
        print("수가 파일 로드 중...")
        suga_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\★수가반영내역(25.8.1.기준)_전체판.xlsx'
        suga_df = pd.read_excel(suga_file, usecols=['수가코드', '한글명', '영문명', '상대가치점수'])
        suga_df = suga_df.dropna(subset=['한글명']).reset_index(drop=True)
        print(f"수가 데이터: {suga_df.shape}")
        
        # 상병코드 파일 로드 (올바른 시트와 헤더)
        print("상병코드 파일 로드 중...")
        disease_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\배포용 상병마스터_240101(2).xlsx'
        
        # 시트 이름 확인 후 적절한 시트 선택
        xl_file = pd.ExcelFile(disease_file)
        print(f"시트 목록: {xl_file.sheet_names}")
        
        # 상병분류번호가 포함된 시트 찾기
        sheet_name = None
        for name in xl_file.sheet_names:
            if '상병분류번호' in name and '전체' in name:
                sheet_name = name
                break
        
        if sheet_name is None:
            sheet_name = xl_file.sheet_names[1]  # 두 번째 시트 사용
            
        print(f"사용할 시트: {sheet_name}")
        disease_df = pd.read_excel(disease_file, sheet_name=sheet_name, header=10)
        
        # 처음 3개 컬럼만 사용 (상병기호, 한글명, 영문명)
        disease_df = disease_df.iloc[:, :3].copy()
        disease_df.columns = ['상병코드', '한글명', '영문명']
        disease_df = disease_df.dropna(subset=['상병코드', '한글명']).reset_index(drop=True)
        
        # 상병코드 패턴 확인 (A00-Z99 형식)
        valid_codes = disease_df['상병코드'].astype(str).str.match(r'^[A-Z]\d+')
        disease_df = disease_df[valid_codes].reset_index(drop=True)
        
        print(f"상병 데이터: {disease_df.shape}")
        print(f"상병코드 샘플: {list(disease_df['상병코드'].head())}")
        print(f"상병명 샘플: {list(disease_df['한글명'].head())}")
        
        return suga_df, disease_df
    
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
        return None, None

def clean_text(text):
    """텍스트 정리"""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    # 괄호 내용 제거
    text = re.sub(r'\([^)]*\)', '', text)
    # 특수문자 제거
    text = re.sub(r'[^\w\s가-힣a-zA-Z]', ' ', text)
    # 공백 정리
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()

def exact_match_mapping(suga_df, disease_df, suga_col, disease_col):
    """완전 일치 매핑"""
    print(f"완전 일치 매핑: {suga_col} vs {disease_col}")
    matches = []
    
    # 상병코드를 딕셔너리로 변환 (성능 최적화)
    disease_dict = {}
    for idx, text in enumerate(disease_df[disease_col]):
        clean_text_val = clean_text(text)
        if clean_text_val and len(clean_text_val) > 1:
            if clean_text_val not in disease_dict:
                disease_dict[clean_text_val] = []
            disease_dict[clean_text_val].append(idx)
    
    # 수가 데이터와 매칭
    match_count = 0
    for suga_idx, suga_text in enumerate(suga_df[suga_col]):
        clean_suga = clean_text(suga_text)
        if clean_suga and clean_suga in disease_dict:
            for disease_idx in disease_dict[clean_suga]:
                matches.append({
                    'suga_idx': suga_idx,
                    'disease_idx': disease_idx,
                    'match_type': 'exact',
                    'match_col': f'{suga_col}_{disease_col}',
                    'similarity': 100
                })
                match_count += 1
                if match_count % 100 == 0:
                    print(f"  매칭 진행: {match_count}개")
    
    print(f"  완료: {len(matches)}개 매칭")
    return matches

def fuzzy_match_mapping(suga_df, disease_df, suga_col, disease_col, threshold=85, max_samples=2000):
    """유사 매칭 (샘플링 사용)"""
    print(f"유사 매칭: {suga_col} vs {disease_col} (임계값: {threshold})")
    matches = []
    
    # 이미 완전일치된 항목들 제외
    exact_matches = exact_match_mapping(suga_df, disease_df, suga_col, disease_col)
    exact_suga_indices = {match['suga_idx'] for match in exact_matches}
    
    # 샘플링
    remaining_suga = suga_df[~suga_df.index.isin(exact_suga_indices)]
    suga_sample = remaining_suga.sample(min(max_samples, len(remaining_suga)), random_state=42) if len(remaining_suga) > 0 else remaining_suga
    disease_sample = disease_df.sample(min(max_samples, len(disease_df)), random_state=42)
    
    print(f"  샘플 크기: 수가 {len(suga_sample)}, 상병 {len(disease_sample)}")
    
    # 상병 텍스트 사전 처리
    disease_texts = []
    disease_indices = []
    for idx, text in enumerate(disease_sample[disease_col]):
        clean_text_val = clean_text(text)
        if clean_text_val and len(clean_text_val) > 2:
            disease_texts.append(clean_text_val)
            disease_indices.append(disease_sample.iloc[idx].name)
    
    # 유사 매칭 수행
    match_count = 0
    for suga_idx, suga_text in enumerate(suga_sample[suga_col]):
        clean_suga = clean_text(suga_text)
        if not clean_suga or len(clean_suga) < 3:
            continue
        
        if disease_texts:
            best_match = process.extractOne(clean_suga, disease_texts, scorer=fuzz.partial_ratio)
            if best_match and best_match[1] >= threshold:
                # 원래 인덱스 찾기
                disease_text_idx = disease_texts.index(best_match[0])
                original_disease_idx = disease_indices[disease_text_idx]
                
                matches.append({
                    'suga_idx': suga_sample.iloc[suga_idx].name,
                    'disease_idx': original_disease_idx,
                    'match_type': 'fuzzy',
                    'match_col': f'{suga_col}_{disease_col}',
                    'similarity': best_match[1]
                })
                match_count += 1
                
                if match_count % 50 == 0:
                    print(f"  유사매칭 진행: {match_count}개")
    
    print(f"  완료: {len(matches)}개 유사매칭")
    return matches

def create_integrated_table(suga_df, disease_df, all_matches):
    """통합 테이블 생성"""
    print("통합 테이블 생성 중...")
    result_rows = []
    
    for i, match in enumerate(all_matches):
        try:
            suga_row = suga_df.iloc[match['suga_idx']]
            disease_row = disease_df.iloc[match['disease_idx']]
            
            result_rows.append({
                '수가코드': str(suga_row.get('수가코드', '')),
                '수가명_한글': str(suga_row.get('한글명', '')),
                '수가명_영문': str(suga_row.get('영문명', '')),
                '단가정보': str(suga_row.get('상대가치점수', '')),
                '상병코드': str(disease_row.get('상병코드', '')),
                '상병명_한글': str(disease_row.get('한글명', '')),
                '상병명_영문': str(disease_row.get('영문명', '')),
                '매칭타입': match['match_type'],
                '매칭컬럼': match['match_col'],
                '유사도': match['similarity']
            })
            
            if (i + 1) % 500 == 0:
                print(f"  처리 진행: {i + 1}개")
                
        except Exception as e:
            print(f"  행 처리 오류 (인덱스 {i}): {e}")
            continue
    
    print(f"통합 테이블 완료: {len(result_rows)}행")
    return pd.DataFrame(result_rows)

def main():
    print("=== 의료 수가-상병코드 매핑 (최종 버전) ===")
    
    # 1. 데이터 로드
    suga_df, disease_df = load_data()
    if suga_df is None or disease_df is None:
        print("데이터 로드 실패")
        return
    
    # 2. 매핑 실행
    print(f"\n=== 매핑 시작 ===")
    all_matches = []
    
    # 한글명 완전일치
    print("\n1. 한글명 완전일치 매핑")
    korean_exact_matches = exact_match_mapping(suga_df, disease_df, '한글명', '한글명')
    all_matches.extend(korean_exact_matches)
    
    # 영문명 완전일치 (영문명이 있는 경우만)
    print("\n2. 영문명 완전일치 매핑")
    suga_with_eng = suga_df.dropna(subset=['영문명'])
    disease_with_eng = disease_df.dropna(subset=['영문명'])
    if len(suga_with_eng) > 0 and len(disease_with_eng) > 0:
        english_exact_matches = exact_match_mapping(suga_with_eng, disease_with_eng, '영문명', '영문명')
        all_matches.extend(english_exact_matches)
    else:
        print("  영문명 데이터가 부족하여 건너뜀")
    
    # 한글명 유사매칭
    print("\n3. 한글명 유사매칭")
    korean_fuzzy_matches = fuzzy_match_mapping(suga_df, disease_df, '한글명', '한글명', threshold=80, max_samples=3000)
    all_matches.extend(korean_fuzzy_matches)
    
    print(f"\n총 매칭 결과: {len(all_matches)}개")
    
    # 3. 중복 제거
    print("중복 제거 중...")
    unique_matches = []
    seen_pairs = set()
    for match in all_matches:
        pair_key = (match['suga_idx'], match['disease_idx'])
        if pair_key not in seen_pairs:
            unique_matches.append(match)
            seen_pairs.add(pair_key)
    
    print(f"중복 제거 후: {len(unique_matches)}개")
    
    # 4. 통합 테이블 생성
    result_df = create_integrated_table(suga_df, disease_df, unique_matches)
    
    # 5. 결과 저장
    output_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medical_code_integrated_final.csv'
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n결과 저장 완료: {output_file}")
    
    # 6. 통계 출력
    print(f"\n=== 최종 결과 통계 ===")
    print(f"전체 매칭 수: {len(result_df)}")
    print(f"완전일치: {len(result_df[result_df['매칭타입'] == 'exact'])}개")
    print(f"유사매칭: {len(result_df[result_df['매칭타입'] == 'fuzzy'])}개")
    print(f"고유 수가코드: {result_df['수가코드'].nunique()}개")
    print(f"고유 상병코드: {result_df['상병코드'].nunique()}개")
    
    # 7. 샘플 결과
    print(f"\n=== 샘플 결과 ===")
    print(result_df.head(10)[['수가코드', '수가명_한글', '상병코드', '상병명_한글', '매칭타입', '유사도']])
    
    # 8. 고품질 매칭 통계
    high_quality = result_df[result_df['유사도'] >= 90]
    print(f"\n고품질 매칭 (유사도 90% 이상): {len(high_quality)}개")

if __name__ == "__main__":
    main()