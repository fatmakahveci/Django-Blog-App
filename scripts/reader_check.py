"""Browser checks for reader features. Use a disposable, seeded demo database."""
import argparse
import os
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright


parser = argparse.ArgumentParser(description='Test the ten reader features on a disposable demo instance. Submits a reaction and a poll vote.')
parser.add_argument('--base-url', default='http://127.0.0.1:8000')
parser.add_argument('--output', type=Path, default=Path(tempfile.gettempdir()) / 'folio-reader-browser')
args = parser.parse_args()
base = args.base_url.rstrip('/')
args.output.mkdir(parents=True, exist_ok=True)
article_url = base + '/posts/demo-less-noise-more-ideas/'

with sync_playwright() as runtime:
    browser = runtime.chromium.launch(executable_path=os.environ.get('CHROME_PATH'), headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, color_scheme='light')
    errors = []
    context.on('page', lambda item: item.on('pageerror', lambda error: errors.append(str(error))))
    page = context.new_page()
    assert page.goto(base + '/discover/', wait_until='networkidle').status == 200
    page.get_by_role('heading', name='Discover', exact=True, level=1).wait_for()
    page.screenshot(path=str(args.output / 'discover-desktop.png'), full_page=True)
    page.get_by_label('Reading length').select_option('long')
    page.get_by_role('button', name='Search and sort').click()
    page.get_by_text('A different length, a new discovery.').wait_for()
    page.get_by_label('Reading length').select_option('short')
    page.get_by_role('button', name='Search and sort').click()
    assert page.locator('.post-card').count() == 6
    page.get_by_role('button', name='Follow Design', exact=True).click()
    page.get_by_role('link', name='For you', exact=True).click()
    page.wait_for_load_state('networkidle')
    assert page.locator('.post-card').count() == 2
    assert page.locator('.card-meta > span:first-child').all_text_contents() == ['Design', 'Design']
    page.reload(wait_until='networkidle')
    assert page.locator('.post-card').count() == 2
    page.screenshot(path=str(args.output / 'personal-feed.png'), full_page=True)
    page.get_by_role('link', name='Discover', exact=True).click()
    page.get_by_role('button', name='Following Design', exact=True).click()
    page.get_by_role('link', name='For you', exact=True).click()
    page.get_by_text('Make this space yours.').wait_for()
    page.get_by_role('link', name='Collections', exact=True).click()
    page.locator('.collection-card').filter(has_text='A calmer digital life').click()
    assert page.locator('.post-card').count() == 3
    page.locator('.post-card h3 a').first.click()
    page.get_by_role('navigation', name='Collection reading order').wait_for()
    assert 'collection=demo-a-calmer-digital-life' in page.url
    assert page.get_by_role('link', name='Next in this collection').count() == 1
    print('Discovery, reading-length filters, topic following, personal feed, and collection navigation passed.', flush=True)

    page.locator('button[name=kind][value=insightful]').click()
    assert page.locator('button[name=kind][value=insightful]').get_attribute('aria-pressed') == 'true'
    page.get_by_label('A quiet moment', exact=True).check()
    page.get_by_role('button', name='Cast my vote').click()
    page.get_by_text('Your vote is in. Thank you for taking part.').wait_for()
    assert page.locator('.poll-results summary').inner_text() == 'Results · 1 vote'
    assert page.get_by_text('· Your vote', exact=True).count() == 1
    page.reload(wait_until='networkidle')
    assert page.locator('.poll-results summary').inner_text() == 'Results · 1 vote'
    page.get_by_role('link', name='Trending', exact=True).click()
    assert page.locator('.post-card').count() == 1
    assert page.locator('.activity-label').inner_text() == '1 response this week'
    page.screenshot(path=str(args.output / 'trending.png'), full_page=True)
    page.goto(article_url, wait_until='networkidle')
    page.get_by_label('Text size', exact=True).select_option('large')
    assert page.locator('.prose').evaluate('(element) => getComputedStyle(element).fontSize') == '24px'
    page.get_by_role('button', name='Focus mode', exact=True).click()
    assert not page.locator('.site-header').is_visible()
    page.reload(wait_until='networkidle')
    assert page.get_by_label('Text size', exact=True).input_value() == 'large'
    assert not page.locator('.site-header').is_visible()
    page.screenshot(path=str(args.output / 'focus-reading.png'), full_page=True)
    page.keyboard.press('Escape')
    assert page.locator('.site-header').is_visible()
    page.get_by_label('Text size', exact=True).select_option('standard')
    # Clear through the UI so an open article's pagehide handler cannot restore it.
    page.goto(base + '/reading-history/', wait_until='networkidle')
    page.get_by_role('button', name='Clear reading history').click()
    page.get_by_text('Your next reading session starts here.').wait_for()
    page.goto(article_url, wait_until='networkidle')
    page.evaluate("""() => {
      const box = document.querySelector('[data-article-body]').getBoundingClientRect();
      scrollTo({top: scrollY + box.top - innerHeight * .3 + Math.max(1, box.height - innerHeight * .5) * .45, behavior: 'instant'});
    }""")
    page.wait_for_function("Number(document.querySelector('.reading-progress').getAttribute('aria-valuenow')) >= 40")
    page.get_by_role('link', name='Continue reading', exact=True).click()
    page.wait_for_load_state('networkidle')
    page.locator('[data-resume-card]').first.click()
    page.wait_for_function("Number(document.querySelector('.reading-progress').getAttribute('aria-valuenow')) >= 35")
    page.get_by_role('button', name='Resume at').wait_for()
    second = context.new_page()
    second.goto(article_url, wait_until='networkidle')
    page.goto(base + '/reading-history/', wait_until='networkidle')
    page.get_by_role('button', name='Clear reading history').click()
    page.get_by_text('Your next reading session starts here.').wait_for()
    second.close()
    assert len(page.evaluate("JSON.parse(localStorage.getItem('folio.history'))")) == 0
    print('Reactions, one-vote poll results, weekly ranking, reading controls, resume, and cross-tab history clearing passed.', flush=True)

    for path in ('/discover/', '/collections/', '/for-you/', '/reading-history/', '/trending/', '/posts/demo-less-noise-more-ideas/'):
        for width in (320, 390, 768, 1440):
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.goto(base + path, wait_until='networkidle').status == 200
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}px on {path}'
        if path == '/discover/':
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(args.output / 'discover-mobile.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(article_url, wait_until='networkidle')
    page.screenshot(path=str(args.output / 'article-mobile.png'), full_page=True)
    page.get_by_role('button', name='Switch to dark theme').click()
    page.screenshot(path=str(args.output / 'article-dark-mobile.png'), full_page=True)
    page.goto(base + '/surprise/', wait_until='networkidle')
    assert '/posts/demo-' in page.url

    # Test playback lifecycle deterministically; CI has no installed audio device.
    audio = browser.new_context()
    audio.add_init_script("""(() => {
      const synth = new EventTarget();
      window.__audio = { calls: [], pauses: 0, resumes: 0 };
      synth.getVoices = () => [{localService: true, lang: 'en-GB', name: 'Test device voice'}];
      synth.paused = false;
      synth.speak = utterance => window.__audio.calls.push(utterance);
      synth.cancel = () => {};
      synth.pause = () => { synth.paused = true; window.__audio.pauses++; };
      synth.resume = () => { synth.paused = false; window.__audio.resumes++; };
      Object.defineProperty(window, 'speechSynthesis', {value: synth});
      window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } };
    })();""")
    listen_page = audio.new_page()
    listen_page.on('pageerror', lambda error: errors.append(str(error)))
    listen_page.goto(article_url, wait_until='networkidle')
    listen_page.get_by_role('button', name='Listen to article').click()
    assert listen_page.evaluate('window.__audio.calls.length') == 1
    listen_page.get_by_role('button', name='Pause audio').click()
    assert listen_page.evaluate('window.__audio.pauses') == 1
    listen_page.get_by_role('button', name='Resume audio').click()
    assert listen_page.evaluate('window.__audio.resumes') == 1
    listen_page.get_by_label('Playback speed').select_option('1.5')
    assert listen_page.evaluate('window.__audio.calls.at(-1).rate') == 1.5
    listen_page.evaluate('window.__audio.calls.at(-1).onend()')
    assert listen_page.evaluate('window.__audio.calls.length') == 3
    listen_page.get_by_role('button', name='Stop listening').click()
    listen_page.evaluate('window.__audio.calls.at(-1).onend()')
    assert listen_page.evaluate('window.__audio.calls.length') == 3
    assert listen_page.get_by_role('button', name='Listen to article').is_visible()
    listen_page.get_by_role('button', name='Listen to article').click()
    listen_page.get_by_role('button', name='Pause audio').click()
    listen_page.get_by_role('button', name='Stop listening').click()
    listen_page.get_by_role('button', name='Listen to article').click()
    assert listen_page.evaluate('window.speechSynthesis.paused') is False
    audio.close()

    fallback = browser.new_context()
    fallback.add_init_script("""(() => {
      Object.defineProperty(window, 'speechSynthesis', {value: undefined});
      Storage.prototype.getItem = () => { throw new DOMException('Blocked', 'SecurityError'); };
      Storage.prototype.setItem = () => { throw new DOMException('Blocked', 'SecurityError'); };
    })();""")
    blocked = fallback.new_page()
    blocked.on('pageerror', lambda error: errors.append(str(error)))
    blocked.goto(base + '/discover/', wait_until='networkidle')
    blocked.get_by_role('button', name='Follow Design', exact=True).click()
    blocked.get_by_text('Your browser could not save your topics. Please check your privacy settings.').wait_for()
    blocked.goto(article_url, wait_until='networkidle')
    blocked.get_by_text('Read-aloud is unavailable in this browser.').wait_for()
    blocked.get_by_label('Text size', exact=True).select_option('large')
    assert blocked.locator('.prose').evaluate('(element) => getComputedStyle(element).fontSize') == '24px'
    fallback.close()
    nojs = browser.new_context(java_script_enabled=False, reduced_motion='reduce')
    static_page = nojs.new_page()
    static_page.goto(article_url)
    static_page.locator('button[name=kind][value=useful]').press('Enter')
    static_page.wait_for_load_state('networkidle')
    assert static_page.locator('button[name=kind][value=useful]').get_attribute('aria-pressed') == 'true'
    static_page.get_by_role('button', name='Remove reaction').press('Enter')
    static_page.wait_for_load_state('networkidle')
    assert static_page.locator('button[name=kind][value=useful]').get_attribute('aria-pressed') == 'false'
    nojs.close()
    assert not errors, errors
    context.close()
    browser.close()
print('Reader browser checks passed, including 320–1440px layouts, speech controls with a test voice, unavailable audio/storage, and no-JavaScript reactions.')
print('Screenshots:', args.output)
