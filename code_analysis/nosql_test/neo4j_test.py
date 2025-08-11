"""
Neo4j 기반 보험심사 규칙 실험적 구현
그래프 DB로 복잡한 보험 규칙 관계 모델링
"""

from neo4j import GraphDatabase
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

class Neo4jInsuranceRules:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="insurance2025"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def clear_database(self):
        """실험용: 기존 데이터 삭제"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("데이터베이스 초기화 완료")
    
    def create_basic_schema(self):
        """기본 스키마 및 제약조건 생성"""
        with self.driver.session() as session:
            # 인덱스 생성
            session.run("CREATE INDEX hospital_type_idx IF NOT EXISTS FOR (h:HospitalType) ON (h.name)")
            session.run("CREATE INDEX patient_type_idx IF NOT EXISTS FOR (p:PatientType) ON (p.name)")
            session.run("CREATE INDEX rule_code_idx IF NOT EXISTS FOR (r:Rule) ON (r.code)")
            
            print("스키마 생성 완료")
    
    def insert_experimental_data(self):
        """실험용 데이터 삽입 - 간단한 구조부터 시작"""
        
        with self.driver.session() as session:
            # 1. 의료기관 유형 노드 생성
            hospital_types = [
                {"name": "상급종합병원", "level": 4, "description": "최고급 의료기관"},
                {"name": "종합병원", "level": 3, "description": "종합의료서비스"},
                {"name": "병원", "level": 2, "description": "일반병원"},
                {"name": "의원", "level": 1, "description": "1차 의료기관"},
                {"name": "약국", "level": 1, "description": "조제기관"}
            ]
            
            for hospital in hospital_types:
                session.run("""
                    CREATE (h:HospitalType {
                        name: $name,
                        level: $level,
                        description: $description
                    })
                """, **hospital)
            
            # 2. 환자 유형 노드 생성
            patient_types = [
                {"name": "일반환자", "code": "NORMAL"},
                {"name": "임신부", "code": "PREGNANT"}, 
                {"name": "신생아", "code": "NEWBORN"},
                {"name": "6세미만", "code": "CHILD_UNDER_6"},
                {"name": "65세이상", "code": "SENIOR"},
                {"name": "만성질환자", "code": "CHRONIC"}
            ]
            
            for patient in patient_types:
                session.run("""
                    CREATE (p:PatientType {
                        name: $name,
                        code: $code
                    })
                """, **patient)
            
            # 3. 지역 구분 노드
            locations = [
                {"name": "동지역", "type": "URBAN"},
                {"name": "읍면지역", "type": "RURAL"}
            ]
            
            for location in locations:
                session.run("""
                    CREATE (l:Location {
                        name: $name,
                        type: $type
                    })
                """, **location)
            
            # 4. 기본 규칙 노드 생성
            rules = [
                {
                    "code": "TERTIARY_GENERAL", 
                    "name": "상급종합병원_일반환자",
                    "consultation_rate": 100,
                    "medical_rate": 60,
                    "description": "진찰료 100% + 기타 60%"
                },
                {
                    "code": "GENERAL_URBAN_NORMAL",
                    "name": "종합병원_동지역_일반",
                    "consultation_rate": 0,
                    "medical_rate": 50,
                    "description": "50% 정률"
                },
                {
                    "code": "CLINIC_TIER1",
                    "name": "의원_1구간",
                    "min_cost": 0,
                    "max_cost": 15000,
                    "fixed_amount": 1500,
                    "description": "15,000원 이하 정액 1,500원"
                },
                {
                    "code": "CLINIC_TIER2", 
                    "name": "의원_2구간",
                    "min_cost": 15001,
                    "max_cost": 20000,
                    "rate": 10,
                    "description": "15,001~20,000원 10%"
                }
            ]
            
            for rule in rules:
                session.run("""
                    CREATE (r:Rule {
                        code: $code,
                        name: $name,
                        consultation_rate: $consultation_rate,
                        medical_rate: $medical_rate,
                        min_cost: $min_cost,
                        max_cost: $max_cost,
                        fixed_amount: $fixed_amount,
                        rate: $rate,
                        description: $description,
                        created_at: datetime()
                    })
                """, **{k: rule.get(k) for k in rule.keys()})
            
            print("기본 노드 생성 완료")
    
    def create_relationships(self):
        """노드 간 관계 생성 - 여기가 Neo4j의 핵심!"""
        
        with self.driver.session() as session:
            # 1. 의료기관 → 환자유형 → 규칙 관계
            relationships = [
                {
                    "hospital": "상급종합병원",
                    "patient": "일반환자", 
                    "rule": "TERTIARY_GENERAL",
                    "priority": 1
                },
                {
                    "hospital": "종합병원",
                    "patient": "일반환자",
                    "rule": "GENERAL_URBAN_NORMAL", 
                    "priority": 1
                },
                {
                    "hospital": "의원",
                    "patient": "일반환자",
                    "rule": "CLINIC_TIER1",
                    "priority": 1
                }
            ]
            
            for rel in relationships:
                session.run("""
                    MATCH (h:HospitalType {name: $hospital})
                    MATCH (p:PatientType {name: $patient})
                    MATCH (r:Rule {code: $rule})
                    CREATE (h)-[:APPLIES_TO {priority: $priority}]->(p)
                    CREATE (p)-[:USES_RULE {priority: $priority}]->(r)
                """, **rel)
            
            # 2. 지역별 차등 관계
            session.run("""
                MATCH (h:HospitalType {name: "종합병원"})
                MATCH (l:Location {name: "동지역"})
                MATCH (r:Rule {code: "GENERAL_URBAN_NORMAL"})
                CREATE (h)-[:LOCATION_RULE]->(l)-[:HAS_RULE]->(r)
            """)
            
            # 3. 연령별 특례 관계 (6세 미만 70% 적용)
            session.run("""
                MATCH (p:PatientType {name: "6세미만"})
                MATCH (r:Rule)
                CREATE (p)-[:DISCOUNT_RATE {multiplier: 0.7, description: "6세미만 30% 할인"}]->(r)
            """)
            
            # 4. 임신부 특례
            session.run("""
                MATCH (h:HospitalType {name: "상급종합병원"})
                MATCH (p:PatientType {name: "임신부"})
                CREATE (h)-[:SPECIAL_RATE {rate: 40, description: "임신부 40%"}]->(p)
            """)
            
            print("관계 생성 완료")
    
    def find_applicable_rules(self, hospital_type: str, patient_age: int, 
                            pregnancy: bool = False, location: str = "동지역") -> List[Dict]:
        """환자 조건에 맞는 규칙 찾기 - 그래프 탐색의 힘!"""
        
        with self.driver.session() as session:
            # 1. 기본 규칙 조회
            result = session.run("""
                MATCH (h:HospitalType {name: $hospital_type})
                -[:APPLIES_TO]->(p:PatientType)
                -[:USES_RULE]->(r:Rule)
                RETURN h.name as hospital, p.name as patient_type, r
                ORDER BY r.created_at DESC
                LIMIT 5
            """, hospital_type=hospital_type)
            
            rules = []
            for record in result:
                rule_node = record["r"]
                rules.append({
                    "hospital_type": record["hospital"],
                    "patient_type": record["patient_type"],
                    "rule_code": rule_node["code"],
                    "rule_name": rule_node["name"],
                    "description": rule_node["description"],
                    "properties": dict(rule_node)
                })
            
            # 2. 특별 조건 확인 (임신부, 연령별)
            if pregnancy:
                special_result = session.run("""
                    MATCH (h:HospitalType {name: $hospital_type})
                    -[:SPECIAL_RATE]->(p:PatientType {name: "임신부"})
                    RETURN h.name as hospital, p.name as special_type
                """, hospital_type=hospital_type)
                
                for record in special_result:
                    rules.append({
                        "hospital_type": record["hospital"],
                        "patient_type": record["special_type"],
                        "rule_code": "SPECIAL_PREGNANCY",
                        "description": "임신부 특례 적용"
                    })
            
            # 3. 연령별 할인 확인
            if patient_age < 6:
                discount_result = session.run("""
                    MATCH (p:PatientType {name: "6세미만"})
                    -[d:DISCOUNT_RATE]->(r:Rule)
                    RETURN p.name as patient_type, d.multiplier as discount, 
                           d.description as discount_desc
                    LIMIT 1
                """)
                
                for record in discount_result:
                    rules.append({
                        "patient_type": record["patient_type"],
                        "rule_code": "AGE_DISCOUNT",
                        "discount_rate": record["discount"],
                        "description": record["discount_desc"]
                    })
            
            return rules
    
    def calculate_with_graph(self, hospital_type: str, medical_cost: int, 
                           patient_age: int, pregnancy: bool = False) -> Dict:
        """그래프 기반 본인부담금 계산"""
        
        # 1. 적용 가능한 규칙 찾기
        applicable_rules = self.find_applicable_rules(
            hospital_type, patient_age, pregnancy
        )
        
        if not applicable_rules:
            return {"error": "적용 가능한 규칙을 찾을 수 없습니다."}
        
        # 2. 주요 규칙 선택 (우선순위 기반)
        main_rule = applicable_rules[0]
        
        # 3. 계산 로직 (간단한 예시)
        copayment = 0
        calculation_details = []
        
        if hospital_type == "의원":
            # 단계별 계산
            if medical_cost <= 15000:
                copayment = 1500
                calculation_details.append("1구간: 정액 1,500원")
            elif medical_cost <= 20000:
                copayment = int(medical_cost * 0.1)
                calculation_details.append("2구간: 10% 적용")
            else:
                copayment = int(medical_cost * 0.3)
                calculation_details.append("3구간: 30% 적용")
        
        elif hospital_type == "상급종합병원":
            if pregnancy:
                copayment = int(medical_cost * 0.4)
                calculation_details.append("임신부 특례: 40%")
            else:
                # 진찰료 가정 (의료비의 20%)
                consultation_fee = int(medical_cost * 0.2)
                other_fee = medical_cost - consultation_fee
                copayment = consultation_fee + int(other_fee * 0.6)
                calculation_details.append("진찰료 100% + 기타 60%")
        
        # 4. 연령별 할인 적용
        if patient_age < 6:
            original_copayment = copayment
            copayment = int(copayment * 0.7)
            calculation_details.append(f"6세미만 할인: {original_copayment} → {copayment}")
        
        # 5. 100원 미만 절사
        copayment = (copayment // 100) * 100
        
        return {
            "success": True,
            "hospital_type": hospital_type,
            "medical_cost": medical_cost,
            "copayment_amount": copayment,
            "copayment_rate": round((copayment / medical_cost) * 100, 2),
            "applicable_rules": applicable_rules,
            "main_rule": main_rule,
            "calculation_details": calculation_details,
            "patient_conditions": {
                "age": patient_age,
                "pregnancy": pregnancy
            }
        }
    
    def get_rule_relationships(self, rule_code: str) -> Dict:
        """특정 규칙의 관계망 조회"""
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:Rule {code: $rule_code})
                OPTIONAL MATCH (r)<-[:USES_RULE]-(p:PatientType)
                OPTIONAL MATCH (p)<-[:APPLIES_TO]-(h:HospitalType)
                OPTIONAL MATCH (r)<-[:HAS_RULE]-(l:Location)
                RETURN r, 
                       collect(DISTINCT p.name) as patient_types,
                       collect(DISTINCT h.name) as hospital_types,
                       collect(DISTINCT l.name) as locations
            """, rule_code=rule_code)
            
            record = result.single()
            if record:
                rule_node = record["r"]
                return {
                    "rule_code": rule_node["code"],
                    "rule_name": rule_node["name"],
                    "description": rule_node["description"],
                    "patient_types": record["patient_types"],
                    "hospital_types": record["hospital_types"], 
                    "locations": record["locations"],
                    "properties": dict(rule_node)
                }
            return {"error": "규칙을 찾을 수 없습니다."}
    
    def analyze_rule_complexity(self) -> Dict:
        """규칙 복잡도 분석 - 그래프 통계"""
        
        with self.driver.session() as session:
            # 1. 전체 노드 수
            node_count = session.run("""
                MATCH (n) 
                RETURN count(n) as total_nodes
            """).single()["total_nodes"]
            
            # 2. 관계 수
            rel_count = session.run("""
                MATCH ()-[r]->() 
                RETURN count(r) as total_relationships
            """).single()["total_relationships"]
            
            # 3. 의료기관별 규칙 수
            hospital_rules = session.run("""
                MATCH (h:HospitalType)-[:APPLIES_TO]->(p:PatientType)-[:USES_RULE]->(r:Rule)
                RETURN h.name as hospital, count(DISTINCT r) as rule_count
                ORDER BY rule_count DESC
            """)
            
            hospital_stats = [{"hospital": record["hospital"], 
                             "rule_count": record["rule_count"]} 
                            for record in hospital_rules]
            
            # 4. 가장 복잡한 규칙 (관계가 많은 규칙)
            complex_rules = session.run("""
                MATCH (r:Rule)
                OPTIONAL MATCH (r)<-[rel]-()
                RETURN r.code as rule_code, r.name as rule_name, 
                       count(rel) as relationship_count
                ORDER BY relationship_count DESC
                LIMIT 3
            """)
            
            complexity_stats = [{"rule_code": record["rule_code"],
                               "rule_name": record["rule_name"],
                               "relationships": record["relationship_count"]}
                              for record in complex_rules]
            
            return {
                "total_nodes": node_count,
                "total_relationships": rel_count,
                "hospital_rule_stats": hospital_stats,
                "most_complex_rules": complexity_stats,
                "analysis_timestamp": datetime.now().isoformat()
            }

# 실험 실행 함수
def run_neo4j_experiment():
    """Neo4j 실험 실행"""
    
    print("🧪 Neo4j 보험규칙 실험 시작")
    
    # 1. 연결 및 초기화
    neo4j_rules = Neo4jInsuranceRules()
    
    try:
        # 2. 데이터베이스 초기화 (실험용)
        neo4j_rules.clear_database()
        neo4j_rules.create_basic_schema()
        
        # 3. 실험 데이터 삽입
        neo4j_rules.insert_experimental_data()
        neo4j_rules.create_relationships()
        
        # 4. 규칙 조회 실험
        print("\n📋 규칙 조회 실험:")
        rules = neo4j_rules.find_applicable_rules("의원", 35, False)
        print(f"의원 35세 일반환자 적용 규칙: {len(rules)}개")
        for rule in rules:
            print(f"  - {rule['rule_code']}: {rule['description']}")
        
        # 5. 본인부담금 계산 실험
        print("\n💰 본인부담금 계산 실험:")
        test_cases = [
            {"hospital": "의원", "cost": 30000, "age": 35, "pregnancy": False},
            {"hospital": "상급종합병원", "cost": 50000, "age": 28, "pregnancy": True},
            {"hospital": "의원", "cost": 10000, "age": 4, "pregnancy": False}
        ]
        
        for case in test_cases:
            result = neo4j_rules.calculate_with_graph(
                case["hospital"], case["cost"], case["age"], case["pregnancy"]
            )
            
            if result.get("success"):
                print(f"\n{case['hospital']} - {case['cost']:,}원 ({case['age']}세):")
                print(f"  본인부담금: {result['copayment_amount']:,}원 ({result['copayment_rate']:.1f}%)")
                print(f"  적용규칙: {result['main_rule']['rule_code']}")
                print(f"  계산과정: {', '.join(result['calculation_details'])}")
        
        # 6. 규칙 관계 분석
        print("\n🔍 규칙 관계 분석:")
        relationship = neo4j_rules.get_rule_relationships("CLINIC_TIER1")
        if "error" not in relationship:
            print(f"규칙 {relationship['rule_code']}:")
            print(f"  적용 의료기관: {relationship['hospital_types']}")
            print(f"  적용 환자유형: {relationship['patient_types']}")
        
        # 7. 복잡도 분석
        print("\n📊 시스템 복잡도 분석:")
        complexity = neo4j_rules.analyze_rule_complexity()
        print(f"  전체 노드: {complexity['total_nodes']}개")
        print(f"  전체 관계: {complexity['total_relationships']}개")
        print(f"  의료기관별 규칙 수:")
        for stat in complexity['hospital_rule_stats']:
            print(f"    {stat['hospital']}: {stat['rule_count']}개")
        
        print("\n✅ Neo4j 실험 완료! 그래프 DB의 관계 모델링 장점을 확인했습니다.")
        
    except Exception as e:
        print(f"❌ 실험 중 오류 발생: {e}")
    
    finally:
        neo4j_rules.close()

if __name__ == "__main__":
    run_neo4j_experiment()