import asyncio
from playwright.async_api import async_playwright

async def debug_koicd_structure():
    """KOICD 페이지의 실제 구조를 분석하여 토글 버튼과 하위 행 패턴 파악"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("🔍 KOICD 페이지 구조 디버깅 시작...")
            
            await page.goto("https://www.koicd.kr/ins/act.do")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_selector('table.act_table tbody tr', timeout=15000)
            
            # 모든 행 가져오기
            rows = await page.query_selector_all('table.act_table tbody tr')
            print(f"📊 총 {len(rows)}개 행 발견")
            
            # 처음 5개 행 상세 분석
            for i in range(min(5, len(rows))):
                row = rows[i]
                row_class = await row.get_attribute("class")
                
                print(f"\n🔍 행 {i+1} 분석 (class: '{row_class}'):")
                
                # TD 구조 분석
                tds = await row.query_selector_all("td")
                print(f"   TD 개수: {len(tds)}")
                
                for j, td in enumerate(tds):
                    td_text = (await td.text_content()).strip()
                    td_html = await td.inner_html()
                    cursor = await td.evaluate('el => window.getComputedStyle(el).cursor')
                    onclick = await td.get_attribute('onclick')
                    
                    print(f"   TD[{j}]: '{td_text[:50]}...'")
                    print(f"        HTML: {td_html[:100]}...")
                    print(f"        Cursor: {cursor}")
                    print(f"        Onclick: {onclick}")
                    
                    # 토글 버튼 요소 찾기
                    toggle_elements = await td.query_selector_all("*")
                    for k, elem in enumerate(toggle_elements):
                        elem_text = (await elem.text_content()).strip()
                        elem_tag = await elem.evaluate('el => el.tagName')
                        if '+' in elem_text or '-' in elem_text:
                            print(f"        토글 후보[{k}]: {elem_tag} = '{elem_text}'")
                
                # 클릭 테스트 (첫 번째 행만)
                if i == 0:
                    print(f"\n🖱️  첫 번째 행 클릭 테스트...")
                    
                    # 스크린샷 - 클릭 전
                    await page.screenshot(path="before_click.png")
                    
                    # TD[0] 클릭 시도
                    try:
                        await tds[0].click()
                        await asyncio.sleep(2)
                        print("   TD[0] 클릭 완료")
                        
                        # 스크린샷 - 클릭 후
                        await page.screenshot(path="after_click.png")
                        
                        # 행 개수 변화 확인
                        new_rows = await page.query_selector_all('table.act_table tbody tr')
                        print(f"   클릭 후 행 개수: {len(new_rows)} (변화: {len(new_rows) - len(rows)})")
                        
                        # 새로 나타난 행들 분석
                        if len(new_rows) > len(rows):
                            print("   🎉 새로운 행들이 나타남!")
                            for new_i in range(len(rows), len(new_rows)):
                                new_row = new_rows[new_i]
                                new_class = await new_row.get_attribute("class")
                                new_content = await new_row.text_content()
                                print(f"      새 행[{new_i}]: class='{new_class}', 내용='{new_content[:100]}...'")
                        else:
                            print("   ⚠️ 새로운 행이 나타나지 않음")
                            
                            # 다른 TD들도 시도
                            for td_idx in range(1, min(3, len(tds))):
                                print(f"   TD[{td_idx}] 클릭 시도...")
                                try:
                                    await tds[td_idx].click()
                                    await asyncio.sleep(2)
                                    
                                    newer_rows = await page.query_selector_all('table.act_table tbody tr')
                                    if len(newer_rows) > len(rows):
                                        print(f"      ✅ TD[{td_idx}] 클릭으로 {len(newer_rows) - len(rows)}개 행 추가됨!")
                                        break
                                except Exception as e:
                                    print(f"      ❌ TD[{td_idx}] 클릭 실패: {e}")
                        
                    except Exception as e:
                        print(f"   ❌ 클릭 실패: {e}")
                
                print("-" * 50)
            
            # 페이지 전체 구조 분석
            print("\n📋 페이지 전체 구조 분석:")
            
            # 모든 '+' 텍스트가 포함된 요소 찾기
            plus_elements = await page.query_selector_all("*:has-text('+')")
            print(f"'+' 텍스트 포함 요소: {len(plus_elements)}개")
            
            for i, elem in enumerate(plus_elements[:10]):  # 처음 10개만
                elem_text = await elem.text_content()
                elem_tag = await elem.evaluate('el => el.tagName')
                elem_class = await elem.get_attribute('class')
                print(f"   [{i}] {elem_tag}.{elem_class}: '{elem_text[:50]}...'")
            
            # JavaScript 기반 토글 함수 찾기
            print("\n🔧 JavaScript 토글 함수 분석:")
            js_functions = await page.evaluate("""
                () => {
                    const functions = [];
                    for (let prop in window) {
                        if (typeof window[prop] === 'function' && 
                            (prop.includes('toggle') || prop.includes('expand') || prop.includes('fold'))) {
                            functions.push(prop);
                        }
                    }
                    return functions;
                }
            """)
            print(f"토글 관련 함수들: {js_functions}")
            
        except Exception as e:
            print(f"❌ 디버깅 실패: {e}")
        
        finally:
            input("브라우저를 닫으려면 Enter를 누르세요...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_koicd_structure())