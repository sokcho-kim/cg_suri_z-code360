#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개선된 유의어 사전 구축 스크립트

사용자 예시에 맞춘 완벽한 유의어 사전 생성:
포크랄시럽,포수클로랄,클로랄하이드레이트,chloral hydrate,클로랄 하이드레이트,클로랄하이드레이트
"""

import pandas as pd
import numpy as np
import re
from collections import defaultdict
from pathlib import Path

class EnhancedSynonymBuilder:
    def __init__(self):
        self.csv_path = r"C:\Jimin\cg_suri_z-code360\pharmaLex_unity\result\meta_master_v2_1_ko_patched.csv"
        self.atc_path = r"C:\Jimin\cg_suri_z-code360\pharmaLex_unity\data\건강보험심사평가원_ATC코드 매핑 목록_20240630.csv"
        self.output_dir = Path("C:/Jimin/cg_suri_z-code360/pharmaLex_unity/result/dictionary_output")
        
    def extract_all_variations(self, text):
        """텍스트에서 모든 변형 추출"""
        if pd.isna(text):
            return set()
        
        text = str(text).strip()
        variations = set()
        
        # 1. 원본 텍스트
        variations.add(text)
        
        # 2. 용량 정보 제거된 버전
        clean_text = self.remove_dosage_info(text)
        if clean_text and clean_text != text:
            variations.add(clean_text)
        
        # 3. 괄호 안 성분명들 추출
        ingredients = re.findall(r'\(([^)]+)\)', text)
        for ingredient in ingredients:
            clean_ingredient = self.remove_dosage_info(ingredient)
            if clean_ingredient and len(clean_ingredient) > 2:
                variations.add(clean_ingredient)
                
                # 띄어쓰기 변형
                if ' ' in clean_ingredient:
                    variations.add(clean_ingredient.replace(' ', ''))
                
                # 특수문자 변형
                if ',' in clean_ingredient:
                    for part in clean_ingredient.split(','):
                        part = part.strip()
                        if len(part) > 2:
                            variations.add(part)
                            if ' ' in part:
                                variations.add(part.replace(' ', ''))
        
        # 4. 제품명에서 브랜드명 추출
        brand_name = re.sub(r'\([^)]+\)', '', text)  # 괄호 제거
        brand_name = self.remove_dosage_info(brand_name).strip()
        if brand_name and len(brand_name) > 2:
            variations.add(brand_name)
        
        return variations
    
    def remove_dosage_info(self, text):
        """용량 정보 제거"""
        if not text:
            return ''
        
        text = str(text)
        
        # 용량 정보 패턴들
        patterns = [
            r'\d+\.?\d*\s?(mg|g|ml|μg|mcg|㎎|㎖|㎍|L|IU|I\.U|unit|units?|%)\b',
            r'\d+\.?\d*\s?(밀리그램|그램|밀리리터|리터|단위|아이유|퍼센트)\b',
            r'\d+\s?(정|캡슐|포|병|앰플|바이알|튜브|개|tab|cap)\b',
            r'_\([^)]+\)',  # _(용량정보)
            r'\d+mg/\d+ml',
            r'\d+mg/\d+정',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 정리
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.strip('()/_')
        
        return text
    
    def build_enhanced_synonyms(self):
        """개선된 유의어 사전 구축"""
        print("개선된 유의어 사전 구축 시작...")
        
        # 메인 데이터 로드
        print("메인 데이터 로드 중...")
        df = pd.read_csv(self.csv_path, encoding='utf-8', low_memory=False)
        
        # ATC 매핑 데이터 로드
        print("ATC 매핑 데이터 로드 중...")
        atc_english_mapping = {}
        try:
            atc_df = pd.read_csv(self.atc_path, encoding='cp949')
            
            # 주성분코드 → 영문명 매핑 구축
            for _, row in atc_df.iterrows():
                if pd.notna(row.get('주성분코드')) and pd.notna(row.get('ATC코드 명칭')):
                    ingredient_code = str(row['주성분코드']).strip()
                    english_name = str(row['ATC코드 명칭']).strip()
                    
                    if ingredient_code not in atc_english_mapping:
                        atc_english_mapping[ingredient_code] = set()
                    
                    # 다양한 영문 변형 추가
                    atc_english_mapping[ingredient_code].add(english_name)
                    atc_english_mapping[ingredient_code].add(english_name.lower())
                    
                    # 단어 분리
                    words = re.findall(r'[a-zA-Z]+', english_name)
                    for word in words:
                        if len(word) > 2:  # 2글자 이상
                            atc_english_mapping[ingredient_code].add(word)
                            atc_english_mapping[ingredient_code].add(word.lower())
                    
                    # 띄어쓰기 제거
                    no_space = english_name.replace(' ', '')
                    if len(no_space) > 3:
                        atc_english_mapping[ingredient_code].add(no_space)
                        atc_english_mapping[ingredient_code].add(no_space.lower())
            
            print(f"ATC 영문 매핑: {len(atc_english_mapping)}개 성분")
        except Exception as e:
            print(f"ATC 데이터 로드 실패: {e}")
        
        # 성분별 유의어 그룹 구축
        print("성분별 유의어 그룹 구축 중...")
        synonym_groups = defaultdict(set)
        
        # 주성분코드 컬럼들
        code_columns = ['ingredient_code_final', '주성분코드_y', '주성분코드_x']
        name_columns = ['제품명', '제품명_공식']
        
        # 1. 주성분코드별 그룹화
        for code_col in code_columns:
            if code_col not in df.columns:
                continue
            
            print(f"  {code_col} 기준으로 처리 중...")
            
            for ingredient_code, group in df.groupby(code_col):
                if pd.isna(ingredient_code) or str(ingredient_code).strip() == '':
                    continue
                
                ingredient_code = str(ingredient_code).strip()
                all_variations = set()
                
                # 제품명들에서 모든 변형 추출
                for name_col in name_columns:
                    if name_col in df.columns:
                        for product_name in group[name_col].dropna().unique():
                            variations = self.extract_all_variations(product_name)
                            all_variations.update(variations)
                
                # 영문명 추가
                if ingredient_code in atc_english_mapping:
                    all_variations.update(atc_english_mapping[ingredient_code])
                
                # 유효한 변형들만 필터링
                filtered_variations = set()
                for var in all_variations:
                    if isinstance(var, str) and len(var.strip()) > 1:
                        var = var.strip()
                        # 숫자로만 구성된 것은 제외
                        if not var.replace('.', '').replace('-', '').isdigit():
                            filtered_variations.add(var)
                
                if len(filtered_variations) >= 2:  # 최소 2개 이상의 유의어
                    synonym_groups[ingredient_code] = filtered_variations
        
        # 2. 중복 그룹 제거 및 정리
        print("중복 그룹 제거 및 정리 중...")
        
        final_synonyms = []
        processed_signatures = set()
        
        for ingredient_code, synonyms in synonym_groups.items():
            if len(synonyms) < 2:
                continue
            
            # 정렬하여 중복 체크
            sorted_synonyms = sorted(list(synonyms))
            signature = '|'.join(sorted_synonyms[:10])  # 처음 10개로 시그니처 생성
            
            if signature in processed_signatures:
                continue
            processed_signatures.add(signature)
            
            # 최대 20개까지만 (너무 길어지지 않도록)
            if len(sorted_synonyms) > 20:
                # 한글, 영문 균형있게 선택
                korean_terms = [s for s in sorted_synonyms if any(0xAC00 <= ord(c) <= 0xD7A3 for c in s)]
                english_terms = [s for s in sorted_synonyms if re.match(r'^[a-zA-Z\s]+$', s)]
                other_terms = [s for s in sorted_synonyms if s not in korean_terms and s not in english_terms]
                
                selected_terms = korean_terms[:10] + english_terms[:10] + other_terms[:5]
                sorted_synonyms = sorted(list(set(selected_terms)))[:20]
            
            final_synonyms.append(','.join(sorted_synonyms))
        
        # 3. 파일 저장
        output_path = self.output_dir / "enhanced_search_synonyms.txt"
        
        print(f"최종 결과 저장 중...")
        with open(output_path, 'w', encoding='utf-8') as f:
            for synonym_line in sorted(final_synonyms):
                f.write(f"{synonym_line}\n")
        
        print(f"\n=== 개선된 유의어 사전 구축 완료 ===")
        print(f"총 {len(final_synonyms)}개 유의어 그룹 생성")
        print(f"저장 위치: {output_path}")
        
        # 샘플 출력 (사용자 예시와 비슷한 것들)
        print(f"\n=== 주요 유의어 그룹 샘플 ===")
        
        sample_keywords = ['클로랄', 'chloral', '아세트', '아스피린']
        
        found_samples = []
        for synonym_line in final_synonyms:
            for keyword in sample_keywords:
                if keyword.lower() in synonym_line.lower():
                    found_samples.append(synonym_line)
                    break
            if len(found_samples) >= 5:
                break
        
        for i, sample in enumerate(found_samples[:5], 1):
            terms = sample.split(',')
            print(f"{i}. {terms[0]} 등 {len(terms)}개 유의어")
            print(f"   → {sample}")
            print()
        
        return final_synonyms

if __name__ == "__main__":
    builder = EnhancedSynonymBuilder()
    builder.build_enhanced_synonyms()