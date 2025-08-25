#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
생성된 사전 파일들의 최종 정리 스크립트
"""

import re
from pathlib import Path

def clean_text(text):
    """텍스트 최종 정리"""
    if not text or len(text) < 2:
        return ''
    
    # 닫히지 않은 괄호 제거
    text = re.sub(r'\([^)]*$', '', text)
    
    # 빈 괄호나 공백만 있는 괄호 제거
    text = re.sub(r'\(\s*\)', '', text)
    
    # 괄호 안이 특수문자나 공백만인 경우 제거
    text = re.sub(r'\([/\s,]*\)', '', text)
    
    # 연속된 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 및 특수문자 제거
    text = text.strip(' ()/')
    
    return text

def clean_unique_terms():
    """고유명사 사전 정리"""
    print("고유명사 사전 정리 중...")
    
    input_file = Path("C:/Jimin/cg_suri_z-code360/pharmaLex_unity/result/dictionary_output/unique_terms.txt")
    output_file = input_file.with_name("unique_terms_clean.txt")
    
    cleaned_terms = set()
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            term = clean_text(line.strip())
            if term and len(term) > 1:
                cleaned_terms.add(term)
    
    # 정렬 후 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        for term in sorted(cleaned_terms):
            f.write(f"{term}\n")
    
    print(f"  정리된 고유명사: {len(cleaned_terms)}개")
    print(f"  저장 위치: {output_file}")

def clean_search_synonyms():
    """검색 유의어 사전 정리"""
    print("검색 유의어 사전 정리 중...")
    
    input_file = Path("C:/Jimin/cg_suri_z-code360/pharmaLex_unity/result/dictionary_output/search_synonyms.csv")
    output_file = input_file.with_name("search_synonyms_clean.csv")
    
    with open(input_file, 'r', encoding='utf-8') as f_in:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            f_out.write("code,synonyms\n")
            
            for i, line in enumerate(f_in):
                if i == 0:  # 헤더 스킵
                    continue
                
                if '","' in line:
                    parts = line.strip().split('","')
                    if len(parts) >= 2:
                        code = parts[0].strip('"')
                        synonyms_str = parts[1].strip('"')
                        
                        # 유의어들 정리
                        synonyms = []
                        for synonym in synonyms_str.split(','):
                            cleaned = clean_text(synonym.strip())
                            if cleaned and len(cleaned) > 1:
                                synonyms.append(cleaned)
                        
                        # 중복 제거 후 저장
                        if synonyms:
                            unique_synonyms = sorted(list(set(synonyms)))[:10]  # 최대 10개
                            f_out.write(f'"{code}","{",".join(unique_synonyms)}"\n')
    
    print(f"  정리 완료: {output_file}")

def clean_code_mapping():
    """코드 매핑 사전 정리"""
    print("코드 매핑 사전 정리 중...")
    
    input_file = Path("C:/Jimin/cg_suri_z-code360/pharmaLex_unity/result/dictionary_output/code_mapping.txt")
    output_file = input_file.with_name("code_mapping_clean.txt")
    
    cleaned_mappings = {}
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if ' => ' in line:
                code, name = line.strip().split(' => ', 1)
                cleaned_name = clean_text(name)
                if cleaned_name and len(cleaned_name) > 1:
                    cleaned_mappings[code] = cleaned_name
    
    # 정렬 후 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        for code, name in sorted(cleaned_mappings.items()):
            f.write(f"{code} => {name}\n")
    
    print(f"  정리된 매핑: {len(cleaned_mappings)}개")
    print(f"  저장 위치: {output_file}")

def create_final_summary():
    """최종 요약 리포트 생성"""
    print("최종 요약 리포트 생성 중...")
    
    output_dir = Path("C:/Jimin/cg_suri_z-code360/pharmaLex_unity/result/dictionary_output")
    summary_file = output_dir / "final_summary.txt"
    
    summary = []
    summary.append("=== 의약품 사전 구축 완료 보고서 ===\n")
    summary.append(f"구축 일시: 2024년\n")
    
    # 파일별 통계
    files_info = [
        ("unique_terms_clean.txt", "고유명사 사전"),
        ("code_mapping_clean.txt", "코드-명칭 매핑"),
        ("search_synonyms_clean.csv", "통합 유의어 사전"),
        ("product_variants.txt", "상품명 변형 사전"),
        ("ingredient_dictionary.txt", "성분 한글-영문 사전"),
        ("complex_drugs.txt", "복합제 리스트")
    ]
    
    summary.append("생성된 사전 파일:")
    for filename, description in files_info:
        filepath = output_dir / filename
        if filepath.exists():
            if filename.endswith('.csv'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    line_count = len(f.readlines()) - 1  # 헤더 제외
            else:
                with open(filepath, 'r', encoding='utf-8') as f:
                    line_count = len(f.readlines())
            summary.append(f"  - {filename}: {description} ({line_count:,}개)")
        else:
            summary.append(f"  - {filename}: 파일 없음")
    
    # 사용법
    summary.append("\n=== OpenSearch 사전 사용법 ===")
    summary.append("1. unique_terms_clean.txt: 사용자 사전으로 로드")
    summary.append("2. search_synonyms_clean.csv: 동의어 사전으로 활용")
    summary.append("3. code_mapping_clean.txt: 코드 검색 기능에 활용")
    summary.append("4. product_variants.txt: 제품명 검색 확장에 활용")
    
    # 파일에 저장
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary))
    
    print(f"  최종 요약 리포트: {summary_file}")
    
    # 콘솔에도 출력
    print('\n'.join(summary))

if __name__ == "__main__":
    print("의약품 사전 최종 정리 시작")
    print("=" * 40)
    
    clean_unique_terms()
    clean_code_mapping()
    clean_search_synonyms()
    create_final_summary()
    
    print("\n모든 정리 작업이 완료되었습니다!")