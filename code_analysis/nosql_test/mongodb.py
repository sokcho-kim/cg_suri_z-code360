"""
건강보험 본인부담기준 NoSQL 구현 예시
MongoDB 기반 규칙 엔진 구현
"""

from pymongo import MongoClient
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

class InsuranceRulesEngine:
    def __init__(self, db_url: str = "mongodb://localhost:27017/"):
        self.client = MongoClient(db_url)
        self.db = self.client.insurance_db
        self.rules_collection = self.db.copayment_rules
        self.setup_indexes()
    
    def setup_indexes(self):
        """인덱스 설정으로 조회 성능 최적화"""
        self.rules_collection.create_index([
            ("hospital_type", 1),
            ("location", 1),
            ("patient_type", 1),
            ("age_group", 1)
        ])
        self.rules_collection.create_index([("rule_code", 1)])
        self.rules_collection.create_index([("effective_date", -1)])

    def insert_copayment_rules(self):
        """본인부담률 규칙 데이터 삽입"""
        
        # 1. 상급종합병원 규칙
        tertiary_hospital_rules = {
            "rule_id": "TH_001",
            "rule_code": "tertiary_hospital_copayment",
            "hospital_type": "상급종합병원",
            "location": "모든지역",
            "effective_date": datetime(2025, 1, 1),
            "rules": [
                {
                    "patient_type": "일반환자",
                    "conditions": {
                        "age_min": 0,
                        "age_max": 999,
                        "pregnancy": False
                    },
                    "copayment": {
                        "consultation_fee": {"rate": 100, "type": "percentage"},
                        "other_medical_cost": {"rate": 60, "type": "percentage"}
                    },
                    "calculation_rule": "진찰료비용의 100% + 나머지 요양급여비용의 60%",
                    "rounding": "100원미만 절사"
                },
                {
                    "patient_type": "임신부",
                    "conditions": {
                        "pregnancy": True
                    },
                    "copayment": {
                        "total_medical_cost": {"rate": 40, "type": "percentage"}
                    },
                    "calculation_rule": "요양급여비용총액의 40%",
                    "rounding": "100원미만 절사"
                }
            ],
            "special_rules": [
                {
                    "rule_name": "6세미만_본인부담률_감면",
                    "condition": {"age_max": 6},
                    "modification": {"multiplier": 0.7, "description": "환자 본인부담률의 70%"}
                },
                {
                    "rule_name": "저체중출생아",
                    "condition": {"birth_weight": "low"},
                    "copayment": {"rate": 5, "type": "percentage"}
                }
            ]
        }

        # 2. 종합병원 규칙
        general_hospital_rules = {
            "rule_id": "GH_001", 
            "rule_code": "general_hospital_copayment",
            "hospital_type": "종합병원",
            "location_rules": {
                "동지역": {
                    "일반환자": {
                        "일반": {"rate": 50, "type": "percentage"},
                        "임신부": {"rate": 30, "type": "percentage"},
                        "1세미만": {"rate": 15, "type": "percentage"}
                    },
                    "의약분업예외환자": {
                        "일반": {
                            "drug_cost": {"rate": 30, "type": "percentage"},
                            "other_cost": {"rate": 50, "type": "percentage"}
                        }
                    }
                },
                "읍면지역": {
                    "일반환자": {
                        "일반": {"rate": 45, "type": "percentage"},
                        "임신부": {"rate": 30, "type": "percentage"},
                        "1세미만": {"rate": 15, "type": "percentage"}
                    }
                }
            },
            "rounding": "100원미만 절사"
        }

        # 3. 의원급 규칙 (단계별 부담금)
        clinic_rules = {
            "rule_id": "CL_001",
            "rule_code": "clinic_copayment", 
            "hospital_type": "의원",
            "age_group": "6세이상",
            "tiered_copayment": [
                {
                    "range": {"min": 0, "max": 15000},
                    "copayment": {"amount": 1500, "type": "fixed"}
                },
                {
                    "range": {"min": 15001, "max": 20000},
                    "copayment": {"rate": 10, "type": "percentage"}
                },
                {
                    "range": {"min": 20001, "max": 25000},
                    "copayment": {"rate": 20, "type": "percentage"}
                },
                {
                    "range": {"min": 25001, "max": 999999999},
                    "copayment": {"rate": 30, "type": "percentage"}
                }
            ],
            "special_conditions": {
                "chronic_disease": {
                    "condition": "고혈압(I10)·당뇨(E11) 상병으로 지속 진료",
                    "rule": "해당 진찰료비용의 20%",
                    "min_amount": 25000
                }
            }
        }

        # 4. 약국 규칙
        pharmacy_rules = {
            "rule_id": "PH_001",
            "rule_code": "pharmacy_copayment",
            "hospital_type": "약국",
            "age_based_rules": {
                "65세이상": {
                    "prescription_dispensing": [
                        {
                            "range": {"min": 0, "max": 10000},
                            "copayment": {"amount": 1000, "type": "fixed"}
                        },
                        {
                            "range": {"min": 10001, "max": 12000},
                            "copayment": {"rate": 20, "type": "percentage"}
                        },
                        {
                            "range": {"min": 12001, "max": 999999999},
                            "copayment": {"rate": 30, "type": "percentage"}
                        }
                    ]
                },
                "65세미만": {
                    "prescription_dispensing": {
                        "copayment": {"rate": 30, "type": "percentage"}
                    }
                }
            },
            "direct_dispensing": {
                "over_4000": {"rate": 40, "type": "percentage"},
                "under_4000": {
                    "1일분": 1400,
                    "2일분": 1600,
                    "3일분이상": 2000
                }
            }
        }

        # 데이터 삽입
        rules_to_insert = [
            tertiary_hospital_rules,
            general_hospital_rules, 
            clinic_rules,
            pharmacy_rules
        ]
        
        for rule in rules_to_insert:
            self.rules_collection.replace_one(
                {"rule_code": rule["rule_code"]},
                rule,
                upsert=True
            )
        
        print("보험 규칙 데이터 삽입 완료")

    def calculate_copayment(self, patient_info: Dict, medical_cost: int, hospital_type: str, location: str = "동지역") -> Dict:
        """본인부담금 계산"""
        
        # 규칙 조회
        rule = self.rules_collection.find_one({
            "hospital_type": hospital_type
        })
        
        if not rule:
            return {"error": "해당 의료기관 유형의 규칙을 찾을 수 없습니다."}
        
        result = {
            "hospital_type": hospital_type,
            "total_medical_cost": medical_cost,
            "patient_info": patient_info,
            "applied_rule": rule["rule_code"]
        }
        
        # 의원급 단계별 계산
        if hospital_type == "의원" and "tiered_copayment" in rule:
            copayment = self._calculate_tiered_copayment(medical_cost, rule["tiered_copayment"])
            result["copayment_amount"] = copayment
            result["copayment_rate"] = round((copayment / medical_cost) * 100, 2)
        
        # 종합병원 지역별 계산  
        elif hospital_type == "종합병원" and "location_rules" in rule:
            location_rule = rule["location_rules"].get(location, {})
            patient_type = self._determine_patient_type(patient_info)
            
            if patient_type in location_rule:
                rate_info = location_rule[patient_type]
                if isinstance(rate_info, dict) and "일반" in rate_info:
                    rate = rate_info["일반"]["rate"]
                    copayment = int(medical_cost * rate / 100)
                    # 100원 미만 절사
                    copayment = (copayment // 100) * 100
                    result["copayment_amount"] = copayment
                    result["copayment_rate"] = rate
        
        # 약국 연령별 계산
        elif hospital_type == "약국" and "age_based_rules" in rule:
            age_group = "65세이상" if patient_info.get("age", 0) >= 65 else "65세미만"
            age_rule = rule["age_based_rules"][age_group]
            
            if "prescription_dispensing" in age_rule:
                if isinstance(age_rule["prescription_dispensing"], list):
                    copayment = self._calculate_tiered_copayment(medical_cost, age_rule["prescription_dispensing"])
                else:
                    rate = age_rule["prescription_dispensing"]["copayment"]["rate"]
                    copayment = int(medical_cost * rate / 100)
                
                copayment = (copayment // 100) * 100  # 100원 미만 절사
                result["copayment_amount"] = copayment
        
        return result

    def _calculate_tiered_copayment(self, medical_cost: int, tiers: List[Dict]) -> int:
        """단계별 본인부담금 계산"""
        for tier in tiers:
            if tier["range"]["min"] <= medical_cost <= tier["range"]["max"]:
                if tier["copayment"]["type"] == "fixed":
                    return tier["copayment"]["amount"]
                else:  # percentage
                    return int(medical_cost * tier["copayment"]["rate"] / 100)
        return 0

    def _determine_patient_type(self, patient_info: Dict) -> str:
        """환자 유형 결정"""
        if patient_info.get("pregnancy", False):
            return "임신부"
        elif patient_info.get("age", 0) < 1:
            return "1세미만"
        else:
            return "일반환자"

    def search_rules_by_condition(self, hospital_type: str = None, patient_age: int = None) -> List[Dict]:
        """조건별 규칙 검색"""
        query = {}
        
        if hospital_type:
            query["hospital_type"] = hospital_type
        
        rules = list(self.rules_collection.find(query))
        
        # 환자 연령에 따른 필터링
        if patient_age is not None:
            filtered_rules = []
            for rule in rules:
                if self._is_age_applicable(rule, patient_age):
                    filtered_rules.append(rule)
            return filtered_rules
        
        return rules

    def _is_age_applicable(self, rule: Dict, age: int) -> bool:
        """연령 적용 가능성 검사"""
        if "age_group" in rule:
            if rule["age_group"] == "6세이상" and age >= 6:
                return True
            elif rule["age_group"] == "6세미만" and age < 6:
                return True
        return True

    def get_frequently_used_rules(self) -> Dict:
        """자주 사용되는 규칙 요약"""
        pipeline = [
            {
                "$group": {
                    "_id": "$hospital_type",
                    "rule_count": {"$sum": 1},
                    "rules": {"$push": {"rule_code": "$rule_code", "rule_id": "$rule_id"}}
                }
            },
            {"$sort": {"rule_count": -1}}
        ]
        
        return list(self.rules_collection.aggregate(pipeline))

# 사용 예시
def main():
    # 규칙 엔진 초기화
    engine = InsuranceRulesEngine()
    
    # 규칙 데이터 삽입
    engine.insert_copayment_rules()
    
    # 본인부담금 계산 예시
    patient1 = {
        "age": 35,
        "pregnancy": False,
        "chronic_disease": None
    }
    
    patient2 = {
        "age": 70,
        "pregnancy": False,
        "chronic_disease": "고혈압"
    }
    
    # 의원 진료비 계산
    result1 = engine.calculate_copayment(patient1, 30000, "의원")
    print("의원 진료 - 35세 환자:", json.dumps(result1, indent=2, ensure_ascii=False))
    
    # 종합병원 진료비 계산  
    result2 = engine.calculate_copayment(patient1, 50000, "종합병원", "동지역")
    print("종합병원 진료 - 35세 환자:", json.dumps(result2, indent=2, ensure_ascii=False))
    
    # 약국 조제비 계산
    result3 = engine.calculate_copayment(patient2, 15000, "약국")
    print("약국 조제 - 70세 환자:", json.dumps(result3, indent=2, ensure_ascii=False))
    
    # 규칙 검색
    clinic_rules = engine.search_rules_by_condition(hospital_type="의원")
    print("의원 관련 규칙 수:", len(clinic_rules))
    
    # 자주 사용되는 규칙
    frequent_rules = engine.get_frequently_used_rules()
    print("의료기관별 규칙 현황:", json.dumps(frequent_rules, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()