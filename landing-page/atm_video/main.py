import os
import sys
import math
import wave
import unicodedata
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_BIN = "ffmpeg"

# ==============================================================================
# ١. إعدادات الفيديو والملفات
# ==============================================================================
W, H = 1080, 1920
FPS = 60

def find_file(candidates):
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"لم يتم العثور على أي من الملفات: {candidates}")

AUDIO_PATH = find_file(["4_6032710011694620435.mp3", "voice.mp3"])
FONT_PATH  = find_file(["Lifta-Black.otf.ttf", "Lifta-Black.otf", "font.ttf"])
LOGO_PATH  = find_file(["1000211478.jpg", "logo.jpg", "logo.png"])
OUTPUT_MP4 = "كيف_يبنى_الصراف_الآلي.mp4"
SFX_WAV    = "temp_sfx.wav"

# ==============================================================================
# ٢. دوال التحريك والمنحنيات (Easing Functions)
# ==============================================================================
def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))

def ease_out_back(t, s=1.70158):
    t = clamp(t)
    t -= 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0

def ease_in_out(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)

def pop_scale(t, start, dur=0.45):
    if t < start:
        return 0.0
    return ease_out_back((t - start) / dur)

def window_alpha(t, start, end, fade=0.35):
    if t < start or t > end:
        return 0.0
    if t < start + fade:
        return clamp((t - start) / fade)
    if t > end - fade:
        return clamp((end - t) / fade)
    return 1.0

def to_hindi_digits(text):
    trans = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
    return text.translate(trans)

# ==============================================================================
# ٣. استخراج أيقونة المكعب الشفافة من الشعار
# ==============================================================================
def prepare_watermark(logo_path, target_size=115, opacity=0.85):
    img = Image.open(logo_path).convert("RGBA")
    lw, lh = img.size
    crop_box = (int(lw * 0.22), int(lh * 0.14), int(lw * 0.78), int(lh * 0.68))
    cube = img.crop(crop_box)
    arr = np.array(cube, dtype=np.float32)

    bg = arr[0, 0, :3]
    dist = np.linalg.norm(arr[:, :, :3] - bg, axis=2)
    alpha = np.clip((dist - 18.0) / 35.0, 0.0, 1.0) * 255.0 * opacity
    arr[:, :, 3] = alpha

    clean_cube = Image.fromarray(arr.astype(np.uint8), "RGBA")
    bbox = clean_cube.getbbox()
    if bbox:
        clean_cube = clean_cube.crop(bbox)
    clean_cube.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
    return clean_cube

# ==============================================================================
# ٤. توليد المؤثرات الصوتية المتزامنة (Procedural SFX)
# ==============================================================================
def generate_sfx_track(duration_sec, filename=SFX_WAV, sr=44100):
    total_samples = int(duration_sec * sr)
    track = np.zeros(total_samples, dtype=np.float32)

    def add_tone(t0, dur, f1, f2=None, vol=0.2, wave_type="sine"):
        i0 = int(t0 * sr)
        n = int(dur * sr)
        if i0 + n > total_samples or n <= 0:
            return
        t = np.linspace(0, dur, n, endpoint=False)
        if f2 is None:
            phase = 2 * np.pi * f1 * t
        else:
            freqs = np.linspace(f1, f2, n)
            phase = 2 * np.pi * np.cumsum(freqs) / sr
        sig = np.sign(np.sin(phase)) if wave_type == "square" else np.sin(phase)
        env = np.exp(-3.5 * t / dur)
        track[i0:i0+n] += sig * env * vol

    def add_noise_burst(t0, dur, vol=0.18, decay=6.0):
        i0 = int(t0 * sr)
        n = int(dur * sr)
        if i0 + n > total_samples or n <= 0:
            return
        t = np.linspace(0, dur, n, endpoint=False)
        noise = np.random.uniform(-1.0, 1.0, n)
        env = np.exp(-decay * t / dur)
        track[i0:i0+n] += noise * env * vol

    add_noise_burst(0.4, 0.25, vol=0.22, decay=8.0)
    add_tone(0.5, 0.18, 140, 80, vol=0.25)
    add_tone(2.2, 0.15, 320, 520, vol=0.15)
    add_noise_burst(8.0, 0.45, vol=0.20, decay=4.0)
    add_tone(8.1, 0.35, 180, 90, vol=0.22)
    add_tone(12.0, 0.2, 220, 440, vol=0.18)
    add_tone(14.2, 0.35, 300, 600, vol=0.15)
    add_tone(17.0, 0.25, 480, 240, vol=0.18, wave_type="square")
    add_noise_burst(20.3, 0.4, vol=0.32, decay=5.0)
    add_tone(20.3, 0.4, 95, 45, vol=0.35)
    for k in range(3):
        add_tone(21.8 + k * 0.22, 0.12, 600, 1200, vol=0.16)
    add_noise_burst(29.5, 0.15, vol=0.15, decay=10.0)
    for k, freq in enumerate([697, 770, 852, 941]):
        add_tone(32.0 + k * 0.22, 0.12, freq, vol=0.18)
    add_tone(35.5, 0.3, 280, 190, vol=0.18, wave_type="square")
    for k in range(5):
        add_tone(40.2 + k * 0.12, 0.09, 880 + k * 140, vol=0.16)
    for k in range(8):
        add_tone(48.0 + k * 0.15, 0.08, 1100 + (k % 3) * 250, vol=0.12)
    add_tone(51.2, 0.15, 587, vol=0.20)
    add_tone(51.38, 0.25, 880, vol=0.22)
    add_tone(56.2, 0.22, 260, 520, vol=0.18)
    for k in range(6):
        add_noise_burst(58.8 + k * 0.25, 0.08, vol=0.16, decay=12.0)
    add_tone(64.2, 0.2, 1320, 1760, vol=0.16)
    add_tone(68.0, 0.15, 400, 220, vol=0.20, wave_type="square")
    add_noise_burst(68.2, 0.2, vol=0.18, decay=8.0)
    add_tone(74.5, 0.15, 987, vol=0.20)
    add_tone(74.7, 0.15, 987, vol=0.20)
    for k in range(5):
        add_noise_burst(77.2 + k * 0.15, 0.09, vol=0.18, decay=10.0)
    add_noise_burst(81.5, 0.3, vol=0.30, decay=6.0)
    add_noise_burst(83.0, 1.4, vol=0.24, decay=2.0)
    add_tone(86.5, 0.18, 440, 880, vol=0.18)
    add_tone(87.8, 0.18, 520, 1040, vol=0.18)
    for k, f in enumerate([523, 659, 784, 1046]):
        add_tone(89.2 + k * 0.16, 0.45, f, vol=0.22)

    track = np.clip(track, -0.95, 0.95)
    pcm = (track * 32767).astype(np.int16)
    with wave.open(filename, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

# ==============================================================================
# ٥. جدول الترجمة المتزامنة
# ==============================================================================
SUBTITLES = [
    (0.0,  2.2,  "لو فتحت *فتحة* في *جدار* *البنك*"),
    (2.2,  5.0,  "وحطيت وراها *موظف* يعطي الناس *فلوسهم*"),
    (5.0,  7.3,  "صار عندك *صراف* *آلي* *بدائي*"),
    (7.3,  11.0, "بس المشكلة إن *البنك* *يسكر* والموظف يروح بيته"),
    (11.0, 14.0, "عشان كذا تحط الفلوس في *صندوق* *ورا* *الفتحة*"),
    (14.0, 16.3, "و *آلة* تطلعها *لحالها*"),
    (16.3, 20.0, "لكن أي أحد يقدر *يمد* *يده* ويسحب *كل* *شيء*"),
    (20.0, 23.3, "فتقفل الفلوس داخل *خزنة* *فولاذية* مثبتة بالأرض"),
    (23.3, 26.2, "والآلة *تعد* *لك* اللي طلبته بس"),
    (26.2, 29.2, "بس كيف تعرف الآلة إنك *صاحب* *الحساب*؟"),
    (29.2, 32.2, "الحل؟ *بطاقة* *بلاستيك* فيها *شريط* *مغناطيسي*"),
    (32.2, 34.6, "و *رقم* *سري* ما يعرفه غيرك"),
    (34.6, 39.2, "لكن الحرامية ينسخون الشريط *بأجهزة* على *فتحة* *البطاقة*"),
    (39.2, 43.8, "فتضيف *شريحة* *صغيرة* تولد *رمز* *جديد* كل مرة"),
    (43.8, 45.6, "و *النسخة* ما تنفع"),
    (45.6, 48.0, "بس الآلة ما تدري كم عندك في *الحساب*"),
    (48.0, 50.4, "فترسل *طلبك* *مشفر* للبنك"),
    (50.4, 53.3, "والبنك يرد عليها: *وافق* أو *رفض*"),
    (53.3, 56.0, "لكن الفلوس كومة *أوراق* *مخلوطة*"),
    (56.0, 58.5, "عشان كذا كل فئة لها *درج* *خاص*"),
    (58.5, 61.2, "و *عجلات* *مطاط* تسحب *ورقة* *ورقة*"),
    (61.2, 64.2, "بس *ورقتين* *لاصقة* ببعض بتعطيك *ضعف* *المبلغ*"),
    (64.2, 67.2, "فتركب *حساس* يقيس *سماكة* كل ورقة"),
    (67.2, 70.6, "ولو أسمك من اللازم ترميها في *صندوق* *جانبي*"),
    (70.6, 74.2, "لكن الناس ياخذون فلوسهم وينسون *بطاقاتهم*"),
    (74.2, 77.2, "عشان كذا الآلة *ترجع* *لك* *البطاقة* *أول*"),
    (77.2, 79.3, "وبعدين *تطلع* *الفلوس*"),
    (79.3, 81.2, "وتدري وش *الغريب*؟"),
    (81.2, 86.3, "لو أحد حاول *يكسر* *الخزنة* ينرش *حبر* على كل الأوراق"),
    (86.3, 89.2, "باقي تركب *كاميرا* و *غطاء* فوق الأزرار"),
    (89.2, 92.5, "ومبروك عليك.. بنيت *صراف* *آلي* بنفسك"),
]

# ==============================================================================
# ٦. معالجة الخط العربي ومنع ظهور [NO GLYPH] نهائياً
# ==============================================================================
LAYOUT_BASIC = getattr(ImageFont.Layout, "BASIC", 0)
FONT_SUB   = ImageFont.truetype(FONT_PATH, 50, layout_engine=LAYOUT_BASIC)
FONT_SMALL = ImageFont.truetype(FONT_PATH, 30, layout_engine=LAYOUT_BASIC)

# إبقاء الحروف المنفصلة في نطاق Unicode الأساسي لأن Lifta-Black لا يدعم Presentation Forms المنفصلة
RESHAPER = arabic_reshaper.ArabicReshaper(
    configuration={
        "delete_harakat": True,
        "support_ligatures": True,
        "use_unshaped_instead_of_isolated": True,
    }
)

# بصمة مربع [NO GLYPH] في الخط لاكتشاف أي حرف غير مدعوم واستبداله فوراً
NOTDEF_MASK_BYTES = bytes(FONT_SUB.getmask("\uffff"))

FALLBACK_CHAR_MAP = {
    "آ": "ا", "أ": "ا", "إ": "ا", "ٱ": "ا",
    "ؤ": "و", "ئ": "ي", "ى": "ي", "ة": "ه",
}

def sanitize_glyphs(shaped_str, font=FONT_SUB):
    out = []
    for ch in shaped_str:
        if ch.isspace():
            out.append(ch)
            continue
        if bytes(font.getmask(ch)) == NOTDEF_MASK_BYTES:
            # ١. إرجاع الحرف إلى أصله الأساسي في Unicode (مثل \uFE8D -> \u0627)
            base_ch = unicodedata.normalize("NFKC", ch)
            if bytes(font.getmask(base_ch)) != NOTDEF_MASK_BYTES:
                out.append(base_ch)
                continue
            # ٢. تعويض الهمزات/المدات في حال عدم وجودها في الخط
            alt_ch = FALLBACK_CHAR_MAP.get(base_ch, base_ch)
            if bytes(font.getmask(alt_ch)) != NOTDEF_MASK_BYTES:
                out.append(alt_ch)
        else:
            out.append(ch)
    return "".join(out)

def shape_ar(word, font=FONT_SUB):
    word = to_hindi_digits(word)
    reshaped = RESHAPER.reshape(word)
    bidi_str = get_display(reshaped)
    return sanitize_glyphs(bidi_str, font=font)

def draw_arabic_subtitle(draw, t):
    active_text = None
    for s, e, txt in SUBTITLES:
        if s <= t < e:
            active_text = txt
            break
    if not active_text:
        return

    raw_words = active_text.split()
    if len(raw_words) > 5:
        mid = (len(raw_words) + 1) // 2
        lines = [raw_words[:mid], raw_words[mid:]]
    else:
        lines = [raw_words]

    base_y = int(H * 0.755)
    line_gap = 64

    for li, word_list in enumerate(lines):
        parsed = []
        total_w = 0
        space_w = 16
        for w in word_list:
            is_hi = w.startswith("*") and w.endswith("*") and len(w) > 2
            clean_w = w[1:-1] if is_hi else w
            shaped = shape_ar(clean_w, FONT_SUB)
            bbox = draw.textbbox((0, 0), shaped, font=FONT_SUB)
            ww = bbox[2] - bbox[0]
            parsed.append((shaped, ww, is_hi))
            total_w += ww
        total_w += space_w * max(0, len(parsed) - 1)

        curr_x = (W + total_w) // 2
        y = base_y + li * line_gap
        for shaped, ww, is_hi in parsed:
            curr_x -= ww
            fill_col = (242, 140, 40) if is_hi else (244, 245, 242)
            draw.text(
                (curr_x, y),
                shaped,
                font=FONT_SUB,
                fill=fill_col,
                stroke_width=5,
                stroke_fill=(17, 24, 32),
            )
            curr_x -= space_w

# ==============================================================================
# ٧. دوال رسم المجسمات والشخصيات (مع إصلاح اتجاه الذراع وحجم الشخصية)
# ==============================================================================
def draw_3d_box(draw, x, y, w, h, depth=14, top_col=(244,245,242), front_col=(210,215,220), side_col=(140,150,160), outline=(25,32,40)):
    if w <= 1 or h <= 1:
        return
    draw.rectangle([x, y, x + w, y + h], fill=front_col, outline=outline, width=3)
    top_pts = [(x, y), (x + depth, y - depth), (x + w + depth, y - depth), (x + w, y)]
    draw.polygon(top_pts, fill=top_col, outline=outline)
    side_pts = [(x + w, y), (x + w + depth, y - depth), (x + w + depth, y + h - depth), (x + w, y + h)]
    draw.polygon(side_pts, fill=side_col, outline=outline)

def draw_person(draw, cx, ground_y, shirt_col, facing=1, is_thief=False, arm_raise=0.0, holding_cash=False, alpha=1.0):
    """
    facing =  1 : يقف على اليسار ويمد يده يميناً (+x) نحو الجدار/الصراف
    facing = -1 : يقف على اليمين (الموظف) ويمد يده يساراً (-x) نحو فتحة الجدار
    """
    if alpha <= 0.02:
        return
    s = clamp(alpha)
    head_r = int(28 * s)
    body_w, body_h = int(52 * s), int(102 * s)
    leg_h = int(92 * s)

    # الأرجل
    draw.line([(cx - 12, ground_y - leg_h), (cx - 12, ground_y)], fill=(38, 48, 62), width=max(3, int(12 * s)))
    draw.line([(cx + 12, ground_y - leg_h), (cx + 12, ground_y)], fill=(38, 48, 62), width=max(3, int(12 * s)))

    # الجذع
    by = ground_y - leg_h - body_h
    draw.rounded_rectangle([cx - body_w // 2, by, cx + body_w // 2, ground_y - leg_h],
                           radius=12, fill=shirt_col, outline=(20, 28, 36), width=3)

    # الرأس والقبعة/القناع
    hy = by - head_r - 4
    draw.ellipse([cx - head_r, hy - head_r, cx + head_r, hy + head_r],
                 fill=(238, 202, 172), outline=(20, 28, 36), width=3)
    if is_thief:
        draw.rectangle([cx - head_r, hy - 8, cx + head_r, hy + 5], fill=(20, 24, 30))
    else:
        draw.pieslice([cx - head_r, hy - head_r, cx + head_r, hy + head_r],
                      start=180, end=360, fill=(105, 68, 42), outline=(20, 28, 36))

    # الذراع الممتدة باتجاه الجدار (حسب معامل facing)
    ax0 = cx + facing * int(10 * s)
    ay0 = by + int(22 * s)
    ax1 = ax0 + facing * int(64 * s * (0.45 + 0.55 * arm_raise))
    ay1 = ay0 - int(58 * s * arm_raise)
    draw.line([(ax0, ay0), (ax1, ay1)], fill=shirt_col, width=max(3, int(13 * s)))
    draw.ellipse([ax1 - 6, ay1 - 6, ax1 + 6, ay1 + 6], fill=(238, 202, 172), outline=(20, 28, 36), width=2)

    if holding_cash:
        bx0 = ax1 - 18 if facing < 0 else ax1
        draw.rectangle([bx0, ay1 - 10, bx0 + 36, ay1 + 8], fill=(72, 188, 112), outline=(25, 85, 45), width=2)

# ==============================================================================
# ٨. بناء اللوحة العالمية الموحدة (Master World Canvas) وحركة الكاميرا
# ==============================================================================
def get_camera(t):
    keyframes = [
        (0.0,  1.00, 540, 960),
        (5.0,  1.04, 520, 980),
        (11.0, 1.16, 535, 960),
        (20.0, 1.08, 575, 1020),
        (29.0, 1.22, 480, 920),
        (39.0, 1.22, 480, 920),
        (45.5, 1.00, 560, 960),
        (55.5, 1.20, 650, 1040),
        (70.5, 1.14, 500, 940),
        (80.5, 1.18, 650, 1040),
        (86.0, 1.00, 540, 960),
        (93.0, 1.00, 540, 960),
    ]
    for i in range(len(keyframes) - 1):
        t0, z0, x0, y0 = keyframes[i]
        t1, z1, x1, y1 = keyframes[i + 1]
        if t0 <= t <= t1:
            u = ease_in_out((t - t0) / max(0.001, t1 - t0))
            return (
                z0 + (z1 - z0) * u,
                x0 + (x1 - x0) * u,
                y0 + (y1 - y0) * u,
            )
    return 1.0, 540, 960

GROUND_Y = 1220
bg_arr = np.zeros((H, W, 3), dtype=np.uint8)

for y in range(GROUND_Y):
    r = int(185 + (235 - 185) * (y / GROUND_Y))
    g = int(212 + (238 - 212) * (y / GROUND_Y))
    b = int(230 + (242 - 230) * (y / GROUND_Y))
    bg_arr[y, :, :] = (r, g, b)

bg_arr[:GROUND_Y, 500:, 0] = 236
bg_arr[:GROUND_Y, 500:, 1] = 230
bg_arr[:GROUND_Y, 500:, 2] = 218

for y in range(GROUND_Y, H):
    u = (y - GROUND_Y) / (H - GROUND_Y)
    r = int(152 - 58 * u)
    g = int(122 - 50 * u)
    b = int(92  - 42 * u)
    bg_arr[y, :, :] = (r, g, b)

BASE_BG = Image.fromarray(bg_arr, "RGB")
bg_draw = ImageDraw.Draw(BASE_BG)
bg_draw.rectangle([0, GROUND_Y, 500, GROUND_Y + 28], fill=(175, 180, 185), outline=(90, 95, 100), width=2)
bg_draw.rectangle([500, GROUND_Y, W, GROUND_Y + 28], fill=(160, 145, 125), outline=(90, 80, 70), width=2)
bg_draw.line([(0, GROUND_Y + 180), (W, GROUND_Y + 180)], fill=(110, 85, 62), width=3)
bg_draw.line([(0, GROUND_Y + 380), (W, GROUND_Y + 380)], fill=(82, 62, 45), width=3)

def render_frame(t, watermark_img):
    canvas = BASE_BG.copy()
    draw = ImageDraw.Draw(canvas)

    # ١. الشمس والسحب المتحركة
    sun_x, sun_y = 140, 210
    draw.ellipse([sun_x - 52, sun_y - 52, sun_x + 52, sun_y + 52], fill=(252, 212, 92))
    for base_cx, cy, spd in [(120, 320, 14.0), (310, 430, 9.5)]:
        cx = int((base_cx + t * spd) % 440) - 40
        draw.rounded_rectangle([cx, cy, cx + 110, cy + 36], radius=18, fill=(248, 250, 252))
        draw.ellipse([cx + 22, cy - 18, cx + 76, cy + 28], fill=(248, 250, 252))

    # إظلام خارجي عند إغلاق البنك (00:07.3 -> 00:11.0)
    night_a = window_alpha(t, 7.3, 11.2, fade=0.6)
    if night_a > 0:
        overlay = Image.new("RGB", (500, GROUND_Y), (22, 42, 82))
        left_crop = canvas.crop((0, 0, 500, GROUND_Y))
        blended = Image.blend(left_crop, overlay, night_a * 0.72)
        canvas.paste(blended, (0, 0))
        draw = ImageDraw.Draw(canvas)

    # ٢. واجهة مبنى البنك اليسرى (مع وضع نص "البنك" وأيقونة المبنى في مكان آمن من القطع)
    draw_3d_box(draw, 0, 520, 185, GROUND_Y - 520, depth=12,
                top_col=(215, 222, 228), front_col=(190, 198, 206), side_col=(155, 165, 175))
    # أيقونة مبنى البنك الصغيرة بجوار كلمة البنك
    draw.rectangle([135, 442, 172, 495], fill=(120, 185, 210), outline=(25, 35, 45), width=2)
    for wy in range(450, 488, 12):
        draw.rectangle([143, wy, 151, wy + 7], fill=(240, 248, 255))
        draw.rectangle([156, wy, 164, wy + 7], fill=(240, 248, 255))
    lbl_bank = shape_ar("البنك", FONT_SUB)
    draw.text((22, 438), lbl_bank, font=FONT_SUB, fill=(30, 42, 56))

    # الجدار المقطعي المركزي (x = 475..525)
    wall_x, wall_w = 475, 50
    for by in range(120, GROUND_Y, 48):
        draw_3d_box(draw, wall_x, by, wall_w, 46, depth=10,
                    top_col=(238, 228, 210), front_col=(222, 210, 190), side_col=(185, 172, 152))

    # ٣. فتحة الجدار في المستوى الصحيح لمحاذاة يد الموظف والعميل (y = 920..1035)
    slot_s = pop_scale(t, 0.3)
    slot_y, slot_h = 920, int(115 * slot_s)
    if slot_s > 0:
        draw.rectangle([wall_x - 2, slot_y, wall_x + wall_w + 10, slot_y + slot_h], fill=(24, 28, 34))

    # ٤. الموظف البشري المؤقت خلف الجدار يمد يده يساراً (facing = -1) نحو الفتحة (00:02.0 -> 00:09.2)
    emp_a = window_alpha(t, 2.0, 9.2, fade=0.45)
    if emp_a > 0:
        walk_away = clamp((t - 8.0) / 1.2)
        emp_x = 582 + int(190 * walk_away)
        emp_facing = 1 if t >= 8.0 else -1
        arm_up = 0.65 + 0.35 * math.sin(t * 5.0) if t < 7.3 else 0.0
        draw_person(draw, emp_x, GROUND_Y, shirt_col=(108, 168, 92),
                    facing=emp_facing, arm_raise=arm_up, holding_cash=(t < 7.0), alpha=emp_a)

    # ٥. الصندوق الخشبي الأولي خلف الفتحة (00:11.2 -> 00:20.3)
    box_a = window_alpha(t, 11.2, 20.3, fade=0.35)
    if box_a > 0:
        bs = pop_scale(t, 11.2) * box_a
        bw, bh = int(175 * bs), int(125 * bs)
        draw_3d_box(draw, wall_x + wall_w + 4, slot_y - 5, bw, bh, depth=12,
                    top_col=(185, 125, 78), front_col=(156, 98, 54), side_col=(120, 72, 38))
        if bw > 60:
            for k in range(4):
                ny = slot_y + 22 + k * 18
                draw.rectangle([wall_x + wall_w + 28, ny, wall_x + wall_w + 135, ny + 14],
                               fill=(72, 188, 112), outline=(28, 96, 52), width=2)

    # ٦. اللص المؤقت يمد يده يميناً (facing = 1) داخل الفتحة (00:16.4 -> 00:20.2)
    thief1_a = window_alpha(t, 16.4, 20.2, fade=0.35)
    if thief1_a > 0:
        draw_person(draw, 412, GROUND_Y, shirt_col=(48, 52, 60),
                    facing=1, is_thief=True, arm_raise=0.95, holding_cash=True, alpha=thief1_a)

    # ٧. الخزنة الفولاذية المثبتة بالأرض متصلة بالفتحة (تظهر منذ 00:20.2 وتبقى للنهاية)
    vault_s = pop_scale(t, 20.2)
    vx, vy, vw, vh = 535, 925, int(330 * vault_s), int(295 * vault_s)
    if vault_s > 0:
        bolt_h = int(75 * clamp((t - 21.5) / 0.45))
        if bolt_h > 0:
            for bx in [vx + 35, vx + vw - 45]:
                draw.rectangle([bx, GROUND_Y, bx + 18, GROUND_Y + bolt_h],
                               fill=(242, 140, 40), outline=(20, 28, 36), width=2)

        shake_x = int(7 * math.sin(t * 45)) if 81.2 <= t <= 82.8 else 0
        draw_3d_box(draw, vx + shake_x, vy, vw, vh, depth=18,
                    top_col=(145, 155, 165), front_col=(102, 114, 125), side_col=(72, 82, 92))
        if vw > 60 and vh > 60:
            draw.rectangle([vx + 22 + shake_x, vy + 22, vx + vw - 22 + shake_x, vy + vh - 22],
                           fill=(42, 48, 56), outline=(24, 28, 34), width=3)

    # ٨. واجهة الصراف الآلي الأمامية المتصلة بالفتحة (تظهر منذ 00:23.0 وتبقى للنهاية)
    panel_s = pop_scale(t, 23.0)
    px, py, pw, ph = 427, 650, int(48 * panel_s), int(410 * panel_s)
    if panel_s > 0:
        draw_3d_box(draw, px, py, pw, ph, depth=10,
                    top_col=(110, 122, 134), front_col=(70, 80, 92), side_col=(50, 58, 68))
        if ph > 150:
            draw.rectangle([px + 8, py + 20, px + pw - 8, py + 150], fill=(115, 198, 248), outline=(25, 35, 45), width=2)
            for ky in range(py + 170, py + 255, 26):
                draw.rectangle([px + 10, ky, px + pw - 10, ky + 18], fill=(215, 220, 226), outline=(40, 45, 52), width=1)
            draw.rectangle([px + 6, py + 280, px + pw - 6, py + 302], fill=(242, 190, 55), outline=(30, 35, 40), width=2)
            draw.rectangle([px + 6, py + 335, px + pw - 6, py + 365], fill=(28, 34, 42), outline=(200, 205, 210), width=2)

    # ٩. العميل والبطاقة البلاستيكية والرقم السري والشريحة الذكية (منذ 00:22.5)
    if t >= 22.5:
        cust_arm = 0.85 if (25.0 <= t <= 38.0 or 74.0 <= t <= 79.0) else 0.25
        draw_person(draw, 355, GROUND_Y, shirt_col=(48, 128, 215), facing=1, arm_raise=cust_arm, alpha=1.0)

    if t >= 29.2:
        card_out = 0
        if 74.2 <= t <= 77.2:
            card_out = int(28 * math.sin((t - 74.2) * 6.0))
        draw.rounded_rectangle([px - 56 - card_out, py + 282, px + 12, py + 304], radius=4,
                               fill=(36, 102, 210), outline=(15, 22, 32), width=2)
        draw.rectangle([px - 54 - card_out, py + 292, px + 10, py + 298], fill=(20, 24, 30))
        if t >= 39.5:
            draw.rectangle([px - 42 - card_out, py + 285, px - 28 - card_out, py + 293], fill=(242, 185, 45))

    # جهاز نسخ الشريط المغناطيسي المؤقت (Skimmer: 00:34.6 -> 00:40.0)
    skim_a = window_alpha(t, 34.6, 40.0, fade=0.3)
    if skim_a > 0:
        draw_person(draw, 310, GROUND_Y, shirt_col=(42, 46, 54), facing=1, is_thief=True, arm_raise=0.8, alpha=skim_a)
        draw.rectangle([px - 18, py + 275, px + 16, py + 308], fill=(225, 58, 52), outline=(25, 25, 25), width=2)

    # ١٠. عدسة التكبير المدمجة: البطاقة والرقم السري والشريحة الذكية (00:29.2 -> 00:45.4)
    lens1_a = window_alpha(t, 29.2, 45.4, fade=0.35)
    if lens1_a > 0:
        lx, ly, lr = 240, 680, int(135 * lens1_a)
        draw.line([(px - 20, py + 290), (lx + lr // 2, ly + lr // 2)], fill=(242, 140, 40), width=4)
        draw.ellipse([lx - lr, ly - lr, lx + lr, ly + lr], fill=(28, 36, 48), outline=(242, 140, 40), width=6)
        if lr > 80:
            draw.rounded_rectangle([lx - 92, ly - 55, lx + 92, ly + 45], radius=12,
                                   fill=(42, 112, 222), outline=(244, 245, 242), width=3)
            draw.rectangle([lx - 90, ly - 35, lx + 90, ly - 12], fill=(20, 24, 30))
            if t >= 39.2:
                cs = pop_scale(t, 39.2)
                cw = int(38 * cs)
                draw.rounded_rectangle([lx - 68, ly + 2, lx - 68 + cw, ly + 30], radius=5,
                                       fill=(242, 185, 45), outline=(25, 30, 35), width=2)
                code_idx = int((t - 39.2) * 2.5) % 3
                codes = ["رمز ١٤٩", "رمز ٨٣٢", "رمز ٥٠٧"]
                draw.text((lx - 15, ly + 2), shape_ar(codes[code_idx], FONT_SMALL), font=FONT_SMALL, fill=(242, 185, 45))
            elif t >= 32.0:
                n_stars = min(4, int((t - 32.0) * 3.5) + 1)
                for si in range(n_stars):
                    sx = lx - 55 + si * 34
                    draw.ellipse([sx, ly + 8, sx + 18, ly + 26], fill=(242, 185, 45))

    # ١١. الكابل المشفر وخادم البنك المركزي (00:46.0+)
    srv_s = pop_scale(t, 46.0)
    if srv_s > 0:
        sx, sy, sw, sh = 875, 580, int(155 * srv_s), int(115 * srv_s)
        draw_3d_box(draw, sx, sy, sw, sh, depth=12,
                    top_col=(85, 115, 165), front_col=(45, 72, 122), side_col=(32, 52, 92))
        if sw > 70:
            draw.rounded_rectangle([sx + 16, sy + 16, sx + sw - 16, sy + sh - 16], radius=8,
                                   fill=(225, 238, 252), outline=(25, 35, 50), width=2)
            pts = []
            for u in np.linspace(0, 1, 18):
                cx_p = int((px + pw) * (1 - u) + sx * u)
                cy_p = int((py + 120) * (1 - u) + (sy + 50) * u - 130 * math.sin(math.pi * u))
                pts.append((cx_p, cy_p))
            for i in range(0, len(pts) - 1, 2):
                draw.line([pts[i], pts[i + 1]], fill=(242, 140, 40), width=4)
            if 47.5 <= t <= 53.5:
                u_pkt = (t - 47.5) / 2.8
                u_pkt = u_pkt if u_pkt <= 1.0 else max(0.0, 2.0 - u_pkt)
                idx = min(len(pts) - 1, int(u_pkt * (len(pts) - 1)))
                px_k, py_k = pts[idx]
                draw.rectangle([px_k - 14, py_k - 12, px_k + 14, py_k + 12],
                               fill=(242, 185, 45), outline=(20, 25, 30), width=2)
            if t >= 50.8:
                draw.line([(sx + 52, sy + 58), (sx + 72, sy + 78), (sx + 108, sy + 38)], fill=(42, 168, 92), width=6)

    # ١٢. داخل الخزنة: كومة مختلطة ثم ٣ أدراج وعجلات مطاط وحساس السماكة وصندوق الرفض
    if 45.0 <= t < 56.0 and vault_s > 0.8:
        rng = np.random.RandomState(42)
        for k in range(14):
            bx = vx + 45 + rng.randint(0, 190)
            by = vy + 140 + rng.randint(0, 100)
            draw.rectangle([bx, by, bx + 68, by + 30], fill=(72, 188, 112), outline=(28, 96, 52), width=2)

    if t >= 56.0 and vault_s > 0.8:
        drawer_s = pop_scale(t, 56.0)
        cols = [(72, 188, 112), (235, 185, 58), (82, 152, 228)]
        for di in range(3):
            dx = vx + 40 + di * 86
            dy = vy + 105
            dw, dh = 72, int(165 * drawer_s)
            draw.rounded_rectangle([dx, dy, dx + dw, dy + dh], radius=6,
                                   fill=(68, 76, 86), outline=(22, 28, 34), width=3)
            for bi in range(8):
                by = dy + dh - 18 - bi * 15
                if by > dy + 26:
                    draw.rectangle([dx + 10, by, dx + dw - 10, by + 10], fill=cols[di], outline=(30, 35, 40), width=1)
            if t >= 58.5:
                rcx, rcy = dx + dw // 2, dy + 15
                draw.ellipse([rcx - 13, rcy - 13, rcx + 13, rcy + 13], fill=(35, 40, 46), outline=(200, 205, 210), width=2)
                ang = t * 12.0
                draw.line([(rcx, rcy), (rcx + int(10 * math.cos(ang)), rcy + int(10 * math.sin(ang)))],
                          fill=(242, 140, 40), width=3)

        if t >= 58.8:
            for k in range(3):
                prog = ((t * 1.6 + k * 0.33) % 1.0)
                bx = int((vx + 65) * (1 - prog) + (vx + 150) * prog)
                by = int((vy + 95) * (1 - prog) + (vy + 38) * prog)
                draw.rectangle([bx, by, bx + 62, by + 26], fill=(72, 188, 112), outline=(25, 85, 45), width=2)
                if 61.2 <= t <= 70.0 and k == 0:
                    draw.rectangle([bx + 5, by - 6, bx + 67, by + 20], fill=(72, 188, 112), outline=(220, 55, 45), width=2)

        if t >= 64.2:
            ss = pop_scale(t, 64.2)
            sx_s, sy_s = vx + 145, vy + 52
            draw.rounded_rectangle([sx_s, sy_s, sx_s + int(76 * ss), sy_s + 24], radius=6,
                                   fill=(235, 175, 45), outline=(25, 30, 35), width=2)
            led_col = (225, 52, 48) if (64.5 <= t <= 70.2 and int(t * 6) % 2 == 0) else (45, 195, 95)
            draw.ellipse([sx_s + 10, sy_s + 5, sx_s + 24, sy_s + 19], fill=led_col)

        if t >= 67.0:
            rs = pop_scale(t, 67.0)
            rx_b, ry_b = vx + 242, vy + 36
            draw.rounded_rectangle([rx_b, ry_b, rx_b + int(58 * rs), ry_b + int(58 * rs)], radius=6,
                                   fill=(198, 52, 48), outline=(25, 30, 35), width=2)

    # ١٣. ترتيب الإخراج: (١) البطاقة أولاً ثم (٢) النقود (01:13.8 -> 01:19.5)
    seq_a = window_alpha(t, 73.8, 79.5, fade=0.35)
    if seq_a > 0:
        for num_txt, badge_y in [("١", 745), ("٢", 835)]:
            draw.ellipse([235, badge_y - 32, 299, badge_y + 32], fill=(52, 168, 92), outline=(244, 245, 242), width=3)
            draw.text((256, badge_y - 26), shape_ar(num_txt, FONT_SUB), font=FONT_SUB, fill=(244, 245, 242))

    # ١٤. نظام رش الحبر الأمني عند محاولة كسر الخزنة (01:21.2+)
    if t >= 81.2 and vault_s > 0.8:
        ink_prog = clamp((t - 82.2) / 1.5)
        if ink_prog > 0:
            draw.line([(vx + 45, vy + 32), (vx + vw - 45, vy + 32)], fill=(55, 65, 210), width=6)
            rng_ink = np.random.RandomState(99)
            n_blobs = int(18 * ink_prog)
            for _ in range(n_blobs):
                ix = vx + 52 + rng_ink.randint(0, 220)
                iy = vy + 105 + rng_ink.randint(0, 150)
                ir = rng_ink.randint(12, 20)
                draw.ellipse([ix - ir, iy - ir, ix + ir, iy + ir], fill=(48, 58, 225))

    # ١٥. تركيب الكاميرا الأمنية وغطاء حماية الأزرار (01:26.3+)
    if t >= 86.3:
        cam_s = pop_scale(t, 86.3)
        draw.ellipse([px - 10, py - 24, px + int(28 * cam_s), py + 8], fill=(35, 42, 50), outline=(244, 245, 242), width=2)
        draw.ellipse([px - 2, py - 14, px + 10, py - 2], fill=(225, 52, 48))
        sh_s = pop_scale(t, 87.4)
        if sh_s > 0:
            draw.polygon([(px - 18, py + 165), (px + 12, py + 150), (px + 12, py + 250), (px - 18, py + 240)],
                         fill=(155, 165, 175), outline=(25, 32, 40))

    # ١٦. الاحتفال الختامي في اللقطة الشاملة (01:29.0+)
    if t >= 89.0:
        rng_c = np.random.RandomState(123)
        conf_cols = [(242, 140, 40), (52, 168, 92), (62, 142, 228), (228, 68, 62)]
        for ci in range(45):
            cx_c = rng_c.randint(60, W - 60)
            cy_c = int((rng_c.randint(0, 900) + (t - 89.0) * rng_c.randint(180, 340)) % (GROUND_Y - 40))
            ccol = conf_cols[ci % len(conf_cols)]
            draw.rectangle([cx_c, cy_c, cx_c + 14, cy_c + 9], fill=ccol)

    # تقريب وتحريك الكاميرا السلس
    zoom, fx, fy = get_camera(t)
    if abs(zoom - 1.0) > 0.003:
        cw, ch = int(W / zoom), int(H / zoom)
        x0 = int(clamp(fx - cw / 2, 0, W - cw))
        y0 = int(clamp(fy - ch / 2, 0, H - ch))
        canvas = canvas.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.Resampling.BILINEAR)

    # ١٧. رسم الترجمة المتزامنة العائمة والعلامة المائية الشفافة
    draw_final = ImageDraw.Draw(canvas)
    draw_arabic_subtitle(draw_final, t)

    wm_x = (W - watermark_img.width) // 2
    wm_y = int(H * 0.865)
    canvas.paste(watermark_img, (wm_x, wm_y), watermark_img)

    return canvas

# ==============================================================================
# ٩. التشغيل الرئيسي والدمج عبر FFmpeg
# ==============================================================================
def get_audio_duration(audio_path):
    cmd = [FFMPEG_BIN, "-i", audio_path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            timestr = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = timestr.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 92.04

def main():
    print("١/٤ جاري استخراج العلامة المائية الشفافة من الشعار...")
    watermark = prepare_watermark(LOGO_PATH, target_size=115, opacity=0.85)

    duration = get_audio_duration(AUDIO_PATH)
    total_frames = int(math.ceil(duration * FPS))
    print(f"٢/٤ مدة التسجيل الصوتي: {duration:.2f} ثانية ({total_frames} إطار بمعدل {FPS}fps)")

    print("٣/٤ جاري توليد المؤثرات الصوتية المتزامنة...")
    generate_sfx_track(duration, SFX_WAV)

    print("٤/٤ جاري رندرة الفيديو ودمج الصوت والمؤثرات...")
    ffmpeg_cmd = [
        FFMPEG_BIN, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",
        "-i", AUDIO_PATH,
        "-i", SFX_WAV,
        "-filter_complex",
        "[1:a]volume=1.0[vo];[2:a]volume=0.32[sfx];[vo][sfx]amix=inputs=2:duration=first:dropout_transition=0[aout]",
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_MP4,
    ]

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    for f in range(total_frames):
        t = f / FPS
        frame_img = render_frame(t, watermark)
        proc.stdin.write(frame_img.tobytes())
        if f % (FPS * 5) == 0 or f == total_frames - 1:
            pct = (f + 1) * 100.0 / total_frames
            print(f"   تم إنجاز: {pct:5.1f}% ({t:5.1f}s / {duration:.1f}s)", end="\r")

    proc.stdin.close()
    proc.wait()

    if os.path.exists(SFX_WAV):
        os.remove(SFX_WAV)
    print(f"\nتم إنشاء الفيديو بنجاح: {os.path.abspath(OUTPUT_MP4)}")

if __name__ == "__main__":
    main()