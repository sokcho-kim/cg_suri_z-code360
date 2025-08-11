{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 1,
   "id": "348c1bb6",
   "metadata": {},
   "outputs": [
    {
     "ename": "RuntimeError",
     "evalue": "asyncio.run() cannot be called from a running event loop",
     "output_type": "error",
     "traceback": [
      "\u001b[1;31m---------------------------------------------------------------------------\u001b[0m",
      "\u001b[1;31mRuntimeError\u001b[0m                              Traceback (most recent call last)",
      "Cell \u001b[1;32mIn[1], line 30\u001b[0m\n\u001b[0;32m     27\u001b[0m         \u001b[38;5;28;01mawait\u001b[39;00m browser\u001b[38;5;241m.\u001b[39mclose()\n\u001b[0;32m     29\u001b[0m \u001b[38;5;66;03m# 실행\u001b[39;00m\n\u001b[1;32m---> 30\u001b[0m \u001b[43masyncio\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mrun\u001b[49m\u001b[43m(\u001b[49m\u001b[43mdebug_page_structure\u001b[49m\u001b[43m(\u001b[49m\u001b[43m)\u001b[49m\u001b[43m)\u001b[49m\n",
      "File \u001b[1;32mc:\\Users\\sokch\\.conda\\envs\\suri-play\\lib\\asyncio\\runners.py:33\u001b[0m, in \u001b[0;36mrun\u001b[1;34m(main, debug)\u001b[0m\n\u001b[0;32m      9\u001b[0m \u001b[38;5;250m\u001b[39m\u001b[38;5;124;03m\"\"\"Execute the coroutine and return the result.\u001b[39;00m\n\u001b[0;32m     10\u001b[0m \n\u001b[0;32m     11\u001b[0m \u001b[38;5;124;03mThis function runs the passed coroutine, taking care of\u001b[39;00m\n\u001b[1;32m   (...)\u001b[0m\n\u001b[0;32m     30\u001b[0m \u001b[38;5;124;03m    asyncio.run(main())\u001b[39;00m\n\u001b[0;32m     31\u001b[0m \u001b[38;5;124;03m\"\"\"\u001b[39;00m\n\u001b[0;32m     32\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m events\u001b[38;5;241m.\u001b[39m_get_running_loop() \u001b[38;5;129;01mis\u001b[39;00m \u001b[38;5;129;01mnot\u001b[39;00m \u001b[38;5;28;01mNone\u001b[39;00m:\n\u001b[1;32m---> 33\u001b[0m     \u001b[38;5;28;01mraise\u001b[39;00m \u001b[38;5;167;01mRuntimeError\u001b[39;00m(\n\u001b[0;32m     34\u001b[0m         \u001b[38;5;124m\"\u001b[39m\u001b[38;5;124masyncio.run() cannot be called from a running event loop\u001b[39m\u001b[38;5;124m\"\u001b[39m)\n\u001b[0;32m     36\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m \u001b[38;5;129;01mnot\u001b[39;00m coroutines\u001b[38;5;241m.\u001b[39miscoroutine(main):\n\u001b[0;32m     37\u001b[0m     \u001b[38;5;28;01mraise\u001b[39;00m \u001b[38;5;167;01mValueError\u001b[39;00m(\u001b[38;5;124m\"\u001b[39m\u001b[38;5;124ma coroutine was expected, got \u001b[39m\u001b[38;5;132;01m{!r}\u001b[39;00m\u001b[38;5;124m\"\u001b[39m\u001b[38;5;241m.\u001b[39mformat(main))\n",
      "\u001b[1;31mRuntimeError\u001b[0m: asyncio.run() cannot be called from a running event loop"
     ]
    }
   ],
   "source": [
    "import asyncio\n",
    "from playwright.async_api import async_playwright\n",
    "\n",
    "async def debug_page_structure():\n",
    "    async with async_playwright() as p:\n",
    "        browser = await p.chromium.launch(headless=False)\n",
    "        page = await browser.new_page()\n",
    "        \n",
    "        await page.goto(\"https://www.koicd.kr/ins/act.do\")\n",
    "        await page.wait_for_load_state('networkidle')\n",
    "        \n",
    "        # 첫 번째 데이터 행 찾기\n",
    "        first_row = await page.query_selector(\"#container table tbody tr[class*='digit']\")\n",
    "        if first_row:\n",
    "            tds = await first_row.query_selector_all(\"td\")\n",
    "            print(f\"TD 개수: {len(tds)}\")\n",
    "            \n",
    "            for i, td in enumerate(tds):\n",
    "                text = await td.text_content()\n",
    "                print(f\"TD[{i}]: '{text.strip()}'\")\n",
    "                \n",
    "                # 클릭 가능한 요소 확인\n",
    "                clickable = await td.query_selector(\"a, button, [onclick]\")\n",
    "                if clickable:\n",
    "                    print(f\"  → 클릭 가능한 요소 있음\")\n",
    "        \n",
    "        await browser.close()\n",
    "\n",
    "# 실행\n",
    "asyncio.run(debug_page_structure())"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "1e8233e6",
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "suri-play",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.10.18"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
