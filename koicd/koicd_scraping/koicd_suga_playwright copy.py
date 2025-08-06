import os
import time
import json
import csv
import asyncio
from playwright.async_api import async_playwright

# 경로 설정
BASE_URL = "https://www.koicd.kr/ins/act.do"
BASE_DIR = os.path.abspath("suga_results")
JSON_DIR = os.path.join(BASE_DIR, "json_pages")
FAILED_FILE = os.path.join(BASE_DIR, "failed_codes.txt")
CSV_FILE = os.path.join(BASE_DIR, "suga_info_detailed.csv")

# 폴더 생성
os.makedirs(JSON_DIR, exist_ok=True)

async def extract_detail_info(page, row_selector):
    """상세 정보 팝업에서 데이터 추출"""
    try:
        # 3번째 td 클릭
        td_element = await page.query_selector(f"{row_selector} td:nth-child(3)")
        if td_element:
            await td_element.click()
            await page.wait_for_timeout(1000)  # 팝업 로딩 대기
            
            # 상세 정보 div가 나타날 때까지 대기
            detail_div = await page.wait_for_selector(".div_table_style", timeout=5000)
            
            if detail_div:
                # 상세 정보 테이블에서 데이터 추출
                detail_data = {}
                
                # 각 행에서 데이터 추출
                rows = await detail_div.query_selector_all("table tbody tr")
                
                for row in rows:
                    ths = await row.query_selector_all("th")
                    tds = await row.query_selector_all("td")
                    
                    if len(ths) == 1 and len(tds) >= 1:  # 단일 th-td 구조
                        th_text = (await ths[0].text_content()).strip()
                        
                        if len(tds) == 1:  # colspan=3인 경우
                            td_text = (await tds[0].text_content()).strip()
                            detail_data[th_text] = td_text
                        elif len(tds) == 3:  # 일반적인 경우
                            td_text = (await tds[0].text_content()).strip()
                            detail_data[th_text] = td_text
                    
                    elif len(ths) == 2 and len(tds) == 2:  # 2개 th-td 쌍
                        th1_text = (await ths[0].text_content()).strip()
                        td1_text = (await tds[0].text_content()).strip()
                        th2_text = (await ths[1].text_content()).strip()
                        td2_text = (await tds[1].text_content()).strip()
                        
                        detail_data[th1_text] = td1_text
                        detail_data[th2_text] = td2_text
                
                # 팝업 닫기 버튼 클릭
                close_btn = await detail_div.query_selector("button:has-text('닫기')")
                if close_btn:
                    await close_btn.click()
                    await page.wait_for_timeout(500)
                
                return detail_data
            
    except Exception as e:
        print(f"❌ 상세 정보 추출 실패: {e}")
        # 팝업이 열려있을 수 있으니 닫기 시도
        try:
            close_btn = await page.query_selector(".div_table_style button:has-text('닫기')")
            if close_btn:
                await close_btn.click()
                await page.wait_for_timeout(500)
        except:
            pass
        
        return {}

async def scrape_koicd():
    async with async_playwright() as p:
        # 브라우저 시작
        browser = await p.chromium.launch(headless=False)  # 디버깅용으로 headless=False
        page = await browser.new_page()
        
        # 뷰포트 크기 설정 (팝업이 잘 보이도록)
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # 네트워크 타임아웃 설정
        page.set_default_timeout(30000)
        
        all_data = []
        failed_codes = []
        page_num = 1
        
        await page.goto(BASE_URL)
        await page.wait_for_load_state('networkidle')
        
        while True:
            print(f"\n▶ 페이지 {page_num} 처리 중...")
            
            try:
                # 테이블 로딩 대기
                await page.wait_for_selector("#container table tbody tr", timeout=10000)
                
                # 현재 페이지의 모든 데이터 행 가져오기
                rows = await page.query_selector_all("#container table tbody tr")
                print(f"📋 현재 페이지 행 수: {len(rows)}")
                
                page_data = []
                
                for i, row in enumerate(rows):
                    try:
                        # 클래스가 숫자인 행만 처리 (데이터 행)
                        row_class = await row.get_attribute("class")
                        if not row_class or not any(c.isdigit() for c in row_class):
                            continue
                        
                        print(f"  🔍 행 {i+1} 처리 중... (class: {row_class})")
                        
                        # 🔍 디버깅: TD 구조 확인
                        tds = await row.query_selector_all("td")
                        print(f"    📊 TD 개수: {len(tds)}")
                        
                        # 각 TD 내용 출력 (처음 5개만)
                        for j, td in enumerate(tds[:5]):
                            td_text = (await td.text_content()).strip()
                            print(f"    TD[{j}]: '{td_text}'")
                        
                        if len(tds) < 3:
                            print(f"    ⚠️ TD가 3개 미만임. 건너뜀.")
                            continue
                        
                        # 🔍 수가코드 위치 확인 (여러 위치 시도)
                        suga_code = ""
                        for idx in range(min(3, len(tds))):
                            potential_code = (await tds[idx].text_content()).strip()
                            if potential_code and len(potential_code) > 2:  # 의미있는 코드인지 확인
                                suga_code = potential_code
                                print(f"    🎯 수가코드 발견 TD[{idx}]: '{suga_code}'")
                                break
                        
                        if not suga_code:
                            print(f"    ❌ 수가코드를 찾을 수 없음")
                            continue
                        
                        kor_name = (await tds[1].text_content()).strip() if len(tds) > 1 else ""
                        eng_name = (await tds[2].text_content()).strip() if len(tds) > 2 else ""
                        
                        # 행의 고유 selector 생성
                        row_selector = f"#container table tbody tr.\\{row_class.replace(' ', '.')}"
                        
                        # 상세 정보 추출
                        print(f"    📝 {suga_code} 상세 정보 추출 중...")
                        detail_info = await extract_detail_info(page, row_selector)
                        
                        # 데이터 통합
                        combined_data = {
                            "수가코드": suga_code,
                            "행위명(한글)_기본": kor_name,
                            "행위명(영문)_기본": eng_name,
                            **detail_info  # 상세 정보 추가
                        }
                        
                        page_data.append(combined_data)
                        print(f"    ✅ {suga_code} 완료")
                        
                        # 요청 간 딜레이
                        await page.wait_for_timeout(500)
                        
                    except Exception as e:
                        print(f"    ❌ 행 {i+1} 처리 실패: {e}")
                        if 'suga_code' in locals():
                            failed_codes.append(suga_code)
                        continue
                
                # 페이지별 JSON 저장
                json_path = os.path.join(JSON_DIR, f"page_{page_num}_detailed.json")
                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump(page_data, jf, ensure_ascii=False, indent=2)
                
                all_data.extend(page_data)
                print(f"📄 페이지 {page_num} 완료: {len(page_data)}개 항목")
                
                # 중간 CSV 저장
                save_to_csv(all_data)
                
                # 다음 페이지로 이동
                try:
                    # 페이지네이션에서 다음 페이지 번호 찾기
                    next_page_num = page_num + 1
                    
                    # 다음 페이지 링크 찾기 (여러 패턴 시도)
                    next_selectors = [
                        f"a:has-text('{next_page_num}')",
                        f".pagination a:has-text('{next_page_num}')",
                        f"a[href*='page={next_page_num}']",
                        "a:has-text('다음')",
                        "a:has-text('>')",
                        ".next"
                    ]
                    
                    next_btn = None
                    for selector in next_selectors:
                        try:
                            next_btn = await page.query_selector(selector)
                            if next_btn:
                                print(f"🔗 다음 페이지 버튼 발견: {selector}")
                                break
                        except:
                            continue
                    
                    if next_btn:
                        await next_btn.scroll_into_view_if_needed()
                        await next_btn.click()
                        await page.wait_for_load_state('networkidle')
                        page_num += 1
                        
                        # 페이지 변경 확인을 위한 짧은 대기
                        await page.wait_for_timeout(2000)
                    else:
                        print(f"⛔ 다음 페이지 버튼을 찾을 수 없음. 마지막 페이지로 판단.")
                        break
                        
                except Exception as e:
                    print(f"⛔ 페이지 이동 실패: {e}")
                    break
                
            except Exception as e:
                print(f"❌ 페이지 {page_num} 처리 실패: {e}")
                break
        
        await browser.close()
        
        # 실패 로그 저장
        with open(FAILED_FILE, "w", encoding="utf-8") as ff:
            for code in failed_codes:
                ff.write(code + "\n")
        
        print(f"\n📦 전체 데이터 수집 완료!")
        print(f"✅ 총 {len(all_data)}개 항목 수집")
        print(f"❌ 실패한 항목: {len(failed_codes)}개")
        
        return all_data, failed_codes

def save_to_csv(data):
    """CSV 파일로 저장"""
    if not data:
        return
    
    try:
        # 모든 키를 수집하여 컬럼 헤더 생성
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        
        # 컬럼 순서 정렬 (기본 정보를 앞으로)
        priority_cols = ["수가코드", "행위명(한글)_기본", "행위명(영문)_기본", "분류코드", "분류단계"]
        ordered_cols = []
        
        for col in priority_cols:
            if col in all_keys:
                ordered_cols.append(col)
                all_keys.remove(col)
        
        ordered_cols.extend(sorted(all_keys))
        
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as cf:
            writer = csv.DictWriter(cf, fieldnames=ordered_cols)
            writer.writeheader()
            
            for item in data:
                # 빈 값들을 ""로 채우기
                row_data = {col: item.get(col, "") for col in ordered_cols}
                writer.writerow(row_data)
        
        print(f"💾 CSV 저장 완료: {CSV_FILE} ({len(data)}개 항목)")
        
    except Exception as e:
        print(f"❌ CSV 저장 실패: {e}")

# 실행
if __name__ == "__main__":
    all_data, failed_codes = asyncio.run(scrape_koicd())
    
    print(f"\n🎯 최종 결과:")
    print(f"   📊 수집된 총 항목: {len(all_data)}개")
    print(f"   ❌ 실패한 항목: {len(failed_codes)}개")
    print(f"   📁 저장 위치: {CSV_FILE}")