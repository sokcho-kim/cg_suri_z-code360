import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz, process
import re
from typing import List, Tuple, Dict
import warnings
warnings.filterwarnings('ignore')

def load_excel_files():
    """수가파일과 상병코드 파일 로드"""
    try:
        # 수가 파일 로드
        suga_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\★수가반영내역(25.8.1.기준)_전체판.xlsx'
        suga_df = pd.read_excel(suga_file)
        print(f"수가 파일 로드 완료: {suga_df.shape}")
        print("수가 파일 컬럼:", list(suga_df.columns))
        print("수가 파일 샘플:")
        print(suga_df.head())
        print("\n" + "="*50 + "\n")
        
        # 상병코드 파일 로드 - 다양한 시트와 헤더 위치 시도
        disease_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\배포용 상병마스터_240101(2).xlsx'
        
        # Excel 파일의 모든 시트 이름 확인
        xl_file = pd.ExcelFile(disease_file)
        print("상병코드 파일 시트 목록:", xl_file.sheet_names)
        
        # 특정 시트 우선 확인 (상병분류번호 시트)
        disease_df = None
        priority_sheets = ['상병분류번호(상병코드)', '상병분류번호(전체)']
        
        for sheet_name in priority_sheets + xl_file.sheet_names:
            if sheet_name not in xl_file.sheet_names:
                continue
                
            print(f"\n시트 '{sheet_name}' 확인 중...")
            
            # 다양한 헤더 위치 시도
            for header_row in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
                try:
                    temp_df = pd.read_excel(disease_file, sheet_name=sheet_name, header=header_row)
                    
                    # 너무 작은 데이터는 건너뛰기
                    if temp_df.shape[0] < 100:
                        continue
                        
                    print(f"  헤더 행 {header_row}: {temp_df.shape}, 컬럼 수: {len(temp_df.columns)}")
                    
                    # 실제 데이터가 있는 행 찾기
                    valid_rows = 0
                    for idx in range(min(10, len(temp_df))):
                        row = temp_df.iloc[idx]
                        if not row.isna().all() and str(row.iloc[0]).strip() != '':
                            valid_rows += 1
                    
                    if valid_rows >= 5:  # 최소 5개 유효 행
                        print(f"  유효한 데이터 행: {valid_rows}")
                        print(f"  컬럼: {list(temp_df.columns)[:5]}...")  # 처음 5개만
                        print(f"  샘플 데이터:")
                        print(temp_df.iloc[:3, :5])  # 3행 5열만
                        
                        # 상병코드 패턴 확인 (A00-Z99, 숫자+문자 조합 등)
                        first_col_sample = temp_df.iloc[:100, 0].dropna().astype(str)
                        code_pattern_count = 0
                        
                        for val in first_col_sample:
                            val = val.strip()
                            # 상병코드 패턴: A00, A001, B12 등
                            if len(val) >= 3 and (
                                (val[0].isalpha() and val[1:3].isdigit()) or  # A00 패턴
                                (val[0].isalpha() and val[1:].replace('.', '').isdigit())  # A00.1 패턴
                            ):
                                code_pattern_count += 1
                        
                        print(f"  상병코드 패턴 매칭: {code_pattern_count}/{len(first_col_sample)}")
                        
                        if code_pattern_count > len(first_col_sample) * 0.5:  # 50% 이상 매칭
                            disease_df = temp_df
                            print(f"  ✓ 유효한 상병코드 시트 발견: {sheet_name}, 헤더 행: {header_row}")
                            break
                            
                except Exception as e:
                    continue
            
            if disease_df is not None:
                break
        
        if disease_df is None:
            print("유효한 상병코드 데이터를 찾지 못했습니다.")
            return suga_df, None
            
        print(f"\n최종 상병코드 파일 로드 완료: {disease_df.shape}")
        print("상병코드 파일 컬럼:", list(disease_df.columns))
        print("상병코드 파일 샘플:")
        print(disease_df.head())
        
        return suga_df, disease_df
    
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        return None, None

def clean_text(text):
    """텍스트 정리 함수"""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    # 특수문자 제거 및 공백 정리
    text = re.sub(r'[^\w\s가-힣]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def exact_match_mapping(suga_df, disease_df, suga_col, disease_col):
    """완전 일치 매핑"""
    matches = []
    
    # 텍스트 정리
    suga_clean = suga_df[suga_col].apply(clean_text)
    disease_clean = disease_df[disease_col].apply(clean_text)
    
    # 완전 일치 찾기
    for suga_idx, suga_text in enumerate(suga_clean):
        if suga_text == "":
            continue
            
        for disease_idx, disease_text in enumerate(disease_clean):
            if disease_text == "":
                continue
                
            if suga_text.lower() == disease_text.lower():
                matches.append({
                    'suga_idx': suga_idx,
                    'disease_idx': disease_idx,
                    'match_type': 'exact',
                    'match_col': f'{suga_col}_{disease_col}',
                    'similarity': 100
                })
    
    return matches

def fuzzy_match_mapping(suga_df, disease_df, suga_col, disease_col, threshold=80):
    """Fuzzy 매칭 (부분 일치)"""
    matches = []
    
    # 텍스트 정리
    suga_clean = suga_df[suga_col].apply(clean_text)
    disease_clean = disease_df[disease_col].apply(clean_text)
    
    # 이미 완전 일치된 항목들 제외를 위한 세트
    exact_matches = set()
    
    for suga_idx, suga_text in enumerate(suga_clean):
        if suga_text == "" or len(suga_text) < 3:
            continue
            
        # 가장 유사한 상병코드 찾기
        disease_texts = [text for text in disease_clean if text != "" and len(text) >= 3]
        
        if disease_texts:
            best_match = process.extractOne(suga_text, disease_texts, scorer=fuzz.partial_ratio)
            
            if best_match and best_match[1] >= threshold:
                # 해당 인덱스 찾기
                disease_idx = disease_clean[disease_clean == best_match[0]].index[0]
                
                # 완전 일치가 아닌 경우만 추가
                if best_match[1] < 100:
                    matches.append({
                        'suga_idx': suga_idx,
                        'disease_idx': disease_idx,
                        'match_type': 'fuzzy',
                        'match_col': f'{suga_col}_{disease_col}',
                        'similarity': best_match[1]
                    })
    
    return matches

def create_integrated_table(suga_df, disease_df, all_matches):
    """통합 테이블 생성"""
    result_rows = []
    
    for match in all_matches:
        suga_row = suga_df.iloc[match['suga_idx']]
        disease_row = disease_df.iloc[match['disease_idx']]
        
        # 수가 정보 추출
        suga_code = suga_row.iloc[0] if len(suga_row) > 0 else ""
        suga_kor = ""
        suga_eng = ""
        unit_price = ""
        
        # 컬럼명 기준으로 정보 추출
        for col in suga_df.columns:
            col_lower = str(col).lower()
            if '한글명' in str(col) or '명칭' in str(col):
                suga_kor = suga_row[col] if pd.notna(suga_row[col]) else ""
            elif '영문명' in str(col) or 'english' in col_lower:
                suga_eng = suga_row[col] if pd.notna(suga_row[col]) else ""
            elif '단가' in str(col) or '점수' in str(col) or 'price' in col_lower:
                unit_price = suga_row[col] if pd.notna(suga_row[col]) else ""
        
        # 상병 정보 추출
        disease_code = disease_row.iloc[0] if len(disease_row) > 0 else ""
        disease_kor = ""
        disease_eng = ""
        
        for col in disease_df.columns:
            col_lower = str(col).lower()
            if '한글명' in str(col) or '명칭' in str(col):
                disease_kor = disease_row[col] if pd.notna(disease_row[col]) else ""
            elif '영문명' in str(col) or 'english' in col_lower:
                disease_eng = disease_row[col] if pd.notna(disease_row[col]) else ""
        
        result_rows.append({
            '수가코드': suga_code,
            '수가명_한글': suga_kor,
            '수가명_영문': suga_eng,
            '단가정보': unit_price,
            '상병코드': disease_code,
            '상병명_한글': disease_kor,
            '상병명_영문': disease_eng,
            '매칭타입': match['match_type'],
            '매칭컬럼': match['match_col'],
            '유사도': match['similarity']
        })
    
    return pd.DataFrame(result_rows)

def main():
    print("의료 수가-상병코드 매핑 시작...")
    
    # 1. 파일 로드
    suga_df, disease_df = load_excel_files()
    
    if suga_df is None or disease_df is None:
        print("파일 로드 실패")
        return
    
    print(f"\n수가 데이터: {suga_df.shape[0]}행, {suga_df.shape[1]}열")
    print(f"상병 데이터: {disease_df.shape[0]}행, {disease_df.shape[1]}열")
    
    # 컬럼 분석
    print("\n=== 컬럼 분석 ===")
    print("수가 파일 컬럼:", list(suga_df.columns))
    print("상병 파일 컬럼:", list(disease_df.columns))
    
    # 2. 매핑 실행
    print("\n=== 매핑 시작 ===")
    all_matches = []
    
    # 한글명 기준 매핑
    print("1. 한글명 완전일치 매핑...")
    korean_exact_matches = exact_match_mapping(suga_df, disease_df, '한글명', '한글명')
    all_matches.extend(korean_exact_matches)
    print(f"   한글명 완전일치: {len(korean_exact_matches)}개")
    
    # 영문명 기준 매핑
    print("2. 영문명 완전일치 매핑...")
    english_exact_matches = exact_match_mapping(suga_df, disease_df, '영문명', '영문명')
    all_matches.extend(english_exact_matches)
    print(f"   영문명 완전일치: {len(english_exact_matches)}개")
    
    # Fuzzy 매핑 (한글명)
    print("3. 한글명 유사도 매핑...")
    korean_fuzzy_matches = fuzzy_match_mapping(suga_df, disease_df, '한글명', '한글명', threshold=85)
    all_matches.extend(korean_fuzzy_matches)
    print(f"   한글명 유사매칭: {len(korean_fuzzy_matches)}개")
    
    # Fuzzy 매핑 (영문명)
    print("4. 영문명 유사도 매핑...")
    english_fuzzy_matches = fuzzy_match_mapping(suga_df, disease_df, '영문명', '영문명', threshold=85)
    all_matches.extend(english_fuzzy_matches)
    print(f"   영문명 유사매칭: {len(english_fuzzy_matches)}개")
    
    print(f"\n총 매칭 결과: {len(all_matches)}개")
    
    # 3. 통합 테이블 생성
    print("5. 통합 테이블 생성...")
    result_df = create_integrated_table(suga_df, disease_df, all_matches)
    print(f"   통합 테이블 크기: {result_df.shape}")
    
    # 4. 결과 저장
    output_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medical_code_integrated.csv'
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"6. 결과 저장 완료: {output_file}")
    
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

if __name__ == "__main__":
    main()