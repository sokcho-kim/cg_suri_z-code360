import asyncio
from playwright.async_api import async_playwright

async def test_single_row_toggle():
    """단일 행의 토글 기능을 집중적으로 테스트"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("🔍 KOICD 단일 행 토글 테스트 시작...")
            
            await page.goto("https://www.koicd.kr/ins/act.do")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_selector('table.act_table tbody tr', timeout=15000)
            
            # 첫 번째 메인 행 선택
            rows = await page.query_selector_all('table.act_table tbody tr')
            main_rows = []
            
            for row in rows:
                row_class = await row.get_attribute("class")
                if row_class and any(c.isdigit() for c in row_class):
                    main_rows.append(row)
            
            if not main_rows:
                print("❌ 메인 행을 찾을 수 없습니다.")
                return
            
            test_row = main_rows[0]
            print(f"🎯 테스트 대상: 첫 번째 메인 행")
            
            # 기본 정보 추출
            tds = await test_row.query_selector_all("td")
            if len(tds) >= 2:
                code = (await tds[1].text_content()).strip()
                name = (await tds[2].text_content()).strip() if len(tds) > 2 else ""
                print(f"   수가코드: {code}")
                print(f"   행위명: {name[:50]}...")
            
            # 초기 행 개수 확인
            initial_count = len(await page.query_selector_all('table.act_table tbody tr'))
            print(f"📊 초기 행 개수: {initial_count}")
            
            # TD 별 클릭 테스트
            for i, td in enumerate(tds[:3]):
                print(f"\n🖱️  TD[{i}] 클릭 테스트:")
                
                td_text = (await td.text_content()).strip()
                td_html = await td.inner_html()
                print(f"   텍스트: '{td_text}'")
                print(f"   HTML: {td_html[:100]}...")
                
                # 스크린샷 - 클릭 전
                await page.screenshot(path=f"before_td{i}_click.png")
                
                try:
                    # 클릭 시도
                    await td.click()
                    print(f"   TD[{i}] 클릭 완료")
                    
                    # 변화 확인 (3초 대기)
                    await asyncio.sleep(3)
                    
                    # 스크린샷 - 클릭 후
                    await page.screenshot(path=f"after_td{i}_click.png")
                    
                    # 행 개수 변화 확인
                    current_count = len(await page.query_selector_all('table.act_table tbody tr'))
                    change = current_count - initial_count
                    
                    print(f"   클릭 후 행 개수: {current_count} (변화: {change:+d})")
                    
                    if change > 0:
                        print(f"   🎉 SUCCESS! {change}개 하위 행이 나타났습니다!")
                        
                        # 새로 나타난 행들 분석
                        all_rows = await page.query_selector_all('table.act_table tbody tr')
                        for j in range(initial_count, current_count):
                            new_row = all_rows[j]
                            new_class = await new_row.get_attribute("class")
                            new_tds = await new_row.query_selector_all("td")
                            new_content = ""
                            if len(new_tds) >= 2:
                                new_content = (await new_tds[1].text_content()).strip()
                            
                            print(f"      새 행[{j}]: class='{new_class}', 내용='{new_content[:30]}...'")
                        
                        # 다시 클릭해서 접기 테스트
                        print(f"   접기 테스트...")
                        await td.click()
                        await asyncio.sleep(2)
                        
                        final_count = len(await page.query_selector_all('table.act_table tbody tr'))
                        if final_count == initial_count:
                            print(f"   ✅ 접기 성공: 원래 행 개수로 복원")
                        else:
                            print(f"   ⚠️ 접기 결과: {final_count}개 행 (예상: {initial_count})")
                        
                        # 테스트 완료
                        print(f"\n🎯 TD[{i}]에서 토글 기능 확인 완료!")
                        break
                    
                    elif change == 0:
                        # 팝업이 나타났는지 확인
                        popup = await page.query_selector(".div_table_style")
                        if popup and await popup.is_visible():
                            print(f"   📋 상세정보 팝업이 나타남")
                            
                            # 팝업 닫기
                            close_btn = await popup.query_selector("button:has-text('닫기')")
                            if close_btn:
                                await close_btn.click()
                                await asyncio.sleep(1)
                                print(f"   팝업 닫기 완료")
                        else:
                            print(f"   변화 없음")
                    
                except Exception as e:
                    print(f"   ❌ TD[{i}] 클릭 실패: {e}")
                    continue
            
            print(f"\n📋 모든 TD 클릭 테스트 완료")
            
            # JavaScript 함수 확인
            toggle_functions = await page.evaluate("""
                () => {
                    const functions = [];
                    for (let prop in window) {
                        if (typeof window[prop] === 'function') {
                            const funcStr = window[prop].toString();
                            if (funcStr.includes('toggle') || funcStr.includes('expand') || 
                                funcStr.includes('fold') || funcStr.includes('child') ||
                                funcStr.includes('sub') || funcStr.includes('detail')) {
                                functions.push({
                                    name: prop,
                                    code: funcStr.substring(0, 200) + '...'
                                });
                            }
                        }
                    }
                    return functions;
                }
            """)
            
            if toggle_functions:
                print(f"\n🔧 발견된 토글 관련 JavaScript 함수들:")
                for func in toggle_functions:
                    print(f"   {func['name']}: {func['code']}")
            else:
                print(f"\n⚠️ 토글 관련 JavaScript 함수를 찾을 수 없음")
            
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
        
        finally:
            input("브라우저를 닫으려면 Enter를 누르세요...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_single_row_toggle())