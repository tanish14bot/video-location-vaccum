from __future__ import annotations

from video_location_vaccum.audio.fit import fit_pass
from video_location_vaccum.audio.spectrogram import compute_spectrogram
from video_location_vaccum.audio.trace import trace_ridge
from video_location_vaccum.demo import build_scene


def test_trace_and_fit_synthetic_flyover() -> None:
    scene = build_scene()
    seg = scene.audio[int(60 * scene.sr) : int(180 * scene.sr)]
    spec = compute_spectrogram(seg, scene.sr, nperseg=2048, hop=128, fmin=60, fmax=400)
    z = spec.whiten(line_s=0)
    tr = trace_ridge(z, f_start=190.0, f_end=110.0, min_z=1.0)
    assert tr.times.size > 100
    assert tr.freqs[0] > tr.freqs[-1]
    fit = fit_pass(tr.times, tr.freqs, c_mps=343.0, height_m=0.0)
    assert abs(fit.pass_.f0_hz - 140.0) < 10.0
    assert abs(fit.pass_.speed_mps - 90.0) < 25.0
