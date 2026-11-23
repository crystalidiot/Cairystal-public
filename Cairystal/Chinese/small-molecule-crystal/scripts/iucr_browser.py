"""Submit the frozen CIF through the public IUCr form in a fresh browser session."""
import os
from time import perf_counter

FORM = "https://checkcif.iucr.org/"
SUBMIT = FORM + "cgi-bin/checkcif_hkl.pl"


def fill_form(page, payload, options):
    form = page.locator("#checkcif-form")
    if form.count() != 1 or form.evaluate(
        "f => [f.action, f.method, f.enctype, f.target]"
    ) != [SUBMIT, "post", "multipart/form-data", ""]:
        raise ValueError("Official form destination, encoding or method changed")
    for field in ("from_index", "runtype", "referer", "Qemailaddress"):
        if form.locator(f'[name="{field}"]').input_value() != options[field]:
            raise ValueError(f"Unexpected official form field: {field}")
    for field in ("outputtype", "validtype", "valout", "duplic"):
        form.locator(f'input[name="{field}"][value="{options[field]}"]').check()
    button = form.locator('input[type=submit][name=UPLOAD]')
    if button.input_value() != options["UPLOAD"] or button.evaluate(
        "b => ['formaction','formmethod','formenctype','formtarget'].some(n => b.hasAttribute(n))"
    ):
        raise ValueError("Official submission control changed")
    form.locator('input[type=file][name=filecif]').set_input_files(
        {"name": "model.cif", "mimeType": "chemical/x-cif", "buffer": payload}
    )
    return button


def submit(payload, options, timeout, checkpoint, save_receipt):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install playwright in the Cairystal Python environment and configure a browser channel") from exc
    channel = os.environ.get("CAIRYSTAL_BROWSER_CHANNEL", "msedge" if os.name == "nt" else "chromium")
    if channel not in {"msedge", "chrome", "chromium"}:
        raise ValueError("Unsupported CAIRYSTAL_BROWSER_CHANNEL")
    with sync_playwright() as driver:
        browser = driver.chromium.launch(channel=channel, headless=False, chromium_sandbox=True)
        context = browser.new_context(service_workers="block")
        page = context.new_page()
        page.set_default_timeout(min(timeout, 30) * 1000)
        armed = False
        sent = False

        def guard(route):
            nonlocal sent
            req = route.request
            if req.method in {"GET", "HEAD"} and req.url.startswith(FORM):
                return route.continue_()
            if armed and not sent and req.method == "POST" and req.url == SUBMIT and req.is_navigation_request() and req.frame == page.main_frame:
                sent = True
                return route.continue_()
            return route.abort()

        context.route("**/*", guard)
        landing = page.goto(FORM, wait_until="domcontentloaded")
        if not landing or not landing.ok or page.url != FORM:
            raise RuntimeError("Official browser form unavailable; no file submitted")
        button = fill_form(page, payload, options)
        checkpoint("submitting", {"channel": channel, "version": browser.version})
        armed = True
        start = perf_counter()
        with page.expect_navigation(wait_until="domcontentloaded", timeout=timeout * 1000) as navigation:
            button.click(timeout=min(timeout, 30) * 1000, no_wait_after=True)
        result = navigation.value
        if not sent or not result or not result.ok or not page.url.startswith(FORM):
            raise RuntimeError(f"Browser submission has no successful IUCr receipt (HTTP {result.status if result else 'unknown'})")
        save_receipt(page.content(), page.url)
        checkpoint("receipt_saved", {"post_to_receipt_s": round(perf_counter() - start, 6)})
