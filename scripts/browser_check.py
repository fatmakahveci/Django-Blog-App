import argparse
import os
import re
import tempfile
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser(description='Check Folio in an isolated browser against the eight-article demo dataset.')
parser.add_argument('--base-url', default='http://127.0.0.1:8000')
parser.add_argument('--output', type=Path, default=Path(tempfile.gettempdir()) / 'folio-browser')
args = parser.parse_args()
base_url = args.base_url.rstrip('/')
out = args.output
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH'), headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1050}, color_scheme='light', permissions=['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    errors = []
    policy_errors = []
    page.on('console', lambda message: policy_errors.append(message.text)
            if message.type == 'error' and 'Content Security Policy' in message.text else None)
    page.on('pageerror', lambda error: errors.append(str(error)))
    assert page.goto(base_url + '/', wait_until='networkidle').status == 200
    assert page.locator('html').get_attribute('lang') == 'en'
    page.keyboard.press('/')
    assert page.get_by_role('searchbox').evaluate('(element) => element === document.activeElement')
    page.keyboard.press('Escape')
    assert not page.get_by_role('searchbox').evaluate('(element) => element === document.activeElement')
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.screenshot(path=str(out / 'desktop.png'), full_page=True)
    page.screenshot(path=str(out / 'desktop-top.png'))
    assert page.locator('.post-card').count() == 6
    page.get_by_role('button', name='Switch to dark theme').click()
    assert page.locator('html').get_attribute('data-theme') == 'dark'
    page.reload(wait_until='networkidle')
    assert page.locator('html').get_attribute('data-theme') == 'dark'
    page.screenshot(path=str(out / 'dark.png'))
    page.get_by_role('button', name='Switch to light theme').click()
    featured_save = page.locator('.featured [data-save-id]')
    featured_save.click()
    assert featured_save.get_attribute('aria-pressed') == 'true'
    assert featured_save.locator('svg').count() == 1, 'Saving should preserve the button icon'
    featured_save.click()
    first_card = page.locator('.post-card').first
    saved_title = first_card.locator('h3').inner_text()
    first_card.get_by_role('button', name='Save').click()
    assert first_card.get_by_role('button', name='Saved').get_attribute('aria-pressed') == 'true'
    page.get_by_role('link', name='Reading list').click()
    page.wait_for_load_state('networkidle')
    assert page.locator('.post-card').count() == 1
    assert page.locator('.post-card h3').inner_text() == saved_title
    page.locator('.post-card h3 a').click()
    page.wait_for_load_state('networkidle')
    page.screenshot(path=str(out / 'article.png'), full_page=True)
    page.get_by_role('button', name='Copy link').click()
    page.get_by_text('Article link copied.').wait_for()
    assert page.evaluate('navigator.clipboard.readText()') == page.url
    page.locator('.article-end').scroll_into_view_if_needed()
    expect(page.locator('.reading-progress')).to_have_attribute('aria-valuenow', re.compile(r'(?:5[1-9]|[6-9][0-9]|100)'))
    page.get_by_role('link', name='Reading list').click()
    page.wait_for_load_state('networkidle')
    page.get_by_role('button', name='Saved').click()
    page.wait_for_load_state('networkidle')
    page.get_by_text('Room for your next discovery.').wait_for()
    page.goto(base_url + '/', wait_until='networkidle')
    page.get_by_role('searchbox').fill('interface')
    page.get_by_role('button', name='Search and sort').click()
    page.wait_for_load_state('networkidle')
    assert page.locator('.post-card').count() == 1
    assert 'interface' in page.locator('.post-card h3').inner_text()
    page.goto(base_url + '/?q=interface', wait_until='networkidle')
    page.get_by_role('link', name='Clear search').click()
    page.wait_for_load_state('networkidle')
    assert page.get_by_role('searchbox').input_value() == ''
    assert page.locator('.post-card').count() == 6
    page.goto(base_url + '/', wait_until='networkidle')
    page.get_by_role('link', name='Next').click()
    page.wait_for_load_state('networkidle')
    assert page.locator('.post-card').count() == 1
    assert page.goto(base_url + '/admin/login/', wait_until='networkidle').status == 200
    assert page.get_by_label('Username:').is_visible()
    assert not policy_errors, policy_errors
    # Inject into the DOM as an attacker would; trusted automation evaluate()
    # itself bypasses CSP and therefore cannot demonstrate script blocking.
    page.evaluate("""() => {
        window.inlineProbeRan = false;
        document.addEventListener('securitypolicyviolation', event => {
            document.body.dataset.blockedDirective = event.effectiveDirective;
        });
        const script = document.createElement('script');
        script.textContent = 'window.inlineProbeRan = true';
        document.body.append(script);
    }""")
    expect(page.locator('body')).to_have_attribute('data-blocked-directive', 'script-src-elem')
    assert page.evaluate('window.inlineProbeRan') is False
    context.close()
    mobile_context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, device_scale_factor=1, color_scheme='light')
    mobile = mobile_context.new_page()
    mobile.on('pageerror', lambda error: errors.append(str(error)))
    mobile.goto(base_url + '/', wait_until='networkidle')
    mobile.screenshot(path=str(out / 'mobile.png'), full_page=True)
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow on mobile home'
    mobile.screenshot(path=str(out / 'mobile-top.png'))
    for width in (320, 768, 1024):
        mobile.set_viewport_size({'width': width, 'height': 900})
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Horizontal overflow at {width}px'
    mobile.set_viewport_size({'width': 390, 'height': 844})
    mobile.get_by_role('link', name='Explore the journal').click()
    assert abs(mobile.locator('.site-header').bounding_box()['y']) < 1, 'Navigation should remain visible while scrolling'
    mobile.screenshot(path=str(out / 'mobile-journal.png'))
    mobile.locator('.featured h2 a').click()
    mobile.wait_for_load_state('networkidle')
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow on mobile article'
    mobile.screenshot(path=str(out / 'mobile-article.png'))
    mobile.emulate_media(media='print')
    assert not mobile.locator('.article-tools').is_visible()
    assert not mobile.locator('.comments-section').is_visible()
    mobile_context.close()
    nojs = browser.new_context(java_script_enabled=False, viewport={'width': 1000, 'height': 800})
    noscript_page = nojs.new_page()
    assert noscript_page.goto(base_url + '/').status == 200
    assert noscript_page.locator('.post-card').count() == 6
    nojs.close()
    browser.close()
    assert not errors, errors
print('Browser checks passed: theme persistence, featured/card bookmarks, sharing, reading progress, keyboard search and reset, pagination, 320–1440px layouts, sticky navigation, print layout, no-JS reading, CSP script blocking, and no JS errors.')
print('Screenshots:', out)
