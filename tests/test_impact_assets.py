"""素材检查保护即时起音、分层来源和擦碰环缝。"""

import hashlib
import json
import math
import wave
from array import array

from paths import resource_root


def test_impact_bank_has_distinct_verified_variants_and_fast_transients():
    root = resource_root() / "assets" / "game" / "audio"
    bank = json.loads((root / "impact-bank.json").read_text(encoding="utf-8"))
    assert bank["version"] == 2
    for name, variants in bank["pools"].items():
        assert len(variants) >= (2 if name.startswith("scrape") else 3)
        assert len({entry["sha256"] for entry in variants}) == len(variants)
        early_rms = []
        for entry in variants:
            path = root / entry["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
            with wave.open(str(path), "rb") as clip:
                assert (clip.getnchannels(), clip.getsampwidth(), clip.getframerate()) == (1, 2, 44100)
                samples = array("h", clip.readframes(clip.getnframes()))
            peak = max(abs(value) for value in samples)
            assert peak <= 32767
            if name.startswith("transient"):
                onset = next(i for i, value in enumerate(samples) if abs(value) >= peak * .1)
                assert onset / 44100 < .005
                window = samples[:round(.08 * 44100)]
                early_rms.append(math.sqrt(sum(value * value for value in window)
                                           / len(window)) / 32768)
            if name.startswith("scrape"):
                assert abs(samples[0] - samples[-1]) <= 2
                assert len(samples) / 44100 >= 2.4
                rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
                assert rms > .025
            else:
                # 单次撞击不携带持续滑动尾音；真正擦碰只由独立接触循环产生。
                assert len(samples) / 44100 <= .40
                if len(samples) > round(.24 * 44100):
                    head = samples[:round(.08 * 44100)]
                    tail = samples[round(.24 * 44100):]
                    head_rms = math.sqrt(sum(x*x for x in head) / len(head))
                    tail_rms = math.sqrt(sum(x*x for x in tail) / len(tail))
                    assert tail_rms / head_rms < .20
        if early_rms:
            assert 20 * math.log10(max(early_rms) / min(early_rms)) < 4.0
