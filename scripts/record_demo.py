import argparse
import os
from io import BytesIO
from pathlib import Path
from PIL import Image
from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser(description='Record nine Folio reader scenes using an isolated browser and seeded demo content.')
parser.add_argument('--base-url', default='http://127.0.0.1:8000')
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/assets/demo.gif')
args = parser.parse_args()
base_url = args.base_url.rstrip('/')
frames = []
scenes = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH'), headless=True)
    page = browser.new_page(viewport={'width': 1200, 'height': 860}, device_scale_factor=1, color_scheme='light', reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def capture(scene):
        page.evaluate('document.fonts.ready')
        page.locator('#toast').wait_for(state='hidden')
        page.mouse.move(1195, 855)
        shot = Image.open(BytesIO(page.screenshot(animations='disabled'))).convert('RGB')
        frames.append(shot.quantize(colors=256))
        scenes.append(scene)

    def top():
        page.evaluate("scrollTo({top: 0, behavior: 'instant'})")

    def show_section(selector, offset=115):
        # Frame the feature below the sticky header, not below the viewport.
        page.locator(selector).evaluate("(element, offset) => scrollTo({top: Math.max(0, scrollY + element.getBoundingClientRect().top - offset), behavior: 'instant'})", offset)

    assert page.goto(base_url + '/', wait_until='networkidle').status == 200
    capture('The journal')

    page.get_by_role('link', name='Discover', exact=True).click()
    page.get_by_role('button', name='Follow Design', exact=True).click()
    expect(page.get_by_role('button', name='Following Design', exact=True)).to_be_visible()
    show_section('.discovery-welcome')
    expect(page.get_by_role('button', name='Following Design', exact=True)).to_be_in_viewport()
    capture('Discover and follow topics')

    page.get_by_role('link', name='For you', exact=True).click()
    page.wait_for_load_state('networkidle')
    expect(page.locator('.post-card')).to_have_count(2)
    page.locator('.post-card [data-save-id]').nth(0).click()
    page.locator('.post-card [data-save-id]').nth(1).click()
    show_section('#journal', offset=85)
    expect(page.locator('.post-card h3').first).to_be_in_viewport()
    capture('Your personal feed')

    page.get_by_role('link', name='Collections', exact=True).click()
    page.locator('.collection-card').filter(has_text='A calmer digital life').click()
    page.wait_for_load_state('networkidle')
    expect(page.locator('.post-card')).to_have_count(3)
    show_section('.page-intro .eyebrow')
    capture('Curated reading collections')

    page.locator('.post-card h3 a').first.click()
    page.wait_for_load_state('networkidle')
    expect(page.get_by_role('heading', name='Less noise. More room for ideas.', exact=True)).to_be_visible()
    expect(page.get_by_label('Text size', exact=True)).to_be_visible()
    capture('Article and reader controls')

    page.get_by_label('Text size', exact=True).select_option('large')
    page.get_by_role('button', name='Focus mode', exact=True).click()
    expect(page.locator('.site-header')).to_be_hidden()
    top()
    capture('Focus mode and larger text')

    page.get_by_role('button', name='Exit focus mode', exact=True).click()
    page.get_by_label('Text size', exact=True).select_option('standard')
    # Show the real feedback forms without submitting reactions or poll votes.
    show_section('#reactions')
    expect(page.get_by_role('button', name='Cast my vote')).to_be_visible()
    capture('Reactions and reader polls')

    page.get_by_role('link', name='Reading list').click()
    page.wait_for_load_state('networkidle')
    expect(page.locator('.post-card')).to_have_count(2)
    show_section('#journal', offset=85)
    expect(page.locator('.post-card h3').first).to_be_in_viewport()
    capture('Saved for later')

    page.goto(base_url + '/', wait_until='networkidle')
    page.get_by_role('button', name='Switch to dark theme').click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    capture('Dark theme')
    browser.close()
    assert not errors, errors
output = args.output
output.parent.mkdir(parents=True, exist_ok=True)
assert len(frames) == 9, scenes
frames[0].save(output, save_all=True, append_images=frames[1:], duration=[3000]*len(frames), loop=0, optimize=True, disposal=2)
with Image.open(output) as gif:
    assert gif.n_frames == len(frames)
    assert gif.size == (1200, 860)
    assert gif.info['loop'] == 0
    for index in range(gif.n_frames):
        gif.seek(index)
        assert gif.info['duration'] == 3000
print(f'Demo refreshed: {output.stat().st_size:,} bytes, {len(frames)} scenes, {len(frames) * 3} seconds.')
print('Scenes: ' + ' → '.join(scenes))
