"""Browser regression for the shared renderer; requires Vite on port 5174."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:5174", wait_until="domcontentloaded")
        result = await page.evaluate("""async () => {
            const { renderMarkdown } = await import('/src/utils/markdown.ts');
            window.markdownAttack = 0;
            const payloads = [
                '<img src=x onerror="window.markdownAttack=1">',
                "<img src=x onerror='window.markdownAttack=1'>",
                '<img src=x onerror=window.markdownAttack=1>',
                '<svg onload=window.markdownAttack=1></svg>',
                '<iframe srcdoc="<script>parent.markdownAttack=1</script>"></iframe>',
                '[bad](javascript:alert(1))',
            ];
            const container = document.createElement('div');
            document.body.append(container);
            for (const payload of payloads) {
                container.innerHTML = renderMarkdown(payload);
                if (container.querySelector('script,iframe,svg,[onerror],[onload]')) {
                    throw new Error('Unsafe HTML survived sanitization');
                }
                for (const link of container.querySelectorAll('a')) {
                    if (link.protocol === 'javascript:') throw new Error('Unsafe link');
                }
            }
            container.innerHTML = renderMarkdown('**safe** [link](https://example.com) 【来源1】', true);
            if (!container.querySelector('strong') || !container.querySelector('a') ||
                !container.querySelector('.cite-ref[data-cite="1"]')) {
                throw new Error('Markdown or citation rendering regressed');
            }
            await new Promise(resolve => requestAnimationFrame(resolve));
            if (window.markdownAttack !== 0) throw new Error('Injected HTML executed');
            container.remove();
            return {payloads: payloads.length, markdown: true, citations: true};
        }""")
        print(result)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
