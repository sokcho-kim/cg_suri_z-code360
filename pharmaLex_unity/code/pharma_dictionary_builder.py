#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
의약품 사전 구축 스크립트

CSV 파일을 읽어서 OpenSearch용 의약품 사전을 생성합니다.
- 데이터 정규화 (용량/개수 정보 제거)
- 고유명사 사전 생성
- 코드-명칭 매핑 사전 생성
- 상품명 변형 사전 생성
- 성분 한글-영문 사전 생성
- 통합 유의어 사전 생성
"""

import pandas as pd
import numpy as np
import re
import os
from collections import defaultdict
from pathlib import Path

class PharmaDictionaryBuilder:
    def __init__(self, csv_path):
        """
        초기화
        
        Args:
            csv_path (str): CSV 파일 경로
        """
        self.csv_path = csv_path
        self.df = None
        self.output_dir = Path(csv_path).parent / "dictionary_output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 정규식 패턴들
        self.dose_patterns = [
            # 용량 정보 패턴
            r'\d+\.?\d*\s?(mg|g|ml|μg|mcg|㎎|㎖|㎍|L|IU|I\.U|unit|units?)\b',
            r'\d+\.?\d*\s?(밀리그램|그램|밀리리터|리터|단위|아이유)\b',
            r'\d+\.?\d*\s?(milligram|gram|milliliter|liter|international\s+unit)\b',
            
            # 개수/포장 정보 패턴
            r'\d+\s?(정|캡슐|포|병|앰플|바이알|튜브|개)\b',
            r'\d+\s?(tablet|capsule|vial|ampoule|bottle|tube)\b',
            
            # 괄호 안의 용량 정보
            r'\([^)]*\d+\.?\d*\s?(mg|g|ml|μg|mcg|㎎|㎖|㎍|L|IU|I\.U|unit)[^)]*\)',
            r'\([^)]*\d+\s?(정|캡슐|포)[^)]*\)',
            
            # 특수 패턴
            r'_\([^)]*\d+[^)]*\)',  # _(숫자포함) 패턴
            r'\d+mg/\d+ml',  # mg/ml 패턴
            r'\d+mg/\d+정',  # mg/정 패턴
            r'\d+\.?\d*%',  # 퍼센트 패턴
        ]
        
        # 의학 약어 매핑
        self.medical_abbreviations = {
            'INJ': 'injection',
            'TAB': 'tablet',
            'CAP': 'capsule',
            'SYR': 'syrup',
            'SOL': 'solution',
            'SUSP': 'suspension',
            'CR': 'controlled release',
            'SR': 'sustained release',
            'XR': 'extended release',
            'ER': 'extended release'
        }
        
    def load_data(self):
        """CSV 파일 로드"""
        print(f"CSV 파일 로딩: {self.csv_path}")
        self.df = pd.read_csv(self.csv_path, encoding='utf-8', low_memory=False)
        print(f"총 {len(self.df)}행, {len(self.df.columns)}컬럼 로드됨")
        
    def normalize_text(self, text):
        """
        텍스트 정규화
        
        Args:
            text (str): 정규화할 텍스트
            
        Returns:
            str: 정규화된 텍스트
        """
        if pd.isna(text) or text == '':
            return ''
            
        text = str(text).strip()
        
        # 1. 괄호 안의 용량/개수 정보 포함된 내용 제거
        text = re.sub(r'\([^)]*\d+[^)]*\)', '', text)
        
        # 2. 언더바로 시작하는 용량 정보 제거 (예: _(2mg/1캡슐))
        text = re.sub(r'_\([^)]+\)', '', text)
        
        # 3. 용량/개수 정보 제거
        for pattern in self.dose_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 4. 남은 빈 괄호 및 불완전한 괄호 제거
        text = re.sub(r'\(\s*\)', '', text)
        text = re.sub(r'\(\s*/\s*\)', '', text)
        text = re.sub(r'\([^)]*$', '', text)  # 닫히지 않은 괄호 제거
        
        # 5. 특수문자 정규화
        text = text.replace('-', ' ').replace('_', ' ')
        text = text.replace('/', ' ').replace(',', ' ')
        
        # 6. 연속된 공백을 단일 공백으로
        text = re.sub(r'\s+', ' ', text)
        
        # 7. 앞뒤 공백 및 특수문자 제거
        text = text.strip(' ()/')
        
        # 8. 최종 정리 - 빈 문자열이나 너무 짧은 문자열 처리
        if len(text) < 2:
            return ''
        
        return text
    
    def normalize_data(self):
        """데이터 정규화 수행"""
        print("\n데이터 정규화 시작...")
        
        # 주요 컬럼들 정규화
        columns_to_normalize = ['제품명', '제품명_공식']
        
        for col in columns_to_normalize:
            if col in self.df.columns:
                print(f"  {col} 컬럼 정규화 중...")
                self.df[f'{col}_normalized'] = self.df[col].apply(self.normalize_text)
        
        # 코드 컬럼 정리
        code_columns = ['주성분코드_x', '주성분코드_y', 'ingredient_code_final']
        for col in code_columns:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(str).str.strip()
        
        print("데이터 정규화 완료")
        
    def generate_unique_terms(self):
        """고유명사 사전(unique_terms.txt) 생성"""
        print("\n고유명사 사전 생성 중...")
        
        unique_terms = set()
        
        # 정규화된 제품명에서 고유 용어 추출
        for col in ['제품명_normalized', '제품명_공식_normalized']:
            if col in self.df.columns:
                terms = self.df[col].dropna().unique()
                for term in terms:
                    if term and len(term.strip()) > 0:
                        unique_terms.add(term.strip())
        
        # 정렬 후 저장
        unique_terms = sorted(list(unique_terms))
        
        output_path = self.output_dir / "unique_terms.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            for term in unique_terms:
                f.write(f"{term}\n")
        
        print(f"  고유명사 사전 저장: {output_path}")
        print(f"  총 {len(unique_terms)}개 고유 용어")
        
        return unique_terms
        
    def generate_code_mapping(self):
        """코드-명칭 매핑 사전(code_mapping.txt) 생성"""
        print("\n코드-명칭 매핑 사전 생성 중...")
        
        code_mapping = {}
        
        # 코드 우선순위: ingredient_code_final > 주성분코드_y > 주성분코드_x
        code_columns = ['ingredient_code_final', '주성분코드_y', '주성분코드_x']
        name_columns = ['제품명_normalized', '제품명_공식_normalized']
        
        for _, row in self.df.iterrows():
            # 코드 선택
            code = None
            for code_col in code_columns:
                if code_col in self.df.columns and pd.notna(row[code_col]) and str(row[code_col]).strip() != '':
                    code = str(row[code_col]).strip()
                    break
            
            if not code or code == 'nan':
                continue
                
            # 이미 매핑된 코드는 건너뛰기
            if code in code_mapping:
                continue
                
            # 명칭 선택
            name = None
            for name_col in name_columns:
                if name_col in self.df.columns and pd.notna(row[name_col]) and str(row[name_col]).strip() != '':
                    name = str(row[name_col]).strip()
                    break
            
            if name:
                code_mapping[code] = name
        
        # 저장
        output_path = self.output_dir / "code_mapping.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            for code, name in sorted(code_mapping.items()):
                f.write(f"{code} => {name}\n")
        
        print(f"  코드-명칭 매핑 사전 저장: {output_path}")
        print(f"  총 {len(code_mapping)}개 매핑")
        
        return code_mapping
        
    def generate_product_variants(self):
        """상품명 변형 사전(product_variants.txt) 생성"""
        print("\n상품명 변형 사전 생성 중...")
        
        # 주성분코드별로 그룹화
        variants_dict = defaultdict(set)
        
        code_col = 'ingredient_code_final'
        if code_col not in self.df.columns:
            code_col = '주성분코드_y' if '주성분코드_y' in self.df.columns else '주성분코드_x'
        
        grouped = self.df.groupby(code_col)
        
        for code, group in grouped:
            if pd.isna(code) or str(code).strip() == '':
                continue
                
            # 해당 그룹의 모든 정규화된 제품명 수집
            for col in ['제품명_normalized', '제품명_공식_normalized']:
                if col in self.df.columns:
                    names = group[col].dropna().unique()
                    for name in names:
                        name = str(name).strip()
                        if name and len(name) > 0:
                            variants_dict[str(code)].add(name)
        
        # 저장 (2개 이상의 변형이 있는 경우만)
        output_path = self.output_dir / "product_variants.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            variant_count = 0
            for code, variants in sorted(variants_dict.items()):
                if len(variants) > 1:
                    variants_list = sorted(list(variants))
                    f.write(f"{', '.join(variants_list)}\n")
                    variant_count += 1
        
        print(f"  상품명 변형 사전 저장: {output_path}")
        print(f"  총 {variant_count}개 변형 그룹")
        
        return variants_dict
        
    def generate_ingredient_dictionary(self):
        """성분 한글-영문 사전(ingredient_dictionary.txt) 생성"""
        print("\n성분 한글-영문 사전 생성 중...")
        
        ingredient_mapping = set()
        
        # ATC 매핑 파일이 있는지 확인하고 로드
        atc_mapping_path = Path(self.csv_path).parent.parent / "data" / "건강보험심사평가원_ATC코드 매핑 목록_20240630.csv"
        atc_mapping = {}
        
        if atc_mapping_path.exists():
            try:
                print("  ATC 코드 매핑 파일 로드 중...")
                atc_df = pd.read_csv(atc_mapping_path, encoding='utf-8')
                
                # ATC 코드별 한글-영문 매핑 구축
                for _, row in atc_df.iterrows():
                    if pd.notna(row.get('ATC코드')) and pd.notna(row.get('ATC코드 명칭')):
                        atc_code = str(row['ATC코드']).strip()
                        english_name = str(row['ATC코드 명칭']).strip().lower()
                        
                        # 제품명에서 한글 성분명 추출
                        if pd.notna(row.get('제품명')):
                            product_name = str(row['제품명'])
                            # 괄호 안의 한글 성분명 추출
                            korean_ingredients = re.findall(r'\(([^)]+)\)', product_name)
                            for korean_ingredient in korean_ingredients:
                                if any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in korean_ingredient):
                                    # 용량 정보가 없는 순수 성분명만
                                    clean_korean = self.normalize_text(korean_ingredient)
                                    if clean_korean and len(clean_korean) > 1:
                                        mapping_entry = f"{english_name}, {clean_korean}"
                                        ingredient_mapping.add(mapping_entry)
                                        
                                        # 띄어쓰기 변형도 추가
                                        if ' ' in clean_korean:
                                            no_space_korean = clean_korean.replace(' ', '')
                                            mapping_entry = f"{english_name}, {no_space_korean}"
                                            ingredient_mapping.add(mapping_entry)
                        
                print(f"  ATC 매핑에서 {len(ingredient_mapping)}개 성분 매핑 추출")
                        
            except Exception as e:
                print(f"  ATC 매핑 파일 로드 실패: {e}")
        
        # 기존 데이터에서 ATC 코드 기반 매핑 추가
        if 'ATC코드' in self.df.columns:
            grouped = self.df.groupby('ATC코드')
            
            for atc_code, group in grouped:
                if pd.isna(atc_code):
                    continue
                    
                names = set()
                for col in ['제품명_normalized', '제품명_공식_normalized']:
                    if col in self.df.columns:
                        group_names = group[col].dropna().unique()
                        for name in group_names:
                            name_str = str(name).strip()
                            if name_str and len(name_str) > 0:
                                names.add(name_str)
                
                # 동일 ATC 코드의 제품명들을 유의어로 처리
                if len(names) > 1:
                    names_list = sorted(list(names))[:5]  # 최대 5개까지만
                    ingredient_mapping.add(', '.join(names_list))
        
        # 저장
        output_path = self.output_dir / "ingredient_dictionary.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            for mapping in sorted(ingredient_mapping):
                f.write(f"{mapping}\n")
        
        print(f"  성분 한글-영문 사전 저장: {output_path}")
        print(f"  총 {len(ingredient_mapping)}개 매핑")
        
        return ingredient_mapping
        
    def generate_search_synonyms(self):
        """통합 유의어 사전(search_synonyms.csv) 생성"""
        print("\n통합 유의어 사전 생성 중...")
        
        synonyms_dict = defaultdict(set)
        
        # 주성분코드별로 그룹화
        code_col = 'ingredient_code_final'
        if code_col not in self.df.columns:
            code_col = '주성분코드_y' if '주성분코드_y' in self.df.columns else '주성분코드_x'
        
        grouped = self.df.groupby(code_col)
        
        for code, group in grouped:
            if pd.isna(code) or str(code).strip() == '':
                continue
                
            synonyms = set()
            
            # 모든 관련 명칭 수집
            for col in ['제품명_normalized', '제품명_공식_normalized']:
                if col in self.df.columns:
                    names = group[col].dropna().unique()
                    for name in names:
                        name = str(name).strip()
                        if name and len(name) > 0:
                            synonyms.add(name)
                            
                            # 띄어쓰기 변형 추가
                            if ' ' in name:
                                synonyms.add(name.replace(' ', ''))
                            else:
                                # 한글의 경우 적절한 위치에 띄어쓰기 추가 시도
                                if any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in name):
                                    # 간단한 규칙으로 띄어쓰기 추가 (예: 제품명 + 성분명 패턴)
                                    pass
            
            if len(synonyms) > 1:
                synonyms_dict[str(code)] = synonyms
        
        # CSV 형식으로 저장
        output_path = self.output_dir / "search_synonyms.csv"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("code,synonyms\n")
            for code, synonyms in sorted(synonyms_dict.items()):
                synonyms_list = sorted(list(synonyms))
                synonyms_str = ','.join(synonyms_list)
                f.write(f'"{code}","{synonyms_str}"\n')
        
        print(f"  통합 유의어 사전 저장: {output_path}")
        print(f"  총 {len(synonyms_dict)}개 코드의 유의어")
        
        return synonyms_dict
        
    def handle_complex_drugs(self):
        """복합제 및 특수 케이스 처리"""
        print("\n복합제 및 특수 케이스 처리 중...")
        
        complex_drugs = []
        
        # 복합제 패턴 감지
        complex_patterns = [r'[+/]', r'복합', r'배합', r'조합']
        
        for col in ['제품명_normalized', '제품명_공식_normalized']:
            if col in self.df.columns:
                for pattern in complex_patterns:
                    mask = self.df[col].str.contains(pattern, na=False, regex=True)
                    if mask.any():
                        complex_names = self.df.loc[mask, col].unique()
                        complex_drugs.extend(complex_names)
        
        # 복합제 리스트 저장
        if complex_drugs:
            output_path = self.output_dir / "complex_drugs.txt"
            with open(output_path, 'w', encoding='utf-8') as f:
                for drug in sorted(set(complex_drugs)):
                    f.write(f"{drug}\n")
            
            print(f"  복합제 리스트 저장: {output_path}")
            print(f"  총 {len(set(complex_drugs))}개 복합제")
        
        return complex_drugs
        
    def generate_quality_report(self):
        """품질 체크 및 리포트 생성"""
        print("\n품질 체크 수행 중...")
        
        report = []
        report.append("=== 의약품 사전 구축 품질 리포트 ===\n")
        
        # 기본 통계
        report.append(f"원본 데이터: {len(self.df)}행")
        report.append(f"고유 제품명: {self.df['제품명'].nunique() if '제품명' in self.df.columns else 0}개")
        report.append(f"고유 주성분코드: {self.df['주성분코드_x'].nunique() if '주성분코드_x' in self.df.columns else 0}개")
        
        # 정규화 효과 확인
        if '제품명_normalized' in self.df.columns:
            original_unique = self.df['제품명'].nunique()
            normalized_unique = self.df['제품명_normalized'].nunique()
            report.append(f"정규화 전후 고유값: {original_unique} -> {normalized_unique}")
        
        # 빈 값 체크
        for col in ['제품명', '주성분코드_x', '제품명_normalized']:
            if col in self.df.columns:
                null_count = self.df[col].isna().sum()
                empty_count = (self.df[col] == '').sum()
                report.append(f"{col} 빈 값: {null_count}개 null, {empty_count}개 빈 문자열")
        
        # 샘플 확인
        report.append("\n=== 정규화 샘플 ===")
        if '제품명' in self.df.columns and '제품명_normalized' in self.df.columns:
            sample_df = self.df[['제품명', '제품명_normalized']].dropna().head(10)
            for _, row in sample_df.iterrows():
                report.append(f"원본: {row['제품명']}")
                report.append(f"정규화: {row['제품명_normalized']}")
                report.append("")
        
        # 리포트 저장
        output_path = self.output_dir / "quality_report.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        print(f"  품질 리포트 저장: {output_path}")
        
        # 콘솔에도 출력
        print('\n'.join(report))
        
    def build_all_dictionaries(self):
        """모든 사전 구축 실행"""
        print("의약품 사전 구축 시작")
        print("=" * 50)
        
        try:
            # 1. 데이터 로드
            self.load_data()
            
            # 2. 데이터 정규화
            self.normalize_data()
            
            # 3. 각종 사전 생성
            self.generate_unique_terms()
            self.generate_code_mapping()
            self.generate_product_variants()
            self.generate_ingredient_dictionary()
            self.generate_search_synonyms()
            
            # 4. 복합제 처리
            self.handle_complex_drugs()
            
            # 5. 품질 체크
            self.generate_quality_report()
            
            print(f"\n모든 사전이 {self.output_dir}에 생성되었습니다.")
            print("생성된 파일:")
            for file_path in sorted(self.output_dir.glob("*.txt")) + sorted(self.output_dir.glob("*.csv")):
                print(f"  - {file_path.name}")
                
        except Exception as e:
            print(f"오류 발생: {e}")
            raise

if __name__ == "__main__":
    # CSV 파일 경로 설정
    csv_path = r"C:\Jimin\cg_suri_z-code360\pharmaLex_unity\result\meta_master_v2_1_ko_patched.csv"
    
    # 사전 구축기 초기화 및 실행
    builder = PharmaDictionaryBuilder(csv_path)
    builder.build_all_dictionaries()