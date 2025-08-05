import os
import time
import json
import csv
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright

# 설정
BASE_URL = "https://www.koicd.kr/ins/act.do"
BASE_DIR = os.path.abspath("koicd_scraping_results")
JSON_DIR = os.path.join(BASE_DIR, "json_pages")
CSV_FILE = os.path.join(BASE_DIR, "koicd_complete_data.csv")
FAILED_FILE = os.path.join(BASE_DIR, "failed_items.txt")
LOG_FILE = os.path.join(BASE_DIR, "scraping.log")

# 폴더 생성
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KOICDScraper:
    def __init__(self):
        self.all_data = []
        self.failed_items = []
        self.current_page = 1
        self.total_processed = 0
        self.browser = None
        self.page = None

    async def initialize_browser(self):
        """브라우저 초기화"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=100  # 디버깅용 느린 실행
        )
        self.page = await self.browser.new_page()
        
        # 뷰포트 설정
        await self.page.set_viewport_size({"width": 1920, "height": 1080})
        
        # 타임아웃 설정
        self.page.set_default_timeout(30000)
        
        # 페이지 이동
        logger.info(f"페이지 접근: {BASE_URL}")
        await self.page.goto(BASE_URL)
        await self.wait_for_page_load()

    async def wait_for_page_load(self):
        """페이지 로딩 완료 대기"""
        try:
            # 네트워크 idle 대기
            await self.page.wait_for_load_state('networkidle')
            
            # 데이터 테이블 로딩 대기
            await self.page.wait_for_selector('table.act_table tbody tr', timeout=15000)
            
            # 실제 데이터 로딩 확인
            for attempt in range(10):
                rows = await self.page.query_selector_all('table.act_table tbody tr')
                if rows and len(rows) > 0:
                    first_row_text = await rows[0].text_content()
                    if first_row_text.strip() and '로딩' not in first_row_text and '처리중' not in first_row_text:
                        logger.info(f"데이터 로딩 완료: {len(rows)}개 행 발견")
                        return True
                
                logger.info(f"데이터 로딩 대기 중... (시도 {attempt + 1}/10)")
                await asyncio.sleep(2)
            
            logger.warning("데이터 로딩 완료를 확인할 수 없음")
            return False
            
        except Exception as e:
            logger.error(f"페이지 로딩 대기 중 오류: {e}")
            return False

    async def extract_row_basic_info(self, row):
        """행의 기본 정보 추출 (TD 내용)"""
        try:
            tds = await row.query_selector_all("td")
            if len(tds) < 3:
                return None
            
            # TD[1]: 수가코드, TD[2]: 행위명
            code = (await tds[1].text_content()).strip()
            name = (await tds[2].text_content()).strip()
            
            if not code or not name:
                return None
            
            return {
                "수가코드": code,
                "행위명_기본": name
            }
            
        except Exception as e:
            logger.error(f"기본 정보 추출 오류: {e}")
            return None

    async def extract_popup_details(self, row):
        """팝업에서 상세 정보 추출"""
        detail_data = {}
        
        try:
            # TD 클릭 (여러 TD 시도)
            tds = await row.query_selector_all("td")
            clicked = False
            
            for i in range(min(3, len(tds))):  # 처음 3개 TD 시도
                try:
                    await tds[i].click()
                    clicked = True
                    break
                except:
                    continue
            
            if not clicked:
                logger.warning("TD 클릭 실패")
                return detail_data
            
            # 팝업 로딩 대기
            await asyncio.sleep(1)
            
            # 팝업 대기 (여러 셀렉터 시도)
            popup_selectors = [
                ".div_table_style",
                ".popup",
                ".modal",
                "div[style*='display: block']",
                "table[class*='popup']"
            ]
            
            popup = None
            for selector in popup_selectors:
                try:
                    popup = await self.page.wait_for_selector(selector, timeout=5000)
                    if popup and await popup.is_visible():
                        logger.debug(f"팝업 발견: {selector}")
                        break
                except:
                    continue
            
            if not popup:
                logger.warning("팝업을 찾을 수 없음")
                return detail_data
            
            # 팝업 내용 추출
            detail_data = await self.extract_popup_content(popup)
            
            # 팝업 닫기
            await self.close_popup(popup)
            
            return detail_data
            
        except Exception as e:
            logger.error(f"팝업 상세 정보 추출 오류: {e}")
            # 팝업이 열려있을 경우 닫기 시도
            await self.close_popup()
            return detail_data

    async def extract_popup_content(self, popup_element):
        """팝업 내용에서 데이터 추출"""
        detail_data = {}
        
        try:
            # 테이블 내용 추출
            tables = await popup_element.query_selector_all("table")
            
            for table in tables:
                rows = await table.query_selector_all("tr")
                
                for row in rows:
                    # TH-TD 쌍 찾기
                    ths = await row.query_selector_all("th")
                    tds = await row.query_selector_all("td")
                    
                    # 단일 TH-TD 구조
                    if len(ths) == 1 and len(tds) >= 1:
                        th_text = (await ths[0].text_content()).strip()
                        
                        if len(tds) == 1:  # colspan인 경우
                            td_text = (await tds[0].text_content()).strip()
                            detail_data[th_text] = td_text
                        elif len(tds) >= 3:  # 일반적인 경우
                            td_text = (await tds[0].text_content()).strip()
                            detail_data[th_text] = td_text
                    
                    # 2개 TH-TD 쌍 구조
                    elif len(ths) == 2 and len(tds) >= 2:
                        th1_text = (await ths[0].text_content()).strip()
                        td1_text = (await tds[0].text_content()).strip()
                        th2_text = (await ths[1].text_content()).strip()
                        td2_text = (await tds[1].text_content()).strip()
                        
                        detail_data[th1_text] = td1_text
                        detail_data[th2_text] = td2_text
                    
                    # 3개 이상의 TH-TD 쌍
                    elif len(ths) >= 3 and len(tds) >= 3:
                        for i in range(min(len(ths), len(tds))):
                            th_text = (await ths[i].text_content()).strip()
                            td_text = (await tds[i].text_content()).strip()
                            if th_text and td_text:
                                detail_data[th_text] = td_text
            
            # 텍스트 정리
            cleaned_data = {}
            for key, value in detail_data.items():
                if key and value and key != value:  # 의미있는 데이터만
                    cleaned_key = key.replace('\n', ' ').strip()
                    cleaned_value = value.replace('\n', ' ').strip()
                    cleaned_data[cleaned_key] = cleaned_value
            
            logger.debug(f"팝업에서 {len(cleaned_data)}개 필드 추출")
            return cleaned_data
            
        except Exception as e:
            logger.error(f"팝업 내용 추출 오류: {e}")
            return detail_data

    async def close_popup(self, popup_element=None):
        """팝업 닫기"""
        try:
            # 닫기 버튼 찾기
            close_selectors = [
                "button:has-text('닫기')",
                "button:has-text('Close')",
                "button:has-text('×')",
                ".close",
                ".popup-close",
                "button[onclick*='close']"
            ]
            
            for selector in close_selectors:
                try:
                    close_btn = await self.page.query_selector(selector)
                    if close_btn and await close_btn.is_visible():
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                        logger.debug(f"팝업 닫기 성공: {selector}")
                        return True
                except:
                    continue
            
            # ESC 키로 닫기 시도
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
            
            logger.debug("ESC로 팝업 닫기 시도")
            return True
            
        except Exception as e:
            logger.error(f"팝업 닫기 오류: {e}")
            return False

    async def check_toggle_button(self, row):
        """행에 토글 버튼(+)이 있는지 확인"""
        try:
            tds = await row.query_selector_all("td")
            if len(tds) > 0:
                first_td = tds[0]
                td_text = (await first_td.text_content()).strip()
                
                # '+' 텍스트가 있는지 확인
                if '+' in td_text:
                    return True, first_td
                
                # 버튼 요소나 클릭 가능한 요소 확인
                button_elements = await first_td.query_selector_all("button, span, a, div")
                for element in button_elements:
                    element_text = (await element.text_content()).strip()
                    if '+' in element_text or 'expand' in element_text.lower():
                        return True, element
                
                # cursor:pointer 스타일 확인
                cursor_style = await first_td.evaluate('el => window.getComputedStyle(el).cursor')
                if cursor_style == 'pointer':
                    return True, first_td
            
            return False, None
            
        except Exception as e:
            logger.debug(f"토글 버튼 확인 오류: {e}")
            return False, None

    async def expand_child_rows(self, toggle_element):
        """하위 행들을 펼치기 위해 토글 버튼 클릭"""
        try:
            logger.debug("토글 버튼 클릭 시도")
            await toggle_element.click()
            await asyncio.sleep(1)  # 펼치기 애니메이션 대기
            
            # 하위 행들이 나타날 때까지 대기
            for attempt in range(5):
                current_rows = await self.page.query_selector_all('table.act_table tbody tr')
                await asyncio.sleep(0.5)
                new_rows = await self.page.query_selector_all('table.act_table tbody tr')
                
                if len(new_rows) > len(current_rows):
                    logger.debug(f"하위 행 펼치기 완료: {len(new_rows) - len(current_rows)}개 행 추가")
                    return True
            
            logger.debug("하위 행 펼치기 완료")
            return True
            
        except Exception as e:
            logger.error(f"하위 행 펼치기 오류: {e}")
            return False

    async def identify_child_rows(self, parent_row, parent_class):
        """펼쳐진 하위 행들 식별"""
        try:
            # 현재 모든 행 가져오기
            all_rows = await self.page.query_selector_all('table.act_table tbody tr')
            
            # 부모 행의 인덱스 찾기
            parent_index = -1
            for i, row in enumerate(all_rows):
                row_class = await row.get_attribute("class")
                if row_class == parent_class:
                    parent_index = i
                    break
            
            if parent_index == -1:
                return []
            
            # 부모 행 다음부터 하위 행들 찾기
            child_rows = []
            for i in range(parent_index + 1, len(all_rows)):
                row = all_rows[i]
                row_class = await row.get_attribute("class")
                
                # 하위 행 판별 로직
                # 1. 클래스가 숫자가 아닌 경우 (하위 행)
                # 2. 들여쓰기가 있는 경우
                # 3. 다음 메인 행이 나올때까지
                
                if row_class and any(c.isdigit() for c in row_class):
                    # 다음 메인 행을 만나면 중단
                    break
                
                # 하위 행으로 판단되는 조건들
                is_child = False
                
                # 클래스명 패턴으로 판별
                if (not row_class or 
                    'child' in row_class.lower() or 
                    'sub' in row_class.lower() or
                    'detail' in row_class.lower()):
                    is_child = True
                
                # 내용이 있는 행인지 확인
                tds = await row.query_selector_all("td")
                if len(tds) >= 2:
                    # TD[1]에 코드가 있는지 확인
                    code_text = (await tds[1].text_content()).strip()
                    if code_text and len(code_text) > 2:
                        is_child = True
                
                if is_child:
                    child_rows.append(row)
                else:
                    # 빈 행이나 의미없는 행은 건너뛰기
                    row_content = await row.text_content()
                    if not row_content.strip():
                        continue
                    else:
                        # 내용이 있는데 하위 행이 아니면 중단
                        break
            
            logger.debug(f"식별된 하위 행 개수: {len(child_rows)}")
            return child_rows
            
        except Exception as e:
            logger.error(f"하위 행 식별 오류: {e}")
            return []

    async def collapse_child_rows(self, toggle_element):
        """하위 행들 다시 접기"""
        try:
            logger.debug("하위 행 접기 시도")
            await toggle_element.click()
            await asyncio.sleep(0.5)  # 접기 애니메이션 대기
            return True
            
        except Exception as e:
            logger.error(f"하위 행 접기 오류: {e}")
            return False

    async def process_single_row(self, row, parent_code=None, hierarchy_level=0):
        """단일 행 처리 (메인 행 또는 하위 행)"""
        try:
            # 기본 정보 추출
            basic_info = await self.extract_row_basic_info(row)
            if not basic_info:
                return None
            
            current_code = basic_info['수가코드']
            logger.info(f"{'  ' * hierarchy_level}{'└─' if hierarchy_level > 0 else ''}수가코드: {current_code}")
            
            # 상세 정보 추출
            detail_info = await self.extract_popup_details(row)
            
            # 계층 정보 추가
            hierarchical_data = {
                **basic_info,
                **detail_info,
                "parent_code": parent_code or current_code,
                "child_code": current_code,
                "hierarchy_level": hierarchy_level,
                "is_parent": hierarchy_level == 0,  # 최상위 행만 부모로 표시
                "페이지": self.current_page,
                "수집일시": datetime.now().isoformat()
            }
            
            self.total_processed += 1
            logger.info(f"{'  ' * hierarchy_level}✅ {current_code} 처리 완료 (레벨 {hierarchy_level})")
            
            return hierarchical_data
            
        except Exception as e:
            logger.error(f"행 처리 오류: {e}")
            return None

    async def process_current_page(self):
        """현재 페이지의 모든 데이터 처리 (계층구조 포함)"""
        logger.info(f"페이지 {self.current_page} 처리 시작")
        
        page_data = []
        
        try:
            # 초기 데이터 행 가져오기 (메인 행들만)
            main_rows = await self.page.query_selector_all('table.act_table tbody tr')
            main_rows = [row for row in main_rows if await self.is_main_row(row)]
            
            logger.info(f"페이지 {self.current_page}: {len(main_rows)}개 메인 행 발견")
            
            for i, main_row in enumerate(main_rows):
                try:
                    row_class = await main_row.get_attribute("class")
                    logger.info(f"행 {i+1}/{len(main_rows)} 처리 중 (class: {row_class})")
                    
                    # 1. 메인 행 처리
                    main_data = await self.process_single_row(main_row, hierarchy_level=0)
                    if not main_data:
                        logger.warning(f"행 {i+1}: 메인 행 처리 실패")
                        continue
                    
                    page_data.append(main_data)
                    parent_code = main_data['수가코드']
                    
                    # 2. 토글 버튼 확인 및 하위 행 처리
                    has_toggle, toggle_element = await self.check_toggle_button(main_row)
                    
                    if has_toggle:
                        logger.info(f"  {parent_code}: 하위 항목 발견, 펼치기 시도")
                        
                        # 하위 행 펼치기
                        if await self.expand_child_rows(toggle_element):
                            # 하위 행들 식별
                            child_rows = await self.identify_child_rows(main_row, row_class)
                            
                            if child_rows:
                                logger.info(f"  {parent_code}: {len(child_rows)}개 하위 행 처리 시작")
                                
                                # 각 하위 행 처리
                                for j, child_row in enumerate(child_rows):
                                    child_data = await self.process_single_row(
                                        child_row, 
                                        parent_code=parent_code, 
                                        hierarchy_level=1
                                    )
                                    
                                    if child_data:
                                        # 부모 정보 업데이트
                                        main_data['is_parent'] = True
                                        page_data.append(child_data)
                                        
                                        # 하위 행 간 대기
                                        await asyncio.sleep(0.3)
                                
                                logger.info(f"  {parent_code}: 하위 행 처리 완료")
                            
                            # 하위 행 다시 접기 (선택사항)
                            await self.collapse_child_rows(toggle_element)
                            await asyncio.sleep(0.5)
                    else:
                        logger.debug(f"  {parent_code}: 하위 항목 없음")
                    
                    # 메인 행 간 대기
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"행 {i+1} 처리 실패: {e}")
                    if 'main_data' in locals() and main_data and main_data.get('수가코드'):
                        self.failed_items.append({
                            'code': main_data['수가코드'],
                            'page': self.current_page,
                            'error': str(e),
                            'timestamp': datetime.now().isoformat()
                        })
                    continue
            
            # 페이지별 JSON 저장
            if page_data:
                json_path = os.path.join(JSON_DIR, f"page_{self.current_page}_hierarchical.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(page_data, f, ensure_ascii=False, indent=2)
                
                self.all_data.extend(page_data)
                
                # 통계 출력
                main_count = len([d for d in page_data if d['hierarchy_level'] == 0])
                child_count = len([d for d in page_data if d['hierarchy_level'] == 1])
                
                logger.info(f"페이지 {self.current_page} 완료: 메인 {main_count}개, 하위 {child_count}개 (총 {len(page_data)}개)")
                
                # 중간 저장
                self.save_to_csv()
            
            return len(page_data) > 0
            
        except Exception as e:
            logger.error(f"페이지 {self.current_page} 처리 중 오류: {e}")
            return False

    async def is_main_row(self, row):
        """메인 행인지 확인 (숫자 클래스를 가진 행)"""
        try:
            row_class = await row.get_attribute("class")
            return row_class and any(c.isdigit() for c in row_class)
        except:
            return False

    async def navigate_to_next_page(self):
        """다음 페이지로 이동"""
        try:
            next_page_num = self.current_page + 1
            
            # 다음 페이지 링크 찾기
            next_selectors = [
                f"a:has-text('{next_page_num}')",
                f".pagination a:has-text('{next_page_num}')",
                f"a[href*='page={next_page_num}']",
                "a:has-text('다음')",
                "a:has-text('>')",
                ".next:not(.disabled)"
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = await self.page.query_selector(selector)
                    if next_btn and await next_btn.is_visible():
                        logger.info(f"다음 페이지 버튼 클릭: {selector}")
                        await next_btn.scroll_into_view_if_needed()
                        await next_btn.click()
                        
                        # 페이지 로딩 대기
                        await self.wait_for_page_load()
                        self.current_page += 1
                        
                        logger.info(f"페이지 {self.current_page}로 이동 완료")
                        return True
                        
                except Exception as e:
                    logger.debug(f"셀렉터 {selector} 시도 실패: {e}")
                    continue
            
            logger.info("다음 페이지 버튼을 찾을 수 없음 - 마지막 페이지로 판단")
            return False
            
        except Exception as e:
            logger.error(f"페이지 이동 오류: {e}")
            return False

    def save_to_csv(self):
        """CSV 파일로 저장 (계층구조 정보 포함)"""
        if not self.all_data:
            return
        
        try:
            # 모든 키 수집
            all_keys = set()
            for item in self.all_data:
                all_keys.update(item.keys())
            
            # 계층구조 우선 컬럼 추가
            priority_cols = [
                "parent_code", "child_code", "hierarchy_level", "is_parent",
                "수가코드", "행위명_기본", "분류코드", "분류단계", 
                "행위명(한글)", "행위명(영문)", "산정명",
                "수술여부", "상대가치점수", "본인부담률", "급여여부",
                "페이지", "수집일시"
            ]
            
            ordered_cols = []
            for col in priority_cols:
                if col in all_keys:
                    ordered_cols.append(col)
                    all_keys.remove(col)
            
            ordered_cols.extend(sorted(all_keys))
            
            # CSV 쓰기
            with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=ordered_cols)
                writer.writeheader()
                
                for item in self.all_data:
                    row_data = {col: item.get(col, "") for col in ordered_cols}
                    writer.writerow(row_data)
            
            # 통계 정보 출력
            main_items = len([d for d in self.all_data if d.get('hierarchy_level') == 0])
            child_items = len([d for d in self.all_data if d.get('hierarchy_level') == 1])
            
            logger.info(f"CSV 저장 완료: 총 {len(self.all_data)}개 항목 (메인 {main_items}개, 하위 {child_items}개)")
            
        except Exception as e:
            logger.error(f"CSV 저장 오류: {e}")

    def save_failed_items(self):
        """실패한 항목 저장"""
        if not self.failed_items:
            return
        
        try:
            with open(FAILED_FILE, "w", encoding="utf-8") as f:
                json.dump(self.failed_items, f, ensure_ascii=False, indent=2)
            
            logger.info(f"실패 항목 저장: {len(self.failed_items)}개")
            
        except Exception as e:
            logger.error(f"실패 항목 저장 오류: {e}")

    async def run(self):
        """메인 스크래핑 실행"""
        start_time = datetime.now()
        logger.info("KOICD 스크래핑 시작")
        
        try:
            await self.initialize_browser()
            
            # 모든 페이지 처리
            while True:
                success = await self.process_current_page()
                
                if not success:
                    logger.warning(f"페이지 {self.current_page} 처리 실패")
                    break
                
                # 다음 페이지로 이동
                if not await self.navigate_to_next_page():
                    logger.info("모든 페이지 처리 완료")
                    break
                
                # 페이지 간 대기
                await asyncio.sleep(2)
            
            # 최종 저장
            self.save_to_csv()
            self.save_failed_items()
            
            # 결과 요약
            end_time = datetime.now()
            duration = end_time - start_time
            
            # 계층구조 통계
            main_items = len([d for d in self.all_data if d.get('hierarchy_level') == 0])
            child_items = len([d for d in self.all_data if d.get('hierarchy_level') == 1])
            parent_items = len([d for d in self.all_data if d.get('is_parent') == True])
            
            logger.info("=" * 60)
            logger.info("🎉 계층구조 스크래핑 완료!")
            logger.info(f"⏱️  처리 시간: {duration}")
            logger.info(f"📄 총 페이지: {self.current_page}")
            logger.info(f"📊 수집 통계:")
            logger.info(f"   └─ 전체 항목: {len(self.all_data)}개")
            logger.info(f"   └─ 메인 항목: {main_items}개")
            logger.info(f"   └─ 하위 항목: {child_items}개")
            logger.info(f"   └─ 부모 항목: {parent_items}개 (하위 데이터 보유)")
            logger.info(f"❌ 실패한 항목: {len(self.failed_items)}개")
            if len(self.all_data) + len(self.failed_items) > 0:
                success_rate = len(self.all_data)/(len(self.all_data)+len(self.failed_items))*100
                logger.info(f"✅ 성공률: {success_rate:.1f}%")
            logger.info(f"💾 저장 위치: {CSV_FILE}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"스크래핑 중 치명적 오류: {e}")
            
        finally:
            if self.browser:
                await self.browser.close()

async def main():
    """메인 함수"""
    scraper = KOICDScraper()
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())