"""分段计时覆盖生成器实际执行，并排除交回结果前的等待。"""

import pytest
from performance import benchmark_physics


def test_generator_timing_counts_read_and_resume_without_external_wait(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(benchmark_physics.time,'perf_counter',lambda:clock[0])

    class Computation:
        def stages(self):
            clock[0] += 2.
            result = yield 'frozen-input'
            clock[0] += 3.
            return result*2

    original = Computation.stages
    timer = benchmark_physics.PhaseTimers()
    timer.enabled = True
    timer.stages(Computation,'stages','read','commit')
    try:
        stages = Computation().stages()
        assert timer.samples == {}
        assert next(stages) == 'frozen-input'
        clock[0] += 1000.
        with pytest.raises(StopIteration) as finished:
            stages.send(7)
        assert finished.value.value == 14
        assert timer.samples == {'read':[2.],'commit':[3.]}
    finally:
        timer.restore()
    assert Computation.stages is original


def test_tail_statistics_keep_outliers_and_use_documented_linear_quantiles():
    statistics = benchmark_physics.distribution([.001,.003,.002])
    assert statistics['mean_ms'] == pytest.approx(2.)
    assert statistics['p95_ms'] == pytest.approx(2.9)
    assert statistics['p99_ms'] == pytest.approx(2.98)
    assert statistics['max_ms'] == 3.
    assert statistics['total_seconds'] == .006
