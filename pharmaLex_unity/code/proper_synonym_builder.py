#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
올바른 유의어 사전 구축 스크립트

동일 성분의 모든 변형(한글, 띄어쓰기, 성분명, 품명, 영문, 영문 성분명)을 
한 줄에 모아서 유의어 사전을 생성합니다.
"""

import pandas as pd
import numpy as np
import re
from collections import defaultdict
from pathlib import Path

class ProperSynonymBuilder:
    def __init__(self):
        self.csv_path = r"C:\Jimin\cg_suri_z-code360\pharmaLex_unity\result\meta_master_v2_1_ko_patched.csv"
        self.atc_path = r"C:\Jimin\cg_suri_z-code360\pharmaLex_unity\data\건강보험심사평가원_ATC코드 매핑 목록_20240630.csv"
        self.output_dir = Path("C:/Jimin/cg_suri_z-code360/pharmaLex_unity/result/dictionary_output")
        
    def extract_ingredient_from_product_name(self, product_name):
        """제품명에서 성분명 추출"""
        if pd.isna(product_name):
            return []
        
        # 괄호 안의 성분명들 추출
        ingredients = re.findall(r'\(([^)]+)\)', str(product_name))
        
        clean_ingredients = []
        for ingredient in ingredients:
            # 용량 정보 제거
            clean = re.sub(r'\d+\.?\d*\s?(mg|g|ml|μg|mcg|㎎|㎖|㎍|L|IU|I\.U|unit|units?)', '', ingredient, flags=re.IGNORECASE)
            clean = re.sub(r'\d+\.?\d*\s?(밀리그램|그램|밀리리터|리터|단위|아이유)', '', clean)
            
            # 특수문자 정리
            clean = clean.replace(',', ' ').replace('/', ' ')
            clean = re.sub(r'\s+', ' ', clean).strip()
            
            if clean and len(clean) > 2:
                clean_ingredients.append(clean)
                
                # 띄어쓰기 변형도 추가
                if ' ' in clean:
                    clean_ingredients.append(clean.replace(' ', ''))
        
        return clean_ingredients
    
    def clean_product_name(self, product_name):
        """제품명에서 용량 제거하여 깔끔한 제품명 생성"""
        if pd.isna(product_name):
            return ''
        
        name = str(product_name).strip()
        
        # 용량 정보가 포함된 괄호 제거
        name = re.sub(r'\([^)]*\d+[^)]*\)', '', name)
        name = re.sub(r'_\([^)]+\)', '', name)
        
        # 용량 정보 직접 제거
        patterns = [
            r'\d+\.?\d*\s?(mg|g|ml|μg|mcg|㎎|㎖|㎍|L|IU|I\.U|unit|units?)\b',
            r'\d+\.?\d*\s?(밀리그램|그램|밀리리터|리터|단위|아이유)\b',
            r'\d+\s?(정|캡슐|포|병|앰플|바이알|튜브|개)\b',
        ]
        
        for pattern in patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        # 정리
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def build_synonyms(self):
        """유의어 사전 구축"""
        print("유의어 사전 구축 시작...")
        
        # 메인 데이터 로드
        print("메인 데이터 로드 중...")
        df = pd.read_csv(self.csv_path, encoding='utf-8', low_memory=False)
        
        # ATC 매핑 데이터 로드
        print("ATC 매핑 데이터 로드 중...")
        try:
            atc_df = pd.read_csv(self.atc_path, encoding='cp949')
            print(f"ATC 데이터: {len(atc_df)}행 로드됨")
        except Exception as e:
            print(f"ATC 데이터 로드 실패: {e}")
            atc_df = pd.DataFrame()
        
        # 성분별 유의어 그룹 구축
        print("성분별 유의어 그룹 구축 중...")
        synonym_groups = defaultdict(set)
        
        # 1. 주성분코드별로 그룹화하여 제품명 수집
        ingredient_codes = ['ingredient_code_final', '주성분코드_y', '주성분코드_x']
        
        for code_col in ingredient_codes:
            if code_col not in df.columns:
                continue
                
            print(f"  {code_col} 기준으로 그룹화 중...")
            
            for ingredient_code, group in df.groupby(code_col):
                if pd.isna(ingredient_code) or str(ingredient_code).strip() == '':
                    continue
                
                ingredient_code = str(ingredient_code).strip()
                synonyms = set()
                
                # 제품명들 수집
                for col in ['제품명', '제품명_공식']:
                    if col in df.columns:
                        product_names = group[col].dropna().unique()
                        
                        for product_name in product_names:
                            # 원본 제품명 (용량 제거)
                            clean_name = self.clean_product_name(product_name)
                            if clean_name and len(clean_name) > 2:
                                synonyms.add(clean_name)
                                
                                # 띄어쓰기 변형
                                if ' ' in clean_name:
                                    synonyms.add(clean_name.replace(' ', ''))
                            
                            # 성분명들 추출
                            ingredients = self.extract_ingredient_from_product_name(product_name)
                            for ingredient in ingredients:
                                if ingredient and len(ingredient) > 2:
                                    synonyms.add(ingredient)
                
                if len(synonyms) > 0:
                    synonym_groups[ingredient_code].update(synonyms)
        
        # 2. ATC 코드 기반 영문명 추가
        if not atc_df.empty:
            print("ATC 기반 영문명 추가 중...")
            
            # ATC 데이터에서 성분코드별 영문명 매핑
            atc_mapping = {}
            for _, row in atc_df.iterrows():
                if pd.notna(row.get('주성분코드')) and pd.notna(row.get('ATC코드 명칭')):
                    ingredient_code = str(row['주성분코드']).strip()
                    english_name = str(row['ATC코드 명칭']).strip()
                    
                    if ingredient_code not in atc_mapping:
                        atc_mapping[ingredient_code] = set()
                    
                    # 영문명 추가
                    atc_mapping[ingredient_code].add(english_name)
                    atc_mapping[ingredient_code].add(english_name.lower())
                    
                    # 단어별로 분리해서도 추가 (복합 성분명의 경우)
                    words = re.findall(r'[a-zA-Z]+', english_name)
                    for word in words:
                        if len(word) > 3:  # 3글자 이상만
                            atc_mapping[ingredient_code].add(word)
                            atc_mapping[ingredient_code].add(word.lower())
            
            # 기존 synonym_groups에 영문명 추가
            for ingredient_code, english_names in atc_mapping.items():
                if ingredient_code in synonym_groups:
                    synonym_groups[ingredient_code].update(english_names)
        
        # 3. 동일 ATC 코드끼리 추가 연결 (메인 데이터에서)
        if 'ATC코드' in df.columns:
            print("ATC 코드 기반 추가 연결 중...")
            
            for atc_code, group in df.groupby('ATC코드'):
                if pd.isna(atc_code):
                    continue
                
                # 해당 ATC 코드의 모든 성분코드들 찾기
                related_codes = set()
                for code_col in ingredient_codes:
                    if code_col in df.columns:
                        codes = group[code_col].dropna().unique()
                        related_codes.update([str(c).strip() for c in codes])
                
                # 관련 코드들의 유의어들을 서로 연결
                all_synonyms = set()
                for code in related_codes:
                    if code in synonym_groups:
                        all_synonyms.update(synonym_groups[code])
                
                # 다시 분배
                for code in related_codes:
                    if code in synonym_groups:
                        synonym_groups[code].update(all_synonyms)
        
        # 4. 결과 정리 및 저장
        print("결과 정리 중...")
        
        final_synonyms = []
        processed_groups = set()
        
        for ingredient_code, synonyms in synonym_groups.items():
            if len(synonyms) < 2:  # 유의어가 1개 이하면 건너뛰기
                continue
            
            # 중복 그룹 제거를 위해 정렬된 문자열로 체크
            synonyms_sorted = sorted(list(synonyms))
            group_signature = ','.join(synonyms_sorted)
            
            if group_signature in processed_groups:
                continue
            processed_groups.add(group_signature)
            
            # 너무 많으면 상위 15개만 (빈도 기반으로 나중에 개선 가능)
            if len(synonyms_sorted) > 15:
                synonyms_sorted = synonyms_sorted[:15]
            
            final_synonyms.append(','.join(synonyms_sorted))
        
        # 5. 파일 저장
        output_path = self.output_dir / "proper_search_synonyms.txt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for synonym_line in sorted(final_synonyms):
                f.write(f"{synonym_line}\n")
        
        print(f"\n=== 유의어 사전 구축 완료 ===")
        print(f"총 {len(final_synonyms)}개 유의어 그룹 생성")
        print(f"저장 위치: {output_path}")
        
        # 샘플 출력
        print(f"\n=== 샘플 유의어 그룹 (처음 10개) ===")
        for i, synonym_line in enumerate(sorted(final_synonyms)[:10], 1):
            synonyms = synonym_line.split(',')
            print(f"{i:2d}. {synonyms[0]} 등 {len(synonyms)}개: {', '.join(synonyms[:5])}{'...' if len(synonyms) > 5 else ''}")
        
        return final_synonyms

if __name__ == "__main__":
    builder = ProperSynonymBuilder()
    builder.build_synonyms()