import asyncio
import json
from playwright.async_api import async_playwright

async def analyze_koicd_page():
    """
    KOICD 페이지 종합 분석:
    1. 모든 테이블 분석 (id, class, 내용)
    2. loading vs 실제 데이터 테이블 구분
    3. 동적 로딩 확인 및 최적 대기 방법
    4. 수가코드 데이터 테이블 정확한 셀렉터
    5. 데이터 행 구조 및 클릭 가능한 td 분석
    6. 네트워크 요청 모니터링
    7. 스크린샷 저장
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 네트워크 요청 모니터링 설정
        network_requests = []
        
        def handle_request(request):
            network_requests.append({
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data
            })
        
        def handle_response(response):
            for req in network_requests:
                if req['url'] == response.url:
                    req['status'] = response.status
                    req['response_headers'] = dict(response.headers)
                    break
        
        page.on('request', handle_request)
        page.on('response', handle_response)
        
        try:
            print("🔍 KOICD 페이지 종합 분석 시작...")
            
            # 네트워크 타임아웃 설정
            page.set_default_timeout(30000)
            
            # 페이지 접근
            print("📡 페이지 로딩 중...")
            await page.goto("https://www.koicd.kr/ins/act.do")
            
            # 1단계: 초기 로딩 완료 대기
            await page.wait_for_load_state('domcontentloaded')
            print("✅ DOM 로딩 완료")
            
            # 초기 상태 스크린샷
            await page.screenshot(path="koicd_initial_state.png", full_page=True)
            print("📸 초기 상태 스크린샷 저장")
            
            # 2단계: 초기 테이블 분석
            print("\n📊 초기 테이블 상태 분석...")
            initial_tables = await analyze_all_tables(page, "초기")
            
            # 3단계: 네트워크 idle 대기
            await page.wait_for_load_state('networkidle')
            print("✅ 네트워크 idle 완료")
            
            # 4단계: 추가 대기 후 재분석
            await page.wait_for_timeout(5000)
            print("\n📊 네트워크 idle 후 테이블 상태 재분석...")
            final_tables = await analyze_all_tables(page, "최종")
            
            # 최종 상태 스크린샷
            await page.screenshot(path="koicd_final_state.png", full_page=True)
            print("📸 최종 상태 스크린샷 저장")
            
            # 5단계: 데이터 테이블 정확한 셀렉터 찾기
            print("\n🎯 수가코드 데이터 테이블 정확한 셀렉터 분석...")
            data_table_info = await find_data_table_selector(page)
            
            # 6단계: 데이터 행 구조 및 클릭 분석
            print("\n📋 데이터 행 구조 및 클릭 가능 요소 분석...")
            row_structure_info = await analyze_row_structure(page)
            
            # 7단계: 네트워크 요청 분석
            print("\n🌐 네트워크 요청 분석...")
            analyze_network_requests(network_requests)
            
            # 8단계: 최적 로딩 전략 제안
            print("\n💡 최적 로딩 대기 전략 제안...")
            suggest_optimal_loading_strategy(initial_tables, final_tables, network_requests)
            
            # 분석 결과를 JSON으로 저장
            analysis_result = {
                'initial_tables': initial_tables,
                'final_tables': final_tables,
                'data_table_info': data_table_info,
                'row_structure_info': row_structure_info,
                'network_requests': network_requests[:10]  # 처음 10개만 저장
            }
            
            with open('koicd_analysis_result.json', 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            print("💾 분석 결과 JSON 저장 완료")
            
        except Exception as e:
            print(f"❌ 분석 실패: {e}")
            try:
                await page.screenshot(path="koicd_error_screenshot.png")
                print("📸 오류 스크린샷 저장")
            except:
                pass
        
        finally:
            await browser.close()

async def analyze_all_tables(page, stage):
    """페이지의 모든 테이블 분석"""
    print(f"   📋 {stage} 단계 - 테이블 분석:")
    
    tables_info = []
    try:
        tables = await page.query_selector_all("table")
        print(f"      총 {len(tables)}개 테이블 발견")
        
        for i, table in enumerate(tables):
            info = {
                'index': i + 1,
                'id': await table.get_attribute('id') or '',
                'class': await table.get_attribute('class') or '',
                'style': await table.get_attribute('style') or '',
                'visible': await table.is_visible()
            }
            
            # 위치 정보
            bbox = await table.bounding_box()
            info['position'] = bbox if bbox else 'hidden'
            
            # 구조 정보
            if info['visible']:
                rows = await table.query_selector_all('tr')
                tbody_rows = await table.query_selector_all('tbody tr')
                headers = await table.query_selector_all('th')
                
                info['structure'] = {
                    'total_rows': len(rows),
                    'tbody_rows': len(tbody_rows),
                    'headers': len(headers)
                }
                
                # 내용 샘플
                if tbody_rows:
                    first_row = await tbody_rows[0].text_content()
                    info['sample_content'] = first_row.strip()[:100]
                elif rows:
                    first_row = await rows[0].text_content()
                    info['sample_content'] = first_row.strip()[:100]
                else:
                    info['sample_content'] = '내용 없음'
            else:
                info['structure'] = '숨겨진 테이블'
                info['sample_content'] = '숨겨진 테이블'
            
            # 부모 컨테이너 정보
            parent = await table.query_selector('xpath=..')
            if parent:
                parent_tag = await parent.evaluate('el => el.tagName')
                parent_id = await parent.get_attribute('id') or ''
                parent_class = await parent.get_attribute('class') or ''
                info['parent'] = f"{parent_tag.lower()}" + (f"#{parent_id}" if parent_id else "") + (f".{parent_class.split()[0]}" if parent_class else "")
            
            tables_info.append(info)
            
            print(f"      테이블 #{i+1}: id='{info['id']}', class='{info['class']}', visible={info['visible']}")
            if info['visible']:
                print(f"                 구조: {info['structure']}, 부모: {info.get('parent', 'N/A')}")
                print(f"                 내용: {info['sample_content']}")
    
    except Exception as e:
        print(f"      ❌ 테이블 분석 오류: {e}")
    
    return tables_info

async def find_data_table_selector(page):
    """수가코드 데이터가 있는 테이블의 정확한 셀렉터 찾기"""
    data_table_info = {}
    
    try:
        # 다양한 셀렉터로 데이터 테이블 찾기
        selectors_to_try = [
            "#container table",
            "table[class*='data']",
            "table[id*='data']",
            ".table-container table",
            "#content table",
            "table tbody tr[class]"
        ]
        
        for selector in selectors_to_try:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"      셀렉터 '{selector}': {len(elements)}개 요소 발견")
                    
                    # 첫 번째 요소의 내용 확인
                    if len(elements) > 0:
                        content = await elements[0].text_content()
                        if '수가' in content or 'suga' in content.lower() or len(content) > 50:
                            data_table_info['best_selector'] = selector
                            data_table_info['element_count'] = len(elements)
                            data_table_info['sample_content'] = content[:200]
                            print(f"      ✅ 데이터 테이블 후보: {selector}")
            
            except Exception:
                continue
        
        # #container table tbody tr 분석 (기존 코드에서 사용하던 셀렉터)
        container_rows = await page.query_selector_all("#container table tbody tr")
        if container_rows:
            data_table_info['container_rows_count'] = len(container_rows)
            print(f"      #container table tbody tr: {len(container_rows)}개 행")
            
            # 첫 번째 행 분석
            if len(container_rows) > 0:
                first_row = container_rows[0]
                row_class = await first_row.get_attribute('class')
                row_content = await first_row.text_content()
                
                data_table_info['first_row'] = {
                    'class': row_class,
                    'content': row_content.strip()[:100]
                }
                print(f"      첫 번째 행 class: '{row_class}', 내용: '{row_content.strip()[:50]}...'")
    
    except Exception as e:
        print(f"      ❌ 데이터 테이블 셀렉터 찾기 오류: {e}")
    
    return data_table_info

async def analyze_row_structure(page):
    """데이터 행의 구조와 클릭 가능한 td 분석"""
    row_info = {}
    
    try:
        rows = await page.query_selector_all("#container table tbody tr")
        if rows:
            print(f"      분석할 행 개수: {len(rows)}")
            
            # 첫 번째 데이터 행 분석
            first_row = rows[0] if rows else None
            if first_row:
                tds = await first_row.query_selector_all("td")
                row_info['td_count'] = len(tds)
                row_info['td_contents'] = []
                row_info['clickable_tds'] = []
                
                print(f"      첫 번째 행의 td 개수: {len(tds)}")
                
                for i, td in enumerate(tds):
                    content = await td.text_content()
                    row_info['td_contents'].append({
                        'index': i,
                        'content': content.strip()[:50],
                        'full_content': content.strip()
                    })
                    
                    # 클릭 가능성 확인
                    cursor_style = await td.evaluate('el => window.getComputedStyle(el).cursor')
                    onclick = await td.get_attribute('onclick')
                    has_link = await td.query_selector('a')
                    
                    if cursor_style == 'pointer' or onclick or has_link:
                        row_info['clickable_tds'].append({
                            'index': i,
                            'reason': 'cursor:pointer' if cursor_style == 'pointer' else 'onclick' if onclick else 'has_link'
                        })
                    
                    print(f"        TD[{i}]: '{content.strip()[:30]}...', 클릭가능: {cursor_style == 'pointer' or bool(onclick) or bool(has_link)}")
                
                # 행 클래스 패턴 분석
                row_classes = []
                for row in rows[:5]:  # 처음 5개 행만 분석
                    row_class = await row.get_attribute('class')
                    if row_class:
                        row_classes.append(row_class)
                
                row_info['row_class_patterns'] = list(set(row_classes))
                print(f"      행 클래스 패턴: {row_info['row_class_patterns']}")
    
    except Exception as e:
        print(f"      ❌ 행 구조 분석 오류: {e}")
    
    return row_info

def analyze_network_requests(requests):
    """네트워크 요청 분석"""
    print(f"      총 {len(requests)}개 네트워크 요청 발생")
    
    ajax_requests = []
    for req in requests:
        if req['method'] in ['POST', 'PUT'] or 'json' in req.get('response_headers', {}).get('content-type', '').lower():
            ajax_requests.append(req)
    
    print(f"      AJAX/API 요청: {len(ajax_requests)}개")
    
    for i, req in enumerate(ajax_requests[:5]):  # 처음 5개만 출력
        print(f"        {i+1}. {req['method']} {req['url']}")
        if req.get('post_data'):
            print(f"           POST 데이터: {req['post_data'][:100]}...")

def suggest_optimal_loading_strategy(initial_tables, final_tables, network_requests):
    """최적 로딩 전략 제안"""
    print("      권장 로딩 전략:")
    print("      1. page.goto(url)")
    print("      2. wait_for_load_state('domcontentloaded')")
    print("      3. wait_for_load_state('networkidle')")
    
    if len(final_tables) > len(initial_tables):
        print("      4. ✅ 동적 테이블 로딩 확인됨 - 추가 대기 필요")
    
    ajax_count = len([r for r in network_requests if r['method'] in ['POST', 'PUT']])
    if ajax_count > 0:
        print(f"      5. ⚠️ {ajax_count}개 AJAX 요청 확인 - 데이터 로딩 완료까지 추가 대기")
        print("         - #container table tbody tr 요소 확인")
        print("         - 첫 번째 행에 실제 데이터 있는지 확인")
    
    print("\n      💻 구현 예시:")
    print("""
    await page.goto(url)
    await page.wait_for_load_state('networkidle')
    
    # 데이터 테이블 로딩 완료 대기
    await page.wait_for_selector('#container table tbody tr', timeout=15000)
    
    # 실제 데이터 확인
    for attempt in range(10):
        rows = await page.query_selector_all('#container table tbody tr')
        if rows and len(rows) > 0:
            first_row_text = await rows[0].text_content()
            if first_row_text.strip() and '로딩' not in first_row_text:
                break
        await page.wait_for_timeout(1000)
    """)

if __name__ == "__main__":
    asyncio.run(analyze_koicd_page())