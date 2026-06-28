import webview

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

NETFLIX_URL = "https://www.netflix.com"
APP_TITLE = "Netflix"

KEYRING_SERVICE = "netflix_app_pywebview"
KEYRING_USERNAME_KEY = "saved_username"
KEYRING_PASSWORD_KEY_PREFIX = "pwd_for_"

class Api:

    def __init__(self):
        self._window = None
        self._is_fullscreen = False

    def attach_window(self, window):
        self._window = window

    def set_fullscreen(self, fullscreen):
        if self._window is None:
            return {"ok": False}
        fullscreen = bool(fullscreen)
        if fullscreen != self._is_fullscreen:
            self._window.toggle_fullscreen()
            self._is_fullscreen = fullscreen
        return {"ok": True}

    def save_credentials(self, email, password):
        if not email or not password:
            return {"ok": False, "error": "champs vides"}

        if not KEYRING_AVAILABLE:
            print(
                "[!] La librairie 'keyring' n'est pas installée : "
                "(pip install keyring)"
            )
            return {"ok": False, "error": "keyring manquant"}

        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, email)
        keyring.set_password(
            KEYRING_SERVICE, KEYRING_PASSWORD_KEY_PREFIX + email, password
        )
        
        return {"ok": True}

    def get_credentials(self):
        if not KEYRING_AVAILABLE:
            return {"email": None, "password": None}

        email = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
        if not email:
            return {"email": None, "password": None}

        password = keyring.get_password(
            KEYRING_SERVICE, KEYRING_PASSWORD_KEY_PREFIX + email
        )
        return {"email": email, "password": password}

    def clear_credentials(self):
        if not KEYRING_AVAILABLE:
            return {"ok": False}
        email = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
        if email:
            try:
                keyring.delete_password(
                    KEYRING_SERVICE, KEYRING_PASSWORD_KEY_PREFIX + email
                )
            except keyring.errors.PasswordDeleteError:
                pass
            try:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
            except keyring.errors.PasswordDeleteError:
                pass
        return {"ok": True}


INJECTED_JS = r"""
(function () {
    if (window.__netflixAppHooked) return;
    window.__netflixAppHooked = true;

    const EMAIL_SELECTORS = [
        'input[name="userLoginId"]',
        'input[type="email"]',
        'input[autocomplete="email"]',
        'input[id*="email" i]'
    ];
    const PASSWORD_SELECTORS = [
        'input[name="password"]',
        'input[type="password"]',
        'input[autocomplete="current-password"]'
    ];

    function findField(selectors) {
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) return el;
        }
        return null;
    }

    function setNativeValue(el, value) {
        const proto = Object.getPrototypeOf(el);
        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        setter.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    async function tryAutofillAndHook() {
        const emailField = findField(EMAIL_SELECTORS);
        const passwordField = findField(PASSWORD_SELECTORS);
        if (!emailField || !passwordField) return false;
        if (emailField.__netflixAppDone) return true;
        emailField.__netflixAppDone = true;

        try {
            const creds = await window.pywebview.api.get_credentials();
            if (creds && creds.email && creds.password) {
                setNativeValue(emailField, creds.email);
                setNativeValue(passwordField, creds.password);
            }
        } catch (e) {
            console.warn("netflix_app: impossible de lire les identifiants", e);
        }

        const form = emailField.closest('form') || document.body;
        form.addEventListener('submit', () => {
            const email = emailField.value;
            const password = passwordField.value;
            if (email && password) {
                window.pywebview.api.save_credentials(email, password);
            }
        }, true);

        const submitBtn = document.querySelector('button[type="submit"], [data-uia*="login" i]');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => {
                const email = emailField.value;
                const password = passwordField.value;
                if (email && password) {
                    window.pywebview.api.save_credentials(email, password);
                }
            }, true);
        }

        return true;
    }

    const interval = setInterval(async () => {
        const done = await tryAutofillAndHook();
        if (done) clearInterval(interval);
    }, 500);

    setTimeout(() => clearInterval(interval), 30000);

    function isPageFullscreen() {
        return !!(document.fullscreenElement || document.webkitFullscreenElement);
    }

    function notifyFullscreen() {
        try {
            window.pywebview.api.set_fullscreen(isPageFullscreen());
        } catch (e) {
            console.warn("netflix_app: set_fullscreen a échoué", e);
        }
    }

    if (!window.__netflixAppFullscreenHooked) {
        window.__netflixAppFullscreenHooked = true;
        document.addEventListener('fullscreenchange', notifyFullscreen);
        document.addEventListener('webkitfullscreenchange', notifyFullscreen);
    }
})();
"""


def on_loaded(window):
    window.evaluate_js(INJECTED_JS)


def main():
    api = Api()
    window = webview.create_window(
        title=APP_TITLE,
        url=NETFLIX_URL,
        width=1280,
        height=800,
        min_size=(900, 600),
        resizable=True,
        confirm_close=False,
        js_api=api,
    )
    api.attach_window(window)

    window.events.loaded += lambda: on_loaded(window)

    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
