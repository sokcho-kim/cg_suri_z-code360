import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz, process
import re
from typing import List, Tuple, Dict
import warnings
warnings.filterwarnings('ignore')

def load_excel_files():
    """수가파일과 상병코드 파일 로드 (최적화됨)"""
    try:
        # 수가 파일 로드 (주요 컬럼만)
        suga_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\★수가반영내역(25.8.1.기준)_전체판.xlsx'
        suga_df = pd.read_excel(suga_file, usecols=['수가코드', '한글명', '영문명', '상대가치점수'])
        print(f"수가 파일 로드 완료: {suga_df.shape}")
        
        # 상병코드 파일 로드 (시트명 확인하여 수정)
        disease_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\배포용 상병마스터_240101(2).xlsx'
        
        # 시트 이름 재확인
        xl_file = pd.ExcelFile(disease_file)
        print("상병코드 파일 시트 목록:", xl_file.sheet_names)
        
        # 올바른 시트명 사용
        sheet_name = '상병분류번호(전체)' if '상병분류번호(전체)' in xl_file.sheet_names else xl_file.sheet_names[1]
        disease_df = pd.read_excel(disease_file, sheet_name=sheet_name, header=10)
        
        # 필요한 컬럼만 선택
        available_cols = list(disease_df.columns)
        print("사용 가능한 컬럼:", available_cols[:5])
        
        # 컬럼명 매핑
        col_mapping = {}
        for col in available_cols:
            col_str = str(col).lower()
            if '상병' in col_str or '기호' in col_str or col == available_cols[0]:
                col_mapping['상병코드'] = col
            elif '한글' in col_str or '명' in col_str:
                if '상병코드' not in col_mapping:
                    col_mapping['한글명'] = col
                elif 'english' not in col_str.lower():
                    col_mapping['한글명'] = col
            elif 'english' in col_str or '영문' in col_str:
                col_mapping['영문명'] = col
        
        # 기본 컬럼 설정
        if '상병코드' not in col_mapping:
            col_mapping['상병코드'] = available_cols[0]
        if '한글명' not in col_mapping:
            col_mapping['한글명'] = available_cols[1] if len(available_cols) > 1 else available_cols[0]
        if '영문명' not in col_mapping:
            col_mapping['영문명'] = available_cols[2] if len(available_cols) > 2 else available_cols[1]
        
        print("컬럼 매핑:", col_mapping)
        
        # 데이터 추출
        disease_df = disease_df[[col_mapping['상병코드'], col_mapping['한글명'], col_mapping['영문명']]].copy()
        disease_df.columns = ['상병코드', '한글명', '영문명']
        print(f"상병코드 파일 로드 완료: {disease_df.shape}")
        
        # 결측값 제거
        suga_df = suga_df.dropna(subset=['한글명']).reset_index(drop=True)
        disease_df = disease_df.dropna(subset=['한글명']).reset_index(drop=True)
        
        print(f"정제 후 - 수가: {suga_df.shape}, 상병: {disease_df.shape}")
        return suga_df, disease_df
    
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        return None, None

def clean_text(text):
    """텍스트 정리 함수"""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    # 괄호와 특수문자 제거
    text = re.sub(r'[^\w\s가-힣a-zA-Z]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()

def exact_match_mapping(suga_df, disease_df, suga_col, disease_col):
    """완전 일치 매핑 (최적화됨)"""
    matches = []
    
    # 텍스트 정리 및 딕셔너리 생성
    disease_dict = {}
    for idx, text in enumerate(disease_df[disease_col]):
        clean_text_val = clean_text(text)
        if clean_text_val and len(clean_text_val) > 2:
            if clean_text_val not in disease_dict:
                disease_dict[clean_text_val] = []
            disease_dict[clean_text_val].append(idx)
    
    # 수가 데이터와 매칭
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
    
    return matches

def fuzzy_match_mapping_optimized(suga_df, disease_df, suga_col, disease_col, threshold=85, max_matches=1000):
    """최적화된 Fuzzy 매칭 (샘플링 사용)"""
    matches = []
    
    # 이미 완전일치된 항목 제외
    exact_matches = exact_match_mapping(suga_df, disease_df, suga_col, disease_col)
    exact_suga_indices = {match['suga_idx'] for match in exact_matches}
    
    # 샘플링으로 처리량 줄이기
    suga_sample = suga_df[~suga_df.index.isin(exact_suga_indices)].sample(
        min(5000, len(suga_df)), random_state=42
    )
    disease_sample = disease_df.sample(min(5000, len(disease_df)), random_state=42)
    
    # 텍스트 정리
    suga_texts = [clean_text(text) for text in suga_sample[suga_col]]
    disease_texts = [clean_text(text) for text in disease_sample[disease_col]]
    
    # 유효한 텍스트만 필터링
    valid_disease_texts = [(i, text) for i, text in enumerate(disease_texts) if text and len(text) > 3]
    
    count = 0
    for suga_idx, suga_text in enumerate(suga_texts):
        if not suga_text or len(suga_text) < 3 or count >= max_matches:
            continue
            
        # 가장 유사한 상병코드 찾기
        if valid_disease_texts:
            disease_only_texts = [text for _, text in valid_disease_texts]
            best_match = process.extractOne(suga_text, disease_only_texts, scorer=fuzz.partial_ratio)
            
            if best_match and best_match[1] >= threshold:
                # 원래 인덱스 찾기
                disease_text_idx = disease_only_texts.index(best_match[0])
                original_disease_idx = valid_disease_texts[disease_text_idx][0]
                
                matches.append({
                    'suga_idx': suga_sample.iloc[suga_idx].name,  # 원래 인덱스
                    'disease_idx': disease_sample.iloc[original_disease_idx].name,  # 원래 인덱스
                    'match_type': 'fuzzy',
                    'match_col': f'{suga_col}_{disease_col}',
                    'similarity': best_match[1]
                })
                count += 1
    
    return matches

def create_integrated_table(suga_df, disease_df, all_matches):
    """통합 테이블 생성"""
    result_rows = []
    
    for match in all_matches:
        try:
            suga_row = suga_df.iloc[match['suga_idx']]
            disease_row = disease_df.iloc[match['disease_idx']]
            
            result_rows.append({
                '수가코드': suga_row.get('수가코드', ''),
                '수가명_한글': suga_row.get('한글명', ''),
                '수가명_영문': suga_row.get('영문명', ''),
                '단가정보': suga_row.get('상대가치점수', ''),
                '상병코드': disease_row.get('상병코드', ''),
                '상병명_한글': disease_row.get('한글명', ''),
                '상병명_영문': disease_row.get('영문명', ''),
                '매칭타입': match['match_type'],
                '매칭컬럼': match['match_col'],
                '유사도': match['similarity']
            })
        except Exception as e:
            print(f"행 처리 오류: {e}")
            continue
    
    return pd.DataFrame(result_rows)

def main():
    print("의료 수가-상병코드 매핑 시작 (최적화 버전)...")
    
    # 1. 파일 로드
    suga_df, disease_df = load_excel_files()
    
    if suga_df is None or disease_df is None:
        print("파일 로드 실패")
        return
    
    print(f"\n수가 데이터: {suga_df.shape[0]}행")
    print(f"상병 데이터: {disease_df.shape[0]}행")
    
    # 2. 매핑 실행
    print("\n=== 매핑 시작 ===")
    all_matches = []
    
    # 한글명 기준 완전일치 매핑
    print("1. 한글명 완전일치 매핑...")
    korean_exact_matches = exact_match_mapping(suga_df, disease_df, '한글명', '한글명')
    all_matches.extend(korean_exact_matches)
    print(f"   한글명 완전일치: {len(korean_exact_matches)}개")
    
    # 영문명 기준 완전일치 매핑
    print("2. 영문명 완전일치 매핑...")
    english_exact_matches = exact_match_mapping(suga_df, disease_df, '영문명', '영문명')
    all_matches.extend(english_exact_matches)
    print(f"   영문명 완전일치: {len(english_exact_matches)}개")
    
    # Fuzzy 매핑 (한글명만, 샘플링)
    print("3. 한글명 유사도 매핑 (샘플링)...")
    korean_fuzzy_matches = fuzzy_match_mapping_optimized(suga_df, disease_df, '한글명', '한글명', threshold=80, max_matches=2000)
    all_matches.extend(korean_fuzzy_matches)
    print(f"   한글명 유사매칭: {len(korean_fuzzy_matches)}개")
    
    print(f"\n총 매칭 결과: {len(all_matches)}개")
    
    # 3. 통합 테이블 생성
    print("4. 통합 테이블 생성...")
    result_df = create_integrated_table(suga_df, disease_df, all_matches)
    print(f"   통합 테이블 크기: {result_df.shape}")
    
    # 4. 결과 저장
    output_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medical_code_integrated.csv'
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"5. 결과 저장 완료: {output_file}")
    
    # 5. 결과 미리보기
    print("\n=== 결과 미리보기 ===")
    print(result_df.head(10))
    
    # 6. 통계 정보
    print("\n=== 매칭 통계 ===")
    print(f"전체 매칭 수: {len(result_df)}")
    print(f"완전일치: {len(result_df[result_df['매칭타입'] == 'exact'])}")
    print(f"유사매칭: {len(result_df[result_df['매칭타입'] == 'fuzzy'])}")
    print(f"고유 수가코드 수: {result_df['수가코드'].nunique()}")
    print(f"고유 상병코드 수: {result_df['상병코드'].nunique()}")
    
    # 7. 고품질 매칭 추출 (유사도 90% 이상)
    high_quality = result_df[result_df['유사도'] >= 90]
    print(f"고품질 매칭 (유사도 90% 이상): {len(high_quality)}개")

if __name__ == "__main__":
    main()