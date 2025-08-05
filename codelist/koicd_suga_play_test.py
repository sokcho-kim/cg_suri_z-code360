import asyncio
from playwright.async_api import async_playwright

async def debug_page_structure():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        await page.goto("https://www.koicd.kr/ins/act.do")
        await page.wait_for_load_state('networkidle')
        
        # 첫 번째 데이터 행 찾기
        first_row = await page.query_selector("#container table tbody tr[class*='digit']")
        if first_row:
            tds = await first_row.query_selector_all("td")
            print(f"TD 개수: {len(tds)}")
            
            for i, td in enumerate(tds):
                text = await td.text_content()
                print(f"TD[{i}]: '{text.strip()}'")
                
                # 클릭 가능한 요소 확인
                clickable = await td.query_selector("a, button, [onclick]")
                if clickable:
                    print(f"  → 클릭 가능한 요소 있음")
        
        await browser.close()

# 실행
asyncio.run(debug_page_structure())