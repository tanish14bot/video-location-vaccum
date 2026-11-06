from __future__ import annotations

import numpy as np

from video_location_vaccum.model.doppler import (
    StraightLinePass,
    delayed_cpa_time,
    doppler_frequency,
    radial_velocity,
    speed_of_sound,
)


def test_speed_of_sound() -> None:
    assert abs(speed_of_sound(20.0, 0.0) - 343.0) < 1.5
    assert speed_of_sound(30.0, 0.0) > speed_of_sound(0.0, 0.0)


def test_sign_convention() -> None:
    # Receding positive => lower frequency.
    assert float(doppler_frequency(100.0, 343.0, 50.0)) < 100.0
    assert float(doppler_frequency(100.0, 343.0, -50.0)) > 100.0
    assert float(doppler_frequency(100.0, 343.0, 0.0)) == 100.0


def test_radial_velocity_sign() -> None:
    observer = np.zeros(3)
    # Aircraft at +x moving +x: receding.
    vr = radial_velocity(np.array([1000.0, 0, 0]), np.array([100.0, 0, 0]), observer)
    assert float(vr) > 0
    # Aircraft at +x moving -x: approaching.
    vr = radial_velocity(np.array([1000.0, 0, 0]), np.array([-100.0, 0, 0]), observer)
    assert float(vr) < 0


def test_cpa_frequency_is_f0_at_delayed_time() -> None:
    c = 343.0
    p = StraightLinePass(
        f0_hz=131.5, speed_mps=106.5, cpa_horizontal_m=3130.0, cpa_time_s=100.0, height_m=0.0
    )
    slant = 3130.0
    t_heard = delayed_cpa_time(100.0, slant, c)
    f = float(p.frequency(np.array([t_heard]), c)[0])
    assert abs(f - 131.5) < 0.5


def test_approach_is_higher_recede_is_lower() -> None:
    c = 343.0
    p = StraightLinePass(
        f0_hz=131.5, speed_mps=106.5, cpa_horizontal_m=3130.0, cpa_time_s=100.0, height_m=0.0
    )
    f_before = float(p.frequency(np.array([60.0]), c)[0])
    f_after = float(p.frequency(np.array([140.0]), c)[0])
    assert f_before > 131.5 > f_after


def test_delay_disappears_at_large_speed_of_sound() -> None:
    p = StraightLinePass(
        f0_hz=131.5, speed_mps=106.5, cpa_horizontal_m=3130.0, cpa_time_s=100.0, height_m=0.0
    )
    t = np.linspace(70, 130, 25)
    # With an enormous c the propagation delay and the Doppler shift both vanish;
    # the delayed and instantaneous models must then agree.
    f_delay = p.frequency(t, 1e9)
    f_fast = p.frequency_no_delay(t, 1e9)
    assert np.max(np.abs(f_delay - f_fast)) < 1e-6
