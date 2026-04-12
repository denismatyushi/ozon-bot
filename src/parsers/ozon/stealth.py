"""Environment stealth for Playwright — WebGL/Canvas/Audio/Battery/Sensors + Client Hints."""

# Comprehensive stealth script applied via add_init_script BEFORE any page JS runs.
# Covers points #2 (environment stealth), #5 (client hints via userAgentData),
# #12 (sensor data: battery, device motion/orientation).
STEALTH_JS = r"""
(() => {
  // --- webdriver ---
  try { Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false }); } catch(e) {}
  try { delete Object.getPrototypeOf(navigator).webdriver; } catch(e) {}

  // --- plugins & mimeTypes ---
  try {
    Object.defineProperty(navigator, 'plugins', {
      get: () => {
        const arr = [
          { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
          { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
          { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
          { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
          { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: '' },
        ];
        arr.__proto__ = PluginArray.prototype;
        return arr;
      }
    });
  } catch(e) {}
  try {
    Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
  } catch(e) {}

  // --- hardware / memory ---
  try { Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch(e) {}
  try { Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 }); } catch(e) {}
  try { Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 }); } catch(e) {}

  // --- permissions shim ---
  try {
    const origQuery = navigator.permissions && navigator.permissions.query;
    if (origQuery) {
      navigator.permissions.query = (p) =>
        p && p.name === 'notifications'
          ? Promise.resolve({ state: Notification.permission, onchange: null })
          : origQuery.call(navigator.permissions, p);
    }
  } catch(e) {}

  // --- Client Hints (Sec-CH-UA via navigator.userAgentData) ---
  try {
    const uaData = {
      brands: [
        { brand: 'Chromium', version: '124' },
        { brand: 'Google Chrome', version: '124' },
        { brand: 'Not-A.Brand', version: '99' }
      ],
      mobile: false,
      platform: 'Windows',
      getHighEntropyValues: (hints) => Promise.resolve({
        brands: [
          { brand: 'Chromium', version: '124' },
          { brand: 'Google Chrome', version: '124' },
          { brand: 'Not-A.Brand', version: '99' }
        ],
        fullVersionList: [
          { brand: 'Chromium', version: '124.0.6367.119' },
          { brand: 'Google Chrome', version: '124.0.6367.119' },
          { brand: 'Not-A.Brand', version: '99.0.0.0' }
        ],
        mobile: false,
        platform: 'Windows',
        platformVersion: '15.0.0',
        architecture: 'x86',
        bitness: '64',
        model: '',
        uaFullVersion: '124.0.6367.119',
        wow64: false
      }),
      toJSON: function() { return { brands: this.brands, mobile: this.mobile, platform: this.platform }; }
    };
    Object.defineProperty(navigator, 'userAgentData', { get: () => uaData });
  } catch(e) {}

  // --- WebGL vendor/renderer spoof ---
  try {
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
      if (p === 37445) return 'Google Inc. (Intel)';
      if (p === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)';
      return getParameter.call(this, p);
    };
    if (window.WebGL2RenderingContext) {
      const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
      WebGL2RenderingContext.prototype.getParameter = function(p) {
        if (p === 37445) return 'Google Inc. (Intel)';
        if (p === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        return getParameter2.call(this, p);
      };
    }
  } catch(e) {}

  // --- Canvas noise ---
  try {
    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...a) {
      try {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
          const shift = { r: Math.floor(Math.random()*3)-1, g: Math.floor(Math.random()*3)-1, b: Math.floor(Math.random()*3)-1 };
          const img = ctx.getImageData(0, 0, this.width, this.height);
          for (let i = 0; i < img.data.length; i += 4) {
            img.data[i]   = Math.min(255, Math.max(0, img.data[i]   + shift.r));
            img.data[i+1] = Math.min(255, Math.max(0, img.data[i+1] + shift.g));
            img.data[i+2] = Math.min(255, Math.max(0, img.data[i+2] + shift.b));
          }
          ctx.putImageData(img, 0, 0);
        }
      } catch(e) {}
      return toDataURL.apply(this, a);
    };
  } catch(e) {}

  // --- AudioContext fingerprint tweak ---
  try {
    const origGetChannel = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function() {
      const res = origGetChannel.apply(this, arguments);
      if (res && res.length) {
        for (let i = 0; i < res.length; i += 500) {
          res[i] = res[i] + (Math.random() - 0.5) * 1e-7;
        }
      }
      return res;
    };
  } catch(e) {}

  // --- Battery API ---
  try {
    navigator.getBattery = () => Promise.resolve({
      charging: true,
      chargingTime: Infinity,
      dischargingTime: Infinity,
      level: 0.87,
      addEventListener: () => {},
      removeEventListener: () => {},
      onchargingchange: null,
      onchargingtimechange: null,
      ondischargingtimechange: null,
      onlevelchange: null
    });
  } catch(e) {}

  // --- DeviceMotion / DeviceOrientation live events ---
  try {
    const fire = (name, evt) => {
      try { window.dispatchEvent(new (name === 'devicemotion' ? DeviceMotionEvent : DeviceOrientationEvent)(name, evt)); } catch(e) {}
    };
    setInterval(() => {
      const t = Date.now() / 1000;
      fire('devicemotion', {
        acceleration: { x: Math.sin(t)*0.02, y: Math.cos(t)*0.02, z: 0.01 },
        accelerationIncludingGravity: { x: Math.sin(t)*0.02, y: Math.cos(t)*0.02 - 9.8, z: 0.01 },
        rotationRate: { alpha: Math.sin(t)*0.1, beta: Math.cos(t)*0.1, gamma: 0 },
        interval: 16
      });
      fire('deviceorientation', {
        alpha: (Math.sin(t)*2 + 180) % 360,
        beta:  Math.cos(t)*1.5,
        gamma: Math.sin(t*0.5)*1.0,
        absolute: false
      });
    }, 250);
  } catch(e) {}

  // --- chrome runtime object ---
  try { window.chrome = window.chrome || { runtime: {}, app: { isInstalled: false }, csi: () => ({}), loadTimes: () => ({}) }; } catch(e) {}

  // --- iframe contentWindow guard ---
  try {
    const getContent = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
      get: function() {
        const w = getContent.get.call(this);
        try { Object.defineProperty(w, 'webdriver', { get: () => false }); } catch(e) {}
        return w;
      }
    });
  } catch(e) {}
})();
"""


# Chrome 124 Windows x64 — strictly ordered client hints for point #5.
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Ordered exactly as Chrome emits them.
CLIENT_HINTS_HEADERS = {
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"15.0.0"',
    "sec-ch-ua-arch": '"x86"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-full-version-list": (
        '"Chromium";v="124.0.6367.119", '
        '"Google Chrome";v="124.0.6367.119", '
        '"Not-A.Brand";v="99.0.0.0"'
    ),
    "sec-fetch-site": "none",
    "sec-fetch-mode": "navigate",
    "sec-fetch-user": "?1",
    "sec-fetch-dest": "document",
    "upgrade-insecure-requests": "1",
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def build_context_kwargs(locale: str = "ru-RU", timezone: str = "Europe/Moscow") -> dict:
    """Build Playwright browser_context kwargs with stealth defaults."""
    return {
        "user_agent": CHROME_UA,
        "locale": locale,
        "timezone_id": timezone,
        "viewport": {"width": 1536, "height": 864},
        "screen": {"width": 1920, "height": 1080},
        "device_scale_factor": 1.0,
        "is_mobile": False,
        "has_touch": False,
        "color_scheme": "light",
        "reduced_motion": "no-preference",
        "extra_http_headers": dict(CLIENT_HINTS_HEADERS),
        "permissions": ["geolocation"],
        "geolocation": {"latitude": 55.7558, "longitude": 37.6173, "accuracy": 40},
        "java_script_enabled": True,
        "bypass_csp": True,
        "ignore_https_errors": True,
    }
