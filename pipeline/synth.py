"""
synth.py - Custom instrument / sample renderer.

Renders original, non-stock instruments directly to WAV so LMMS can play them
as real samples: supersaws, trance leads, FM plucks, reese basses, 808 subs,
hoovers, vocal chops and DJ FX. Everything is synthesised from scratch - no
stock LMMS or plugin sounds are used for these.
"""
from __future__ import annotations

import os

import numpy as np

SR = 44100
from config_paths import ROOT
OUT = os.path.join(ROOT, "samples", "custom")


# --------------------------------------------------------------- utilities --
def _n(seconds: float, sr: int = SR) -> int:
    return max(1, int(round(seconds * sr)))


def _t(n: int, sr: int = SR) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / sr


def adsr(n: int, a=0.005, d=0.08, s=0.7, r=0.12, sr: int = SR) -> np.ndarray:
    """Classic ADSR envelope of length n."""
    an, dn, rn = int(a * sr), int(d * sr), int(r * sr)
    an = max(1, an)
    dn = max(0, dn)
    rn = max(0, min(rn, n - an - dn))
    body = max(0, n - an - dn - rn)
    env = np.concatenate([
        np.linspace(0.0, 1.0, an, endpoint=False),
        np.linspace(1.0, s, dn, endpoint=False) if dn else np.array([]),
        np.full(body, s),
        np.linspace(s, 0.0, rn) if rn else np.array([]),
    ])
    if len(env) < n:
        env = np.concatenate([env, np.zeros(n - len(env))])
    return env[:n]


def decay_env(n: int, tau: float, sr: int = SR) -> np.ndarray:
    t = _t(n, sr)
    return np.exp(-t / max(tau, 1e-4))


def saw(freq, n: int, phase: float = 0.0) -> np.ndarray:
    """Band-limited saw via additive synthesis. `freq` may be a scalar or a
    per-sample array (frequency sweep)."""
    f = np.asarray(freq, dtype=np.float64)
    t = _t(n)
    if f.ndim == 0:
        out = np.zeros(n)
        nyq = SR * 0.48
        k = 1
        while k * f < nyq and k < 60:
            out += np.sin(2 * np.pi * k * f * t + phase * k) / k
            k += 1
        return out * (2.0 / np.pi)
    ph = 2 * np.pi * np.cumsum(f) / SR + phase
    kmax = int(min(48, max(1, (SR * 0.48) / max(float(f.max()), 1.0))))
    out = np.zeros(n)
    for k in range(1, kmax + 1):
        out += np.sin(k * ph) / k
    return out * (2.0 / np.pi)


def square(freq, n: int, duty=0.5) -> np.ndarray:
    f = np.asarray(freq, dtype=np.float64)
    t = _t(n)
    if f.ndim == 0:
        out = np.zeros(n)
        nyq = SR * 0.48
        k = 1
        while k * f < nyq and k < 60:
            out += np.sin(2 * np.pi * k * f * t) * (2.0 / k) * (1 if k % 2 else 0)
            k += 1
        return out * (0.5 + duty * 0.5)
    ph = 2 * np.pi * np.cumsum(f) / SR
    kmax = int(min(48, max(1, (SR * 0.48) / max(float(f.max()), 1.0))))
    out = np.zeros(n)
    for k in range(1, kmax + 1, 2):
        out += np.sin(k * ph) * (2.0 / k)
    return out * (0.5 + duty * 0.5)


def noise(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-1, 1, n)


def svf(x: np.ndarray, cutoff, q=0.5, mode="lp", sr: int = SR) -> np.ndarray:
    """State-variable-style filter, vectorised with block-wise biquads."""
    from scipy.signal import lfilter
    n = len(x)
    if np.isscalar(cutoff):
        cutoff = np.full(n, float(cutoff))
    cutoff = np.asarray(cutoff, dtype=np.float64)
    if cutoff.size == 1:
        cutoff = np.full(n, cutoff[0])
    elif cutoff.size != n:
        cutoff = np.interp(np.linspace(0, 1, n),
                           np.linspace(0, 1, cutoff.size), cutoff)
    cutoff = np.clip(cutoff, 20.0, sr * 0.45)
    q = 1.0 - float(np.clip(q, 0.0, 0.95))
    block = 64
    out = np.empty(n)
    zi = None
    for start in range(0, n, block):
        end = min(start + block, n)
        fc = float(np.mean(cutoff[start:end]))
        w0 = 2 * np.pi * fc / sr
        alpha = np.sin(w0) / (2 * (q + 1e-6))
        cosw = np.cos(w0)
        if mode == "lp":
            b = [(1 - cosw) / 2, 1 - cosw, (1 - cosw) / 2]
            a = [1 + alpha, -2 * cosw, 1 - alpha]
        elif mode == "hp":
            b = [(1 + cosw) / 2, -(1 + cosw), (1 + cosw) / 2]
            a = [1 + alpha, -2 * cosw, 1 - alpha]
        else:  # bandpass
            b = [alpha, 0.0, -alpha]
            a = [1 + alpha, -2 * cosw, 1 - alpha]
        seg = x[start:end]
        if zi is None:
            y, zi = lfilter(b, a, seg, zi=np.zeros(2))
        else:
            y, zi = lfilter(b, a, seg, zi=zi)
        out[start:end] = y
    return out


def softclip(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    y = np.tanh(x * drive) / np.tanh(max(drive, 1e-6))
    return y


def dc_block(x: np.ndarray, r=0.997) -> np.ndarray:
    from scipy.signal import lfilter
    return lfilter([1.0], [1.0, -r], x)


def normalize(x: np.ndarray, peak=0.97) -> np.ndarray:
    m = float(np.max(np.abs(x)))
    if m < 1e-9:
        return x
    return x * (peak / m)


def duck(x: np.ndarray, depth=0.65, hold=0.02, release=0.12, sr: int = SR) -> np.ndarray:
    """Sidechain-style amplitude dip at the start of the sample."""
    n = len(x)
    env = np.ones(n)
    hn = max(1, int(hold * sr))
    rn = max(1, int(release * sr))
    env[:hn] = 1.0 - depth
    if rn > 0:
        ramp = np.linspace(1.0 - depth, 1.0, min(rn, n - hn))
        env[hn:hn + len(ramp)] = ramp
    return x * env


def fade(x: np.ndarray, in_s=0.002, out_s=0.01, sr: int = SR) -> np.ndarray:
    n = len(x)
    ni, no = min(int(in_s * sr), n // 2), min(int(out_s * sr), n // 2)
    if ni > 1:
        x[:ni] *= np.linspace(0, 1, ni)
    if no > 1:
        x[-no:] *= np.linspace(1, 0, no)
    return x


def write_wav(name: str, x: np.ndarray, sr: int = SR, peak=0.97) -> str:
    import soundfile as sf
    os.makedirs(OUT, exist_ok=True)
    x = normalize(np.asarray(x, dtype=np.float64), peak)
    path = os.path.join(OUT, name if name.endswith(".wav") else name + ".wav")
    sf.write(path, x, sr, subtype="PCM_16")
    return path


def _freq(name: str) -> float:
    """'A3' -> Hz."""
    names = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
             "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10,
             "Bb": 10, "B": 11}
    i = 2 if len(name) > 1 and name[1] in "#b" else 1
    p = name[:i]
    p = p[0] + ("#" if len(p) > 1 else "")
    octv = int(name[i:])
    midi = 12 * (octv + 1) + names[p]
    return 440.0 * 2 ** ((midi - 69) / 12.0)


# -------------------------------------------------------------- instruments --
def supersaw(freq, dur=1.0, voices=7, detune=0.16, cut_lo=300, cut_hi=9000,
             q=0.45, env_a=0.006, env_d=0.25, env_s=0.75, env_r=0.25,
             sr=SR, mix=None):
    """Classic trance/eurodance supersaw stack."""
    n = _n(dur, sr)
    out = np.zeros(n)
    rng = np.random.default_rng(7)
    for v in range(voices):
        off = (v - (voices - 1) / 2.0) * detune
        f = freq * 2 ** (off / 12.0)
        ph = rng.uniform(0, 2 * np.pi)
        out += saw(f, n, ph)
    out /= voices
    # unison widening in the stereo field is added by the caller (mono here)
    cut = np.linspace(cut_hi, cut_lo, n) if cut_hi > cut_lo else cut_hi
    out = svf(out, cut, q=q, mode="lp", sr=sr)
    env = adsr(n, env_a, env_d, env_s, env_r, sr)
    return fade(out * env, 0.003, 0.02, sr)


def trance_lead(freq, dur=1.0, sr=SR):
    """Bright, slightly over-driven trance lead."""
    n = _n(dur, sr)
    a = saw(freq, n, 0.0) * 0.7
    b = saw(freq * 2.0, n, 1.1) * 0.22
    c = square(freq, n, 0.5) * 0.12
    x = a + b + c
    cut = np.linspace(12000, 4200, n)
    x = svf(x, cut, q=0.28, mode="lp", sr=sr)
    x = softclip(x * 1.7, 1.6)
    env = adsr(n, 0.004, 0.09, 0.82, 0.10, sr)
    return fade(x * env, 0.002, 0.02, sr)


def fm_pluck(freq, dur=0.5, ratio=2.0, index=6.0, decay=0.16, sr=SR):
    """Two-operator FM pluck - the classic future-house bass voice."""
    n = _n(dur, sr)
    t = _t(n, sr)
    mod = np.sin(2 * np.pi * freq * ratio * t)
    idx = index * np.exp(-t / decay)
    x = np.sin(2 * np.pi * freq * t + idx * mod)
    x += 0.25 * np.sin(4 * np.pi * freq * t + 0.6 * idx * mod)
    x = svf(x, np.linspace(7000, 1200, n), q=0.2, mode="lp", sr=sr)
    env = np.exp(-t / (decay * 1.6))
    env[: int(0.002 * sr)] *= np.linspace(0, 1, int(0.002 * sr))
    return fade(x * env, 0.001, 0.015, sr)


def reese(freq, dur=0.5, sr=SR):
    """Detuned, distorted reese bass (trance)."""
    n = _n(dur, sr)
    x = np.zeros(n)
    for off, ph in ((-0.09, 0.0), (0.0, 1.7), (0.11, 3.1)):
        x += saw(freq * 2 ** (off / 12.0), n, ph) / 3.0
    x = svf(x, np.linspace(2400, 900, n), q=0.5, mode="lp", sr=sr)
    x = softclip(x * 2.4, 2.2)
    env = adsr(n, 0.004, 0.10, 0.85, 0.08, sr)
    return fade(x * env, 0.002, 0.015, sr)


def sub808(freq, dur=0.6, drive=2.4, sr=SR):
    """Saturated sine sub with a short pitch drop - phonk 808."""
    n = _n(dur, sr)
    t = _t(n, sr)
    f = freq * (1.0 + 0.06 * np.exp(-t / 0.02))
    x = np.sin(2 * np.pi * np.cumsum(f) / sr)
    x += 0.10 * np.sin(4 * np.pi * np.cumsum(f) / sr)
    x = softclip(x * drive, drive)
    env = adsr(n, 0.001, 0.08, 0.9, 0.10, sr)
    return fade(x * env, 0.001, 0.02, sr)


def hoover(freq, dur=1.0, sr=SR):
    """Eurodance hoover bass."""
    n = _n(dur, sr)
    x = np.zeros(n)
    for off, ph in ((-0.06, 0.0), (0.06, 2.2)):
        x += saw(freq * 2 ** (off / 12.0), n, ph) * 0.5
    x += square(freq, n, 0.5) * 0.18
    x = svf(x, np.linspace(4000, 1100, n), q=0.35, mode="lp", sr=sr)
    env = adsr(n, 0.006, 0.12, 0.85, 0.12, sr)
    return fade(x * env, 0.003, 0.02, sr)


def pluck(freq, dur=0.5, sr=SR, damp=0.5, bright=0.7):
    """Karplus-Strong string/pluck."""
    n = _n(dur, sr)
    f = int(sr / freq)
    if f < 2:
        f = 2
    rng = np.random.default_rng(int(freq * 100) % 99991)
    buf = rng.uniform(-1, 1, f)
    out = np.zeros(n)
    idx = 0
    for i in range(n):
        v = buf[idx]
        nv = 0.5 * (buf[idx] + buf[(idx + 1) % f])
        buf[idx] = nv * (0.996 - 0.01 * (1 - bright))
        idx = (idx + 1) % f
        out[i] = v
    out = svf(out, np.linspace(12000, 3000, n), q=0.2, mode="lp", sr=sr)
    env = adsr(n, 0.001, 0.05, 0.8, 0.10, sr)
    return fade(out * env, 0.001, 0.02, sr)


def vocal_chop(freq, dur=0.4, sr=SR, vowel="ah", bright=0.6):
    """Formant-synthesised vocal chop (original, not a stock sample)."""
    n = _n(dur, sr)
    t = _t(n, sr)
    # vibrato + slight pitch drift
    f = freq * (1 + 0.012 * np.sin(2 * np.pi * 5.2 * t))
    ph = 2 * np.pi * np.cumsum(f) / sr
    glottal = (np.sin(ph)
               + 0.55 * np.sin(2 * ph)
               + 0.32 * np.sin(3 * ph)
               + 0.2 * np.sin(4 * ph)
               + 0.12 * np.sin(5 * ph)) * 0.4
    formants = {"ah": [700, 1220, 2600], "eh": [530, 1840, 2480],
                "oh": [450, 800, 2830], "ee": [270, 2290, 3010],
                "oo": [300, 870, 2250], "ai": [660, 1720, 2410]}[vowel]
    out = np.zeros(n)
    for i, fc in enumerate(formants):
        bw = 90 + 110 * i
        out += svf(glottal, fc, q=fc / bw, mode="bp", sr=sr) * (1.0 / (i + 1))
    out = svf(out, 7000, q=0.7, mode="lp", sr=sr) * (0.35 + 0.65 * bright)
    env = adsr(n, 0.008, 0.06, 0.85, 0.10, sr)
    return fade(out * env, 0.004, 0.02, sr)


# -------------------------------------------------------------------- FX ----
def riser(dur=4.0, sr=SR):
    n = _n(dur, sr)
    t = _t(n, sr)
    x = noise(n, seed=11)
    cut = np.exp(np.linspace(np.log(300), np.log(16000), n))
    x = svf(x, cut, q=0.6, mode="bp", sr=sr)
    x *= (t / dur) ** 2.2
    x += 0.3 * saw(np.exp(np.linspace(np.log(200), np.log(4000), n)), n) * (t / dur) ** 3
    return fade(x, 0.01, 0.05, sr)


def impact(dur=2.0, sr=SR):
    n = _n(dur, sr)
    t = _t(n, sr)
    x = noise(n, seed=3) * np.exp(-t / 0.10)
    x += 0.6 * np.sin(2 * np.pi * (55 * np.exp(-t / 0.18) + 38) * t) * np.exp(-t / 0.25)
    x = svf(x, np.linspace(9000, 700, n), q=0.3, mode="lp", sr=sr)
    return fade(x, 0.001, 0.15, sr)


def vinyl(dur=4.0, sr=SR, crackle=0.05):
    n = _n(dur, sr)
    rng = np.random.default_rng(5)
    x = noise(n, seed=21) * crackle
    # sparse crackle pops
    k = max(1, int(sr * 0.02))
    for i in range(0, n, k):
        if rng.random() < 0.25:
            amp = rng.uniform(0.1, 0.5)
            L = int(rng.uniform(0.0005, 0.004) * sr)
            x[i:i + L] += rng.uniform(-1, 1, L) * amp * np.exp(-np.arange(L) / (sr * 0.0008))
    x = svf(x, 6500, q=0.2, mode="lp", sr=sr)
    return x


def noise_sweep(dur=2.0, up=True, sr=SR):
    n = _n(dur, sr)
    x = noise(n, seed=33)
    a, b = (200, 14000) if up else (14000, 200)
    x = svf(x, np.exp(np.linspace(np.log(a), np.log(b), n)), q=0.5, mode="bp", sr=sr)
    ramp = np.linspace(0.0, 1.0, n)
    e = ramp ** 2 if up else (1.0 - ramp) ** 2
    return fade(x * e, 0.01, 0.05, sr)


def reverse_crash(dur=1.6, sr=SR):
    n = _n(dur, sr)
    x = noise(n, seed=41)
    x = svf(x, np.exp(np.linspace(np.log(12000), np.log(2500), n)), q=0.4, mode="hp", sr=sr)
    x *= np.exp(-np.linspace(0, 6, n))
    return x[::-1].copy()


def clap_layer(dur=0.35, sr=SR, seed=99):
    """Layered clap: 3 noise bursts + body."""
    n = _n(dur, sr)
    out = np.zeros(n)
    for k, off in enumerate((0.0, 0.011, 0.021, 0.032)):
        s = int(off * sr)
        seg = noise(n - s, seed=seed + k) * np.exp(-np.arange(n - s) / (sr * 0.007))
        out[s:] += seg * 0.55
    body = np.sin(2 * np.pi * 1100 * _t(n, sr)) * np.exp(-_t(n, sr) / 0.006) * 0.4
    tail = noise(n, seed=7) * np.exp(-_t(n, sr) / 0.09) * 0.25
    out = out + body + tail
    out = svf(out, np.linspace(6000, 9000, n), q=0.4, mode="bp", sr=sr)
    return fade(out, 0.001, 0.02, sr)


def hat(dur=0.06, open_=False, sr=SR, seed=3):
    n = _n(dur, sr)
    x = noise(n, seed=seed)
    x = svf(x, 9000, q=0.2, mode="hp", sr=sr)
    x = svf(x, 11000, q=0.3, mode="hp", sr=sr)
    env = np.exp(-_t(n, sr) / (0.11 if open_ else 0.012))
    return fade(x * env, 0.0005, 0.008, sr)


def kick_synth(dur=0.42, sr=SR, punch=1.0):
    n = _n(dur, sr)
    t = _t(n, sr)
    f = 52 * np.exp(-t / 0.035) + 43
    body = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.16)
    click = noise(n, seed=13) * np.exp(-t / 0.0035) * 0.5 * punch
    x = softclip((body * 1.5 + click) * 1.4, 1.7)
    return fade(x, 0.0008, 0.02, sr)


def snare_synth(dur=0.22, sr=SR):
    n = _n(dur, sr)
    t = _t(n, sr)
    tone = (np.sin(2 * np.pi * 190 * t) + np.sin(2 * np.pi * 278 * t)) * np.exp(-t / 0.055) * 0.6
    nz = noise(n, seed=17) * np.exp(-t / 0.075)
    x = svf(tone + nz * 0.9, np.linspace(5200, 3200, n), q=0.4, mode="bp", sr=sr)
    return fade(x, 0.0008, 0.02, sr)


def tom(freq=180, dur=0.3, sr=SR):
    n = _n(dur, sr)
    t = _t(n, sr)
    f = freq * np.exp(-t / 0.09) + freq * 0.82
    x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.11)
    x = softclip(x * 1.6, 1.5)
    return fade(x, 0.001, 0.02, sr)


# --------------------------------------------------------------- wavetables --
def wavetable(name: str, harmonics: list[float], sr: int = SR, size: int = 2048) -> str:
    """Render a periodic wavetable .wav for LMMS's Watsyn instrument."""
    import soundfile as sf
    os.makedirs(OUT, exist_ok=True)
    n = np.arange(size)
    wave = np.zeros(size)
    for k, amp in enumerate(harmonics, start=1):
        wave += amp * np.sin(2 * np.pi * k * n / size)
    wave = np.concatenate([wave, wave])          # for looping
    wave = normalize(wave, 0.98)
    path = os.path.join(OUT, name if name.endswith(".wav") else name + ".wav")
    sf.write(path, wave.astype(np.float32), sr, subtype="PCM_16")
    return path

