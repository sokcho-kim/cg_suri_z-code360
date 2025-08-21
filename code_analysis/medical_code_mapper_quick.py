import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz, process
import re
import warnings
warnings.filterwarnings('ignore')

def load_sample_data():
    """샘플 데이터 로드"""
    try:
        # 수가 파일 로드 (처음 1000행만)
        suga_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\★수가반영내역(25.8.1.기준)_전체판.xlsx'
        suga_df = pd.read_excel(suga_file, usecols=['수가코드', '한글명', '영문명', '상대가치점수'], nrows=1000)
        print(f"수가 파일 로드 완료: {suga_df.shape}")
        
        # 상병코드 파일 로드 (처음 1000행만)
        disease_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\배포용 상병마스터_240101(2).xlsx'
        xl_file = pd.ExcelFile(disease_file)
        sheet_name = xl_file.sheet_names[1]  # 두 번째 시트 사용
        
        # 다양한 헤더 위치 시도
        disease_df = None
        for header_row in range(15):
            try:
                temp_df = pd.read_excel(disease_file, sheet_name=sheet_name, header=header_row, nrows=1000)
                if len(temp_df.columns) >= 3 and temp_df.shape[0] > 100:
                    # 상병코드 패턴 확인
                    first_col = temp_df.iloc[:10, 0].astype(str)
                    if any(len(val) >= 3 and val[0].isalpha() for val in first_col):
                        disease_df = temp_df
                        print(f"상병코드 시트 발견: 헤더 행 {header_row}")
                        break
            except:
                continue
        
        if disease_df is None:
            print("상병코드 데이터를 찾지 못했습니다.")
            return None, None
        
        # 컬럼 정리
        disease_df = disease_df.iloc[:, :3].copy()  # 처음 3개 컬럼만
        disease_df.columns = ['상병코드', '한글명', '영문명']
        
        # 결측값 제거
        suga_df = suga_df.dropna(subset=['한글명']).reset_index(drop=True)
        disease_df = disease_df.dropna(subset=['한글명']).reset_index(drop=True)
        
        print(f"정제 후 - 수가: {suga_df.shape}, 상병: {disease_df.shape}")
        return suga_df, disease_df
    
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        return None, None

def clean_text(text):
    """텍스트 정리"""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    text = re.sub(r'[^\w\s가-힣a-zA-Z]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()

def find_matches(suga_df, disease_df):
    """간단한 매칭 찾기"""
    matches = []
    
    # 1. 완전 일치 찾기
    print("완전 일치 매칭...")
    disease_korean_dict = {}
    for idx, korean in enumerate(disease_df['한글명']):
        clean_korean = clean_text(korean)
        if clean_korean and len(clean_korean) > 2:
            disease_korean_dict[clean_korean] = idx
    
    for suga_idx, suga_korean in enumerate(suga_df['한글명']):
        clean_suga = clean_text(suga_korean)
        if clean_suga in disease_korean_dict:
            matches.append({
                'suga_idx': suga_idx,
                'disease_idx': disease_korean_dict[clean_suga],
                'match_type': 'exact',
                'similarity': 100
            })
    
    print(f"완전 일치: {len(matches)}개")
    
    # 2. 유사 매칭 (제한적으로)
    print("유사 매칭...")
    matched_suga = {m['suga_idx'] for m in matches}
    
    # 샘플링으로 처리량 제한
    remaining_suga = suga_df[~suga_df.index.isin(matched_suga)].head(200)
    disease_sample = disease_df.head(200)
    
    for suga_idx, suga_row in remaining_suga.iterrows():
        suga_text = clean_text(suga_row['한글명'])
        if not suga_text or len(suga_text) < 3:
            continue
        
        disease_texts = [clean_text(text) for text in disease_sample['한글명'] if clean_text(text)]
        
        if disease_texts:
            best_match = process.extractOne(suga_text, disease_texts, scorer=fuzz.partial_ratio)
            if best_match and best_match[1] >= 80:
                # 원래 인덱스 찾기
                disease_idx = None
                for idx, disease_text in enumerate(disease_sample['한글명']):
                    if clean_text(disease_text) == best_match[0]:
                        disease_idx = disease_sample.iloc[idx].name
                        break
                
                if disease_idx is not None:
                    matches.append({
                        'suga_idx': suga_idx,
                        'disease_idx': disease_idx,
                        'match_type': 'fuzzy',
                        'similarity': best_match[1]
                    })
    
    print(f"총 매칭: {len(matches)}개")
    return matches

def create_result_table(suga_df, disease_df, matches):
    """결과 테이블 생성"""
    results = []
    
    for match in matches:
        try:
            suga_row = suga_df.iloc[match['suga_idx']]
            disease_row = disease_df.iloc[match['disease_idx']]
            
            results.append({
                '수가코드': suga_row['수가코드'],
                '수가명_한글': suga_row['한글명'],
                '수가명_영문': suga_row.get('영문명', ''),
                '단가정보': suga_row.get('상대가치점수', ''),
                '상병코드': disease_row['상병코드'],
                '상병명_한글': disease_row['한글명'],
                '상병명_영문': disease_row.get('영문명', ''),
                '매칭타입': match['match_type'],
                '유사도': match['similarity']
            })
        except Exception as e:
            continue
    
    return pd.DataFrame(results)

def main():
    print("=== 의료 수가-상병코드 매핑 (퀵 테스트) ===")
    
    # 1. 데이터 로드
    suga_df, disease_df = load_sample_data()
    if suga_df is None or disease_df is None:
        return
    
    # 2. 매칭 수행
    matches = find_matches(suga_df, disease_df)
    
    # 3. 결과 테이블 생성
    result_df = create_result_table(suga_df, disease_df, matches)
    
    # 4. 결과 저장
    output_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medical_code_sample_result.csv'
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"\n=== 결과 ===")
    print(f"매칭 결과: {len(result_df)}개")
    print(f"완전일치: {len(result_df[result_df['매칭타입'] == 'exact'])}개")
    print(f"유사매칭: {len(result_df[result_df['매칭타입'] == 'fuzzy'])}개")
    print(f"결과 저장: {output_file}")
    
    print(f"\n=== 샘플 결과 ===")
    print(result_df.head(10))

if __name__ == "__main__":
    main()