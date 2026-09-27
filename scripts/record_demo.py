import argparse
import os
from io import BytesIO
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description='Record the Folio demo using an isolated browser.')
parser.add_argument('--base-url', default='http://127.0.0.1:8000')
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/assets/demo.gif')
args = parser.parse_args()
base_url = args.base_url.rstrip('/')
frames = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH'), headless=True)
    page = browser.new_page(viewport={'width': 1200, 'height': 860}, device_scale_factor=1, color_scheme='light', reduced_motion='reduce')
    def capture():
        shot = Image.open(BytesIO(page.screenshot())).convert('RGB')
        frames.append(shot.quantize(colors=256))
    page.goto(base_url + '/', wait_until='networkidle')
    capture()
    page.get_by_role('link', name='Explore the journal').click()
    capture()
    page.locator('.post-card [data-save-id]').nth(0).click()
    page.locator('.post-card [data-save-id]').nth(1).click()
    page.get_by_role('link', name='Reading list').click()
    page.wait_for_load_state('networkidle')
    capture()
    page.locator('.post-card h3 a').first.click()
    page.wait_for_load_state('networkidle')
    capture()
    page.goto(base_url + '/', wait_until='networkidle')
    page.get_by_role('button', name='Switch to dark theme').click()
    capture()
    browser.close()
output = args.output
output.parent.mkdir(parents=True, exist_ok=True)
frames[0].save(output, save_all=True, append_images=frames[1:], duration=[3000]*5, loop=0, optimize=True)
with Image.open(output) as gif:
    assert gif.n_frames == 5
    assert gif.size == (1200, 860)
print(f'Demo refreshed: {output.stat().st_size:,} bytes, 5 screens, 15 seconds.')
