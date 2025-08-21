import pandas as pd
import re

def debug_data_structure():
    """데이터 구조 디버깅"""
    try:
        # 수가 파일 디버깅
        print("=== 수가 파일 디버깅 ===")
        suga_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\★수가반영내역(25.8.1.기준)_전체판.xlsx'
        suga_df = pd.read_excel(suga_file, nrows=10)
        print("수가 파일 컬럼:", list(suga_df.columns))
        print("수가 파일 샘플:")
        print(suga_df[['수가코드', '한글명']].head())
        
        # 상병코드 파일 디버깅  
        print("\n=== 상병코드 파일 디버깅 ===")
        disease_file = r'C:\Jimin\cg_suri_z-code360\code_analysis\medi_code\배포용 상병마스터_240101(2).xlsx'
        xl_file = pd.ExcelFile(disease_file)
        print("시트 목록:", xl_file.sheet_names)
        
        # 각 시트의 다양한 헤더 위치 확인
        for sheet_name in xl_file.sheet_names:
            print(f"\n--- 시트: {sheet_name} ---")
            for header_row in [0, 5, 10, 15]:
                try:
                    temp_df = pd.read_excel(disease_file, sheet_name=sheet_name, header=header_row, nrows=5)
                    print(f"헤더 행 {header_row}: {temp_df.shape}")
                    print(f"컬럼: {list(temp_df.columns)[:3]}")
                    print(f"첫 번째 컬럼 샘플: {list(temp_df.iloc[:3, 0])}")
                    print()
                except:
                    continue
        
    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    debug_data_structure()